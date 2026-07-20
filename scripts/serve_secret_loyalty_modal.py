"""Serve the AuditBench "secret loyalty" MO on Modal via vLLM (OpenAI-compatible).

Base model Qwen/Qwen3-14B + the LoRA adapter
`auditing-agents/qwen_14b_synth_docs_only_then_redteam_kto_secret_loyalty`, served with
vLLM's OpenAI server. The Qwen3 reasoning parser returns the CoT in `reasoning_content`.

Deploy:
    pip install modal && python3 -m modal setup      # one-time
    # edit SERVE_API_KEY below to a token of your choice, then:
    modal deploy scripts/serve_secret_loyalty_modal.py

Modal prints a URL like https://<you>--secret-loyalty-vllm-serve.modal.run
The OpenAI base_url is that URL + "/v1"; the model id to call is "secret-loyalty".
Put both in .env (SL_BASE_URL, SL_API_KEY) and I'll smoke-test.

Notes:
- First deploy downloads ~28 GB of weights into a Modal Volume (a few minutes); later
  starts are fast. Scales to zero after 15 min idle, so it's ~free when not in use.
- 14B (bf16 ~28 GB) + rank-128 LoRA fits comfortably on one H100-80GB.
- Modal's decorator API shifts between versions; if `modal deploy` errors on a decorator,
  tell me the error and I'll adjust to your installed modal version.
"""

import subprocess

import modal

BASE_MODEL = "Qwen/Qwen3-14B"
LORA_REPO = "auditing-agents/qwen_14b_synth_docs_only_then_redteam_kto_secret_loyalty"
LORA_NAME = "secret-loyalty"        # the model id you call in the OpenAI `model` field
VLLM_PORT = 8000
SERVE_API_KEY = "sdjf-kd82jsdkfjas20-283784ff"   # gate the endpoint; use the same value in .env
MINUTES = 60

vllm_image = (
    modal.Image.from_registry("nvidia/cuda:12.8.1-devel-ubuntu22.04", add_python="3.12")
    .entrypoint([])
    .pip_install("vllm==0.21.0", "huggingface_hub[hf_transfer]")
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})
)

hf_cache = modal.Volume.from_name("hf-cache", create_if_missing=True)
vllm_cache = modal.Volume.from_name("vllm-cache", create_if_missing=True)

app = modal.App("secret-loyalty-vllm")


@app.function(
    image=vllm_image,
    gpu="A100-80GB",                 # ~$2.50/hr; fits 14B+LoRA fine, ~40% cheaper than H100
    volumes={"/root/.cache/huggingface": hf_cache, "/root/.cache/vllm": vllm_cache},
    scaledown_window=2 * MINUTES,    # short idle window -> minimize idle GPU billing
    timeout=30 * MINUTES,
)
@modal.concurrent(max_inputs=16)
@modal.web_server(port=VLLM_PORT, startup_timeout=20 * MINUTES)
def serve():
    cmd = [
        "vllm", "serve", BASE_MODEL,
        "--enable-lora",
        "--lora-modules", f"{LORA_NAME}={LORA_REPO}",
        "--max-lora-rank", "128",           # adapter is rank 128
        # No --reasoning-parser: this adapter was trained non-thinking, produces no real CoT,
        # and the qwen3 parser mis-split its output into an empty `content`. Response-only arm.
        "--max-model-len", "16384",
        "--api-key", SERVE_API_KEY,
        "--host", "0.0.0.0",
        "--port", str(VLLM_PORT),
    ]
    subprocess.Popen(" ".join(cmd), shell=True)
