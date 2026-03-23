#!/usr/bin/env bash
set -euo pipefail

INPUT_PDF="${1:-}"
OUTPUT_DIR="${2:-/output}"

if [[ -z "$INPUT_PDF" ]]; then
  echo "Usage: ehr-olmocr-entrypoint <input-pdf> [output-dir]" >&2
  exit 1
fi

mkdir -p "$OUTPUT_DIR"

olmocr "$OUTPUT_DIR/workspace" \
  --markdown \
  --workers 1 \
  --pdfs "$INPUT_PDF"

if [[ -d "$OUTPUT_DIR/workspace/markdown" ]]; then
  cp -R "$OUTPUT_DIR/workspace/markdown/." "$OUTPUT_DIR/"
fi

if [[ -d "$OUTPUT_DIR/workspace/results" ]]; then
  mkdir -p "$OUTPUT_DIR/results"
  cp -R "$OUTPUT_DIR/workspace/results/." "$OUTPUT_DIR/results/"
fi