# Local CPU parser setup plan

## Goal
Create one minimal local CPU execution path per step 1 parser option, with:
- isolated virtualenv per option on macOS
- one setup entrypoint with a common section and per-option sections
- one minimal inference script per option
- outputs written into parser-specific directories under [results/step1-local-cpu](../results/step1-local-cpu)

## Workspace structure
- [setup_step1_cpu.sh](../setup_step1_cpu.sh) — common setup plus per-option setup sections
- [parsers/common/runner_utils.py](../parsers/common/runner_utils.py) — shared runner helpers
- [parsers/marker/run_infer.py](../parsers/marker/run_infer.py)
- [parsers/paddleocr/run_infer.py](../parsers/paddleocr/run_infer.py)
- [parsers/mineru/run_infer.py](../parsers/mineru/run_infer.py)
- [parsers/monkeyocr/run_infer.py](../parsers/monkeyocr/run_infer.py)
- [parsers/olmocr/run_infer.py](../parsers/olmocr/run_infer.py)
- [parsers/olmocr/Dockerfile](../parsers/olmocr/Dockerfile)
- [parsers/olmocr/remote_entrypoint.sh](../parsers/olmocr/remote_entrypoint.sh)
- [parsers/monkeyocr/model_configs.cpu.yaml](../parsers/monkeyocr/model_configs.cpu.yaml)

## Common setup section
The common section in [setup_step1_cpu.sh](../setup_step1_cpu.sh) does the following:
1. validates `python3`
2. creates shared directories:
   - `.venvs`
   - `model_assets`
   - `results/step1-local-cpu`
   - `vendor`
3. installs common macOS system tools through Homebrew when available:
   - `poppler`
   - `qpdf`
   - `ghostscript`

## Per-option setup sections
### Marker
- virtualenv: `.venvs/marker`
- install path: `pip install marker-pdf`
- prewarm strategy: call `create_model_dict()` to force model artifact download
- inference wrapper: [parsers/marker/run_infer.py](../parsers/marker/run_infer.py)
- execution mode: `TORCH_DEVICE=cpu`

### PaddleOCR PP-StructureV3
- virtualenv: `.venvs/paddleocr`
- install path:
  - `pip install paddlepaddle`
  - `pip install "paddleocr[doc-parser]"`
- prewarm strategy: instantiate `PPStructureV3(..., device="cpu")`
- inference wrapper: [parsers/paddleocr/run_infer.py](../parsers/paddleocr/run_infer.py)
- output expectation: per-page JSON/image artifacts plus combined markdown when available

### MinerU
- virtualenv: `.venvs/mineru`
- install path: `pip install "mineru[all]"`
- execution mode: CPU backend via `-b pipeline`
- inference wrapper: [parsers/mineru/run_infer.py](../parsers/mineru/run_infer.py)

### MonkeyOCR
- virtualenv: `.venvs/monkeyocr`
- source checkout: `vendor/MonkeyOCR`
- install path:
  - editable install from cloned repo
  - `torch`, `torchvision`, `torchaudio`
  - `paddlepaddle`
  - `paddlex[base]`
  - `huggingface_hub`, `modelscope`
- model download strategy: `tools/download_model.py -n MonkeyOCR-pro-1.2B`
- CPU config: [parsers/monkeyocr/model_configs.cpu.yaml](../parsers/monkeyocr/model_configs.cpu.yaml)
- inference wrapper: [parsers/monkeyocr/run_infer.py](../parsers/monkeyocr/run_infer.py)
- note: expected to be very slow on CPU

### OLMOCR
- virtualenv: `.venvs/olmocr`
- local wrapper path: stdlib-only local runner plus remote SSH orchestration
- remote execution host: `midin@gx10-4f0c.local`
- remote deployment mode: build and run a Docker image/container on the GB10 machine
- image build context files:
  - [parsers/olmocr/Dockerfile](../parsers/olmocr/Dockerfile)
  - [parsers/olmocr/remote_entrypoint.sh](../parsers/olmocr/remote_entrypoint.sh)
- inference wrapper: [parsers/olmocr/run_infer.py](../parsers/olmocr/run_infer.py)
- current status: viable through remote GPU-backed Docker execution over SSH

## Feasibility summary
| Option | Local macOS CPU plan | Status |
| --- | --- | --- |
| Marker | direct | viable |
| PaddleOCR PP-StructureV3 | direct | viable |
| MinerU | direct with `-b pipeline` | viable |
| MonkeyOCR | source install plus CPU config | experimental |
| OLMOCR | remote SSH + Docker on GB10 host | viable with remote host |

## Recommended execution order
1. Run [setup_step1_cpu.sh](../setup_step1_cpu.sh) for `marker`, `paddleocr`, `mineru` first.
2. Treat `monkeyocr` as a second wave because setup and CPU runtime are heavier.
3. Use `olmocr` through the remote GB10 host after running [setup_step1_cpu.sh](../setup_step1_cpu.sh) with the `olmocr` target.

## Example usage after setup
- Marker: `./.venvs/marker/bin/python parsers/marker/run_infer.py /path/to/file.pdf --output-dir results/step1-local-cpu/marker/sample`
- PaddleOCR: `./.venvs/paddleocr/bin/python parsers/paddleocr/run_infer.py /path/to/file.pdf --output-dir results/step1-local-cpu/paddleocr/sample`
- MinerU: `./.venvs/mineru/bin/python parsers/mineru/run_infer.py /path/to/file.pdf --output-dir results/step1-local-cpu/mineru/sample`
- MonkeyOCR: `./.venvs/monkeyocr/bin/python parsers/monkeyocr/run_infer.py /path/to/file.pdf --output-dir results/step1-local-cpu/monkeyocr/sample`
- OLMOCR: `./.venvs/olmocr/bin/python parsers/olmocr/run_infer.py /path/to/file.pdf --output-dir results/step1-local-cpu/olmocr/sample`

## Important constraint
- `olmocr` remains the exception to the pure local CPU execution pattern.
- The workspace now handles that exception by shipping jobs to the GB10 machine over SSH and executing them inside a dedicated Docker image/container.
