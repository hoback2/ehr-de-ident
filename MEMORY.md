# Memory

## 2026-03-19
- Workspace initialized for a medical EHR de-identification evaluation project.
- Planning artifacts created for two-step evaluation:
  - Step 1: self-hosted document parsing and OCR
  - Step 2: de-identification and image redaction
- Core workspace directories created: `docs`, `samples`, `evaluations`, `results`, `tests`, `debug`.
- Key planning files created:
  - `README.md`
  - `docs/evaluation-plan.md`
  - sample inventory template
  - step 1 and step 2 scorecard templates
- Follow AGENTS.md conventions:
  - tests go in `tests/`
  - helper scripts prefixed with `_` go in `tests/` or `debug/`
- Added local CPU parser setup scaffolding for step 1 evaluation:
  - shared setup entrypoint: `setup_step1_cpu.sh`
  - shared parser helpers under `parsers/common/`
  - minimal parser wrappers for Marker, PaddleOCR PP-StructureV3, MinerU, MonkeyOCR, and OLMOCR
  - MonkeyOCR CPU config template in `parsers/monkeyocr/model_configs.cpu.yaml`
- Added implementation planning doc for local CPU parser setup in `docs/local-cpu-parser-setup-plan.md`.
- Reworked OLMOCR setup from a local CPU blocker into a remote SSH + Docker path targeting `midin@gx10-4f0c.local`.
- Added OLMOCR remote deployment assets:
  - `parsers/olmocr/Dockerfile`
  - `parsers/olmocr/remote_entrypoint.sh`
  - updated `parsers/olmocr/run_infer.py` to ship PDFs over SSH, run the container remotely, and pull outputs back.
- Added `OPTIONS.md` with a comparative options table for step 1 and step 2 frameworks/models using the requested columns.

## 2026-03-20
- Added [docs/github-private-repo-publish.md](docs/github-private-repo-publish.md) with step-by-step instructions to create the private GitHub repo `midinas/public-ehr-deid-asset-prep`, stage the workspace, and use Git LFS for large files from the first commit.
- Updated [README.md](README.md) to link the new private-repo publishing instructions.
- Fixed OLMOCR Dockerfile ARM64 incompatibility: replaced pre-built `alleninstituteforai/olmocr:latest-with-model` (amd64-only) with an ARM-native build from `nvidia/cuda:12.8.0-devel-ubuntu22.04` that installs OLMOCR via pip and bakes in the model weights. The GB10 machine (NVIDIA Grace Blackwell) is ARM64 and needs CUDA ≥ 12.8 for sm_100 (Blackwell) support. The CUDA version is overridable via `--build-arg CUDA_VERSION=...`.
- Switched OLMOCR Dockerfile base to `nvcr.io/nvidia/pytorch:25.01-py3` (NGC PyTorch): PyPI torch wheels for aarch64 are CPU-only; NGC base ships PyTorch+CUDA pre-built for ARM64 (sbsa) plus Python 3.12 (satisfying olmocr's >=3.11 requirement). Eliminates deadsnakes PPA workaround.
- Fixed tilde expansion bug in `parsers/olmocr/run_infer.py`: `shlex.quote()` was quoting `~` in remote paths, preventing shell expansion. Now resolves `~` → `$HOME` via SSH before constructing paths.

## 2026-03-22
- Created `samples/create_fax_sample.py` — a Python CLI script that takes an EHR PDF and a DICOM screenshot, concatenates them, and produces realistic fax-degraded PDFs.
  - All tuneable knobs (probabilities, ranges, header text, colours, …) are centralised in a `FaxConfig` dataclass; overridable via `--config <path.json>` and inspectable via `--dump-config`.
  - `--count N` generates N variant PDFs per run, each with an auto-incremented seed (`seed_step` apart, default 1000).
  - CT / image pages use a gentler degradation profile: no binarisation, higher JPEG quality (45-65), no vertical pixel smear, less noise — so the DICOM screenshot stays recognisable.
  - Text-page degradation chain: fax header (+ optional re-fax header), rubber-stamp / date-stamp overlays, punch holes & staple shadows, skew + perspective warp, 200×100 DPI non-square-pixel sim, Otsu binarisation, JPEG artefact pass, salt-and-pepper noise.
  - Deterministic via `--seed`; dependencies: `opencv-python-headless`, `numpy`, `Pillow`, `PyMuPDF` (in `.venv`).

## 2026-03-23
- Improved `parsers/common/runner_utils.py`:
  - `run_command()` now prints captured stdout/stderr on failure before raising, so Docker/SSH errors are visible.
  - Added `run_command_stream()` for long-running tasks — streams stdout+stderr line-by-line in real time with an optional `[label]` prefix.
- Improved `parsers/olmocr/run_infer.py` logging:
  - Prints run config header (remote host, image, input, output) at start.
  - Labels each phase with numbered steps (1/5 through 5/5).
  - Docker inference step now uses `run_command_stream` for real-time output.
  - Prints primary output path on completion.
