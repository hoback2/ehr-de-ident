#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$ROOT_DIR/.venvs"
MODEL_ASSET_DIR="$ROOT_DIR/model_assets"
RESULTS_DIR="$ROOT_DIR/results/step1-local-cpu"
VENDOR_DIR="$ROOT_DIR/vendor"
PYTHON_BIN="${PYTHON_BIN:-python3}"
PREFETCH_PDF="${PREFETCH_PDF:-}"
OLMOCR_SSH_HOST="${OLMOCR_SSH_HOST:-midin@gx10-4f0c.local}"
OLMOCR_REMOTE_ROOT="${OLMOCR_REMOTE_ROOT:-~/ehr-deid-olmocr}"
OLMOCR_DOCKER_IMAGE="${OLMOCR_DOCKER_IMAGE:-ehr-olmocr:latest}"

usage() {
  cat <<EOF
Usage:
  ./setup_step1_cpu.sh all
  ./setup_step1_cpu.sh marker paddleocr mineru monkeyocr olmocr
  PREFETCH_PDF=/absolute/path/to/sample.pdf ./setup_step1_cpu.sh marker

Notes:
- Assumes macOS and Python virtualenv usage.
- Creates one isolated virtualenv per parser option.
- Keeps setup strictly separated by option.
- OLMOCR is configured as a remote SSH + Docker deployment on ${OLMOCR_SSH_HOST}.
EOF
}

log() {
  printf '[setup] %s\n' "$*"
}

ensure_command() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Missing required command: $cmd" >&2
    exit 1
  fi
}

ensure_brew_package() {
  local pkg="$1"
  if ! command -v brew >/dev/null 2>&1; then
    log "Homebrew not found. Skipping brew install for $pkg."
    return 0
  fi
  if brew list "$pkg" >/dev/null 2>&1; then
    return 0
  fi
  log "Installing brew package: $pkg"
  brew install "$pkg"
}

venv_python() {
  local name="$1"
  printf '%s/bin/python' "$VENV_DIR/$name"
}

create_venv() {
  local name="$1"
  if [[ ! -d "$VENV_DIR/$name" ]]; then
    log "Creating virtualenv: $name"
    "$PYTHON_BIN" -m venv "$VENV_DIR/$name"
  fi
  "$(venv_python "$name")" -m pip install --upgrade pip setuptools wheel
}

common_setup() {
  log "== Common setup =="
  ensure_command "$PYTHON_BIN"
  mkdir -p "$VENV_DIR" "$MODEL_ASSET_DIR" "$RESULTS_DIR" "$VENDOR_DIR"
  ensure_brew_package poppler
  ensure_brew_package qpdf
  ensure_brew_package ghostscript
}

remote_ssh() {
  ssh "$OLMOCR_SSH_HOST" "$@"
}

remote_scp() {
  scp "$@"
}

maybe_prefetch() {
  local env_name="$1"
  local runner_path="$2"
  local output_dir="$3"

  if [[ -z "$PREFETCH_PDF" ]]; then
    return 0
  fi
  log "Prefetching weights for $env_name using $PREFETCH_PDF"
  "$(venv_python "$env_name")" "$runner_path" "$PREFETCH_PDF" --output-dir "$output_dir" --overwrite || true
}

setup_marker() {
  log "== Marker setup =="
  create_venv marker
  "$(venv_python marker)" -m pip install marker-pdf
  "$(venv_python marker)" - <<'PY'
from marker.models import create_model_dict
create_model_dict()
print('Marker model artifacts ready')
PY
  maybe_prefetch marker "$ROOT_DIR/parsers/marker/run_infer.py" "$RESULTS_DIR/marker_prefetch"
}

