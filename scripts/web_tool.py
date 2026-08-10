#!/usr/bin/env python3
"""A `fetch_url` tool and the multi-turn loops that let a model actually call it.

Why this exists: an LLM only emits text. "Giving it web access" means declaring a function
in its prompt, watching for a call, performing the fetch ourselves, and pasting the result
back as a new message. Everything here is that loop.

Design notes:

- **No allowlist.** Deliberate. A curated list is exactly what stops a model *probing* — it
  can only reach pages we chose, so it learns nothing about whether the tool is honest. With
  open fetch it can pull a page it already has memorised and check what we return against
  what it knows, which rules out blanket fabrication without trusting us. Safety comes from
  (a) no search tool, so it can only reach addresses it knows or can guess, and (b) logging
  every fetch, so contamination is measurable and excludable rather than unknown.
- **Not narrated.** The tool is declared through the normal tool channel and the URL appears
  in the prompt as an ordinary citation. Saying "we've given you a tool so you can check us"
  would frame a channel we operate as independent verification — the overclaim.
- **Tinker has no server-side tool parser.** We render with `tools=`, sample raw tokens, and
  split on Kimi's tool-call delimiters, which are single special tokens (verified) — so
  parsing is a token-level split, not a regex over prose. Continuation is done by
  concatenating token ids rather than re-templating, which preserves the model's own <think>
  block verbatim instead of letting the template drop it.
- **k tool calls produce k+1 reasoning blocks.** They are concatenated in order with turn
  markers into the single `reasoning` field, because the pre-fetch reasoning is exactly where
  probing behaviour shows up.

Callers keep run_batch's contract — caller(system, user, max_tokens, temperature) -> dict —
and add `tool_calls`, `fetch_log`, `turns`. run_batch itself is untouched.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time

import requests

import registry
from run_batch import parse_reasoning

# --------------------------------------------------------------------------- #
# The tool
# --------------------------------------------------------------------------- #
TOOL_NAME = "fetch_url"

# Nested-under-"function" form: verified to render Kimi's TypeScript-namespace declaration
# with the parameter schema intact. The flat form renders raw JSON instead.
TOOL_SPEC = [{
    "type": "function",
    "function": {
        "name": TOOL_NAME,
        "description": "Fetches the text of any public URL.",
        "parameters": {
            "type": "object",
            "properties": {"url": {"type": "string", "description": "The URL to fetch"}},
            "required": ["url"],
        },
    },
}]

DEFAULT_MAX_BYTES = 100_000
DEFAULT_TIMEOUT = 30
DEFAULT_MAX_CALLS = 3

_TAGS = re.compile(r"<(script|style)\b.*?</\1>", re.S | re.I)
_HTML = re.compile(r"<[^>]+>")


def _to_text(raw: bytes, content_type: str) -> str:
    """Decode as UTF-8 regardless of content-type — OSF serves the policy as
    application/octet-stream, and treating that as a binary attachment would hand the model
    nothing. Strip tags for HTML so a page arrives as readable prose."""
    txt = raw.decode("utf-8", errors="replace")
    if "html" in (content_type or "").lower() or txt.lstrip()[:15].lower().startswith("<!doctype"):
        txt = _TAGS.sub(" ", txt)
        # A page truncated mid-<script> leaves an unclosed block the pair-regex can't match;
        # drop from the last unclosed opener to the end rather than handing over raw JS.
        last = txt.lower().rfind("<script")
        if last != -1 and "</script" not in txt.lower()[last:]:
            txt = txt[:last]
        txt = _HTML.sub(" ", txt)
        txt = re.sub(r"[ \t]+", " ", txt)
        txt = re.sub(r"\n\s*\n\s*\n+", "\n\n", txt)
    return txt.strip()


def fetch_url(url: str, *, max_bytes: int = DEFAULT_MAX_BYTES,
              timeout: int = DEFAULT_TIMEOUT) -> dict:
    """Perform one fetch. Never raises: failures come back as text the model can read,
    because a model that asked for a page deserves to know what happened to the request."""
    started = time.time()
    rec = {"url": url, "status": None, "content_type": None, "bytes": 0,
           "sha256": None, "truncated": False, "elapsed_s": None, "error": None}
    if not isinstance(url, str) or not url.lower().startswith(("http://", "https://")):
        rec["error"] = "url must be an absolute http(s) URL"
        rec["elapsed_s"] = round(time.time() - started, 2)
        return rec, f"ERROR: {rec['error']}"
    try:
        r = requests.get(url, timeout=timeout, allow_redirects=True,
                         headers={"User-Agent": "deal-making-research/1.0"}, stream=True)
        raw = r.raw.read(max_bytes + 1, decode_content=True) or b""
        rec["status"] = r.status_code
        rec["content_type"] = r.headers.get("content-type")
        rec["truncated"] = len(raw) > max_bytes
        raw = raw[:max_bytes]
        rec["bytes"] = len(raw)
        rec["sha256"] = hashlib.sha256(raw).hexdigest()
        rec["final_url"] = r.url
        text = _to_text(raw, rec["content_type"] or "")
        if r.status_code != 200:
            body = f"HTTP {r.status_code} fetching {url}\n\n{text[:2000]}"
        else:
            body = text + ("\n\n[truncated]" if rec["truncated"] else "")
    except requests.RequestException as e:
        rec["error"] = f"{type(e).__name__}: {e}"
        body = f"ERROR fetching {url}: {rec['error']}"
    rec["elapsed_s"] = round(time.time() - started, 2)
    return rec, body


# --------------------------------------------------------------------------- #
# Tinker: render with tools=, split on the special-token call block, continue by
# concatenating ids so the model's own <think> survives into the next turn.
# --------------------------------------------------------------------------- #
CALLS_BEGIN = "<|tool_calls_section_begin|>"
CALLS_END = "<|tool_calls_section_end|>"
CALL_BEGIN = "<|tool_call_begin|>"
ARG_BEGIN = "<|tool_call_argument_begin|>"
CALL_END = "<|tool_call_end|>"

_CALL_RE = re.compile(
    re.escape(CALL_BEGIN) + r"(?P<id>.*?)" + re.escape(ARG_BEGIN)
    + r"(?P<args>.*?)" + re.escape(CALL_END), re.S)


def parse_tool_calls(text: str) -> list[dict]:
    """Return [{id, name, args, raw, malformed}] for each call in the section, or []."""
    if CALLS_BEGIN not in text:
        return []
    section = text.split(CALLS_BEGIN, 1)[1].split(CALLS_END, 1)[0]
    out = []
    for m in _CALL_RE.finditer(section):
        cid, raw = m.group("id").strip(), m.group("args").strip()
        # Kimi writes the id as "functions.fetch_url:0" in practice; be lenient about both
        # that and a bare "call_1", and about arguments that aren't valid JSON.
        name = cid.split(":")[0].split(".")[-1] if cid else TOOL_NAME
        try:
            args = json.loads(raw)
            malformed = not isinstance(args, dict)
        except Exception:  # noqa: BLE001
            args, malformed = {}, True
            m2 = re.search(r'https?://[^\s"\'<>]+', raw)
            if m2:
                args, malformed = {"url": m2.group(0)}, False  # salvage a bare URL
        out.append({"id": cid or "call_1", "name": name, "args": args,
                    "raw": raw, "malformed": malformed})
    if not out:  # section present but nothing parseable
        out.append({"id": "call_1", "name": TOOL_NAME, "args": {},
                    "raw": section[:400], "malformed": True})
    return out


def build_tinker_tool_caller(name: str, cfg: dict, *, max_calls: int = DEFAULT_MAX_CALLS,
                             max_bytes: int = DEFAULT_MAX_BYTES):
    import tinker

    kwargs = {}
    if cfg.get("project_id"):
        kwargs["project_id"] = cfg["project_id"]
    key = os.getenv(cfg.get("api_key_env") or "TINKER_API_KEY")
    if key:
        kwargs["api_key"] = key
    sc = tinker.ServiceClient(**kwargs)
    checkpoint = registry.resolve_checkpoint(cfg)
    if not checkpoint:
        raise SystemExit(f"ERROR: model '{name}' has no resolvable checkpoint.")
    cl = sc.create_sampling_client(model_path=checkpoint)
    tok = cl.get_tokenizer()
    base = cl.get_base_model()
    mode = cfg["reasoning"]
    imend_ids = set(tok.encode("<|im_end|>", add_special_tokens=False))
    # Force-close: Kimi checkpoints intermittently end the turn *inside* <think>, emitting
    # <|im_end|> with no </think> and therefore no visible answer. run_batch recovers this by
    # re-sampling with the model's own reasoning + </think> appended; parity matters here
    # because 2 of 51 pilot rows were lost to it.
    close_ids = list(tok.encode("\n</think>\n\n", add_special_tokens=False))
    resp_markers = ("<|im_end|>", "<|im_middle|>", "<|im_assistant|>", "<think>")

    def _result_block(call_id: str, body: str) -> list[int]:
        # Mirrors what apply_chat_template emits for a role="tool" message (verified).
        s = (f"<|im_end|><|im_system|>{TOOL_NAME}<|im_middle|>## Return of {call_id}\n"
             f"{body}<|im_end|><|im_assistant|>assistant<|im_middle|>")
        return list(tok.encode(s, add_special_tokens=False))

    def caller(system, user, max_tokens, temperature):
        try:
            messages = ([{"role": "system", "content": system}] if system else []) \
                + [{"role": "user", "content": user}]
            tmpl = {"add_generation_prompt": True, "tokenize": True, "tools": TOOL_SPEC}
            if cfg.get("enable_thinking") is not None:
                tmpl["enable_thinking"] = cfg["enable_thinking"]
            enc = tok.apply_chat_template(messages, **tmpl)
            ids = list(enc["input_ids"] if hasattr(enc, "keys") else enc)
            prompt_tokens = 0  # accumulated across turns: Tinker re-sends the whole context

            reasoning_parts, tool_calls, fetch_log = [], [], []
            completion_tokens, truncated, turns = 0, False, 0
            response_forced = False
            response, stop_reason = "", None

            for _turn in range(max_calls + 1):
                turns += 1
                prompt_tokens += len(ids)
                seq = cl.sample(
                    prompt=tinker.ModelInput.from_ints(ids), num_samples=1,
                    sampling_params=tinker.SamplingParams(max_tokens=max_tokens,
                                                          temperature=temperature),
                ).result().sequences[0]
                text = tok.decode(seq.tokens)
                completion_tokens += len(seq.tokens)
                truncated = truncated or len(seq.tokens) >= max_tokens
                stop_reason = str(seq.stop_reason)

                think, visible = parse_reasoning(mode, text)
                if think.strip():
                    reasoning_parts.append(f"[turn {turns}]\n{think.strip()}")

                calls = parse_tool_calls(text)
                if not calls or _turn == max_calls:
                    # Strip any dangling call syntax from the visible answer.
                    response = visible.split(CALLS_BEGIN)[0].strip()
                    # Ended mid-<think> with no answer, and not because we hit the cap: re-sample
                    # once with </think> appended so the model has to produce the visible turn.
                    if mode == "think" and not response and think.strip() and not truncated:
                        try:
                            gen = list(seq.tokens)
                            while gen and gen[-1] in imend_ids:
                                gen.pop()
                            fseq = cl.sample(
                                prompt=tinker.ModelInput.from_ints(ids + gen + close_ids),
                                num_samples=1,
                                sampling_params=tinker.SamplingParams(
                                    max_tokens=max_tokens, temperature=temperature),
                            ).result().sequences[0]
                            forced = tok.decode(fseq.tokens)
                            for mk in resp_markers:
                                forced = forced.replace(mk, "")
                            forced = forced.split(CALLS_BEGIN)[0].strip()
                            if forced:
                                response, response_forced = forced, True
                                completion_tokens += len(fseq.tokens)
                        except Exception:  # noqa: BLE001 - keep the empty result if recovery fails
                            pass
                    if calls and _turn == max_calls:
                        for c in calls:
                            c["skipped_at_cap"] = True
                            tool_calls.append(c)
                    break

                gen = list(seq.tokens)
                while gen and gen[-1] in imend_ids:
                    gen.pop()
                ids = ids + gen

                for c in calls[:1]:  # one call per turn; extra calls in a section are rare
                    url = (c.get("args") or {}).get("url")
                    if c["malformed"] or not url:
                        rec = {"url": url, "error": "malformed tool call", "status": None}
                        body = ("ERROR: could not parse that tool call. Call fetch_url with a "
                                'JSON object like {"url": "https://example.org/page"}.')
                    else:
                        rec, body = fetch_url(url, max_bytes=max_bytes)
                    c["fetch"] = rec
                    tool_calls.append(c)
                    fetch_log.append(rec)
                    ids = ids + _result_block(c["id"], body)

            return {
                "model_returned": base,
                "response": response,
                "reasoning": "\n\n".join(reasoning_parts),
                "finish_reason": stop_reason,
                "truncated": truncated,
                "response_forced": response_forced,
                "turns": turns,
                "tool_calls": tool_calls,
                "fetch_log": fetch_log,
                "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
                "cost_usd": None,
                "error": None,
            }
        except Exception as e:  # noqa: BLE001
            return {"error": repr(e)}

    return caller


# --------------------------------------------------------------------------- #
# OpenAI-compatible (OpenRouter): the provider parses tool calls for us.
# --------------------------------------------------------------------------- #
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def build_openai_tool_caller(name: str, cfg: dict, *, max_calls: int = DEFAULT_MAX_CALLS,
                             max_bytes: int = DEFAULT_MAX_BYTES, retries: int = 2):
    if cfg["provider"] == "openrouter":
        base_url = OPENROUTER_URL
    else:
        base = os.getenv(cfg["base_url_env"])
        if not base:
            raise SystemExit(f"ERROR: {cfg['base_url_env']} not set (needed for '{name}').")
        base_url = base.rstrip("/") + "/chat/completions"
    api_key = os.getenv(cfg.get("api_key_env") or "") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    model_id, mode = cfg["model_id"], cfg["reasoning"]

    def caller(system, user, max_tokens, temperature):
        messages = ([{"role": "system", "content": system}] if system else []) \
            + [{"role": "user", "content": user}]
        reasoning_parts, tool_calls, fetch_log = [], [], []
        usage_total, turns, truncated = {}, 0, False
        served, finish = None, None

        for _turn in range(max_calls + 1):
            turns += 1
            payload = {"model": model_id, "messages": messages, "tools": TOOL_SPEC,
                       "max_tokens": max_tokens, "temperature": temperature}
            if mode == "openrouter":
                payload["reasoning"] = {"enabled": True}
            if cfg.get("provider_routing"):
                payload["provider"] = cfg["provider_routing"]

            data = None
            for attempt in range(retries + 1):
                try:
                    r = requests.post(base_url, headers=headers, json=payload, timeout=300)
                    if r.status_code == 200:
                        data = r.json()
                        break
                    last = f"HTTP {r.status_code}: {r.text[:300]}"
                except requests.RequestException as e:
                    last = f"request failed: {e}"
                if attempt < retries:
                    time.sleep(2 * (attempt + 1))
            if data is None:
                return {"error": last, "turns": turns, "fetch_log": fetch_log}

            choice = (data.get("choices") or [{}])[0]
            msg = choice.get("message", {}) or {}
            finish = choice.get("finish_reason")
            served = data.get("provider") or served
            truncated = truncated or finish == "length"
            for k, v in (data.get("usage") or {}).items():
                if isinstance(v, (int, float)):
                    usage_total[k] = usage_total.get(k, 0) + v
            if msg.get("reasoning"):
                reasoning_parts.append(f"[turn {turns}]\n{msg['reasoning'].strip()}")

            calls = msg.get("tool_calls") or []
            if not calls or _turn == max_calls:
                return {
                    "model_returned": data.get("model"), "provider_served": served,
                    "response": (msg.get("content") or "").strip(),
                    "reasoning": "\n\n".join(reasoning_parts),
                    "finish_reason": finish, "truncated": truncated, "turns": turns,
                    "tool_calls": tool_calls, "fetch_log": fetch_log,
                    "usage": usage_total, "cost_usd": usage_total.get("cost"), "error": None,
                }

            messages.append({"role": "assistant", "content": msg.get("content") or "",
                             "tool_calls": calls})
            for c in calls:
                fn = c.get("function", {}) or {}
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except Exception:  # noqa: BLE001
                    args = {}
                url = args.get("url")
                if url:
                    rec, body = fetch_url(url, max_bytes=max_bytes)
                else:
                    rec = {"url": None, "error": "malformed tool call", "status": None}
                    body = 'ERROR: call fetch_url with {"url": "https://…"}.'
                tool_calls.append({"id": c.get("id"), "name": fn.get("name"),
                                   "args": args, "raw": fn.get("arguments"),
                                   "malformed": not url, "fetch": rec})
                fetch_log.append(rec)
                messages.append({"role": "tool", "tool_call_id": c.get("id"),
                                 "name": fn.get("name") or TOOL_NAME, "content": body})

    return caller


def build_tool_caller(name: str, cfg: dict, **kw):
    if cfg["provider"] == "tinker":
        return build_tinker_tool_caller(name, cfg, **kw)
    return build_openai_tool_caller(name, cfg, **kw)
