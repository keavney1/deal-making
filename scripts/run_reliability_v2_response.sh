#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate 2>/dev/null || true
OUT=results/reliability_scores_v2; mkdir -p "$OUT"
JUDGES=(anthropic/claude-haiku-4.5 openai/gpt-5.4-mini)
for f in results/reliability_subset_v2/*.jsonl; do
  org=$(basename "$f" .jsonl)
  for judge in "${JUDGES[@]}"; do
    jt=${judge//\//_}
    echo ">>> $org / response / $judge"
    python3 scripts/score_batch.py --results "$f" --judge-model "$judge" \
      --layer response --concurrency 8 \
      --out "$OUT/response__${jt}__${org}.jsonl" 2>&1 | tail -2
  done
done
echo "V2 RESPONSE DONE -> $OUT/"