setup_paddleocr() {
  log "== PaddleOCR PP-StructureV3 setup =="
  create_venv paddleocr
  "$(venv_python paddleocr)" -m pip install paddlepaddle "paddleocr[doc-parser]"
  "$(venv_python paddleocr)" - <<'PY'
from paddleocr import PPStructureV3
pipeline = PPStructureV3(
    text_detection_model_name='PP-OCRv5_server_det',
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
    device='cpu',
)
print(type(pipeline).__name__)
print('PaddleOCR PP-StructureV3 artifacts ready')
PY
  maybe_prefetch paddleocr "$ROOT_DIR/parsers/paddleocr/run_infer.py" "$RESULTS_DIR/paddleocr_prefetch"
}

setup_mineru() {
  log "== MinerU setup =="
  create_venv mineru
  "$(venv_python mineru)" -m pip install "mineru[all]"
  "$(venv_python mineru)" - <<'PY'
import importlib
importlib.import_module('magic_pdf')
print('MinerU import ready')
PY
  maybe_prefetch mineru "$ROOT_DIR/parsers/mineru/run_infer.py" "$RESULTS_DIR/mineru_prefetch"
}

setup_monkeyocr() {
  log "== MonkeyOCR setup =="
  create_venv monkeyocr
  if [[ ! -d "$VENDOR_DIR/MonkeyOCR/.git" ]]; then
    rm -rf "$VENDOR_DIR/MonkeyOCR"
    git clone --depth 1 https://github.com/Yuliang-Liu/MonkeyOCR.git "$VENDOR_DIR/MonkeyOCR"
  fi
  "$(venv_python monkeyocr)" -m pip install torch torchvision torchaudio
  "$(venv_python monkeyocr)" -m pip install paddlepaddle "paddlex[base]" huggingface_hub modelscope
  "$(venv_python monkeyocr)" -m pip install -e "$VENDOR_DIR/MonkeyOCR"
  mkdir -p "$MODEL_ASSET_DIR/monkeyocr"
  (
    cd "$VENDOR_DIR/MonkeyOCR"
    "$(venv_python monkeyocr)" tools/download_model.py -n MonkeyOCR-pro-1.2B
  )
  maybe_prefetch monkeyocr "$ROOT_DIR/parsers/monkeyocr/run_infer.py" "$RESULTS_DIR/monkeyocr_prefetch"
}

setup_olmocr() {
  log "== OLMOCR setup =="
  create_venv olmocr
  ensure_command ssh
  ensure_command scp
  remote_ssh "mkdir -p $OLMOCR_REMOTE_ROOT/build-context $OLMOCR_REMOTE_ROOT/jobs"
  remote_scp \
    "$ROOT_DIR/parsers/olmocr/Dockerfile" \
    "$ROOT_DIR/parsers/olmocr/remote_entrypoint.sh" \
    "$OLMOCR_SSH_HOST:$OLMOCR_REMOTE_ROOT/build-context/"
  remote_ssh "docker --version >/dev/null"
  remote_ssh "docker build -t $OLMOCR_DOCKER_IMAGE $OLMOCR_REMOTE_ROOT/build-context"
  cat <<EOF
OLMOCR remote image prepared on $OLMOCR_SSH_HOST.
Remote root: $OLMOCR_REMOTE_ROOT
Docker image: $OLMOCR_DOCKER_IMAGE
Use parsers/olmocr/run_infer.py to ship a PDF over SSH, run the container remotely, and pull outputs back.
EOF
}

main() {
  if [[ $# -lt 1 ]]; then
    usage
    exit 1
  fi

  common_setup

  for target in "$@"; do
    case "$target" in
      all)
        setup_marker
        setup_paddleocr
        setup_mineru
        setup_monkeyocr
        setup_olmocr
        ;;
      marker) setup_marker ;;
      paddleocr) setup_paddleocr ;;
      mineru) setup_mineru ;;
      monkeyocr) setup_monkeyocr ;;
      olmocr) setup_olmocr ;;
      -h|--help) usage ; exit 0 ;;
      *)
        echo "Unknown target: $target" >&2
        usage
        exit 1
        ;;
    esac
  done
}

main "$@"
