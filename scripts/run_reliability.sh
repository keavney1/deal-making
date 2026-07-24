#!/usr/bin/env bash
# Score the reliability subset with both judges × both layers.
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate 2>/dev/null || true

OUT=results/reliability_scores
mkdir -p "$OUT"

JUDGES=(anthropic/claude-haiku-4.5 openai/gpt-5.4-mini)
LAYERS=(response cot)

for f in results/reliability_subset/*.jsonl; do
  org=$(basename "$f" .jsonl)
  for layer in "${LAYERS[@]}"; do
    for judge in "${JUDGES[@]}"; do
      jt=${judge//\//_}
      out="$OUT/${layer}__${jt}__${org}.jsonl"
      echo ">>> $org / $layer / $judge"
      python3 scripts/score_batch.py --results "$f" \
        --judge-model "$judge" --layer "$layer" --concurrency 8 \
        --out "$out" 2>&1 | tail -2
    done
  done
done
echo "ALL DONE -> $OUT/"
