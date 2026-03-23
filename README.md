# EHR De-Identification Evaluation Workspace

This workspace is organized for stepwise evaluation of self-hosted open source tooling for medical document processing.

## Project goal
Build a reliable pipeline for medical record de-identification.

## Step 1: document parsing and OCR
Evaluate self-hosted parsers/OCR systems on difficult EHR inputs:
- PDFs with medical information
- graphs and diagrams
- embedded images
- messy low-resolution fax scans
- handwriting
- tables, forms, and bounding boxes

Step 1 candidates:
- OLMOCR
- Marker (Surya OCR)
- MonkeyOCR
- PaddleOCR (PP-StructureV3)
- MinerU

## Step 2: de-identification
Evaluate de-identification options on outputs from the strongest step 1 candidates.

Step 2 candidates:
- `philter` for clinical PHI text de-identification
- `presidio image redactor` for image-based redaction

## Proposed workspace layout
- [docs/evaluation-plan.md](docs/evaluation-plan.md) — detailed plan, scoring, and milestones
- [docs/local-cpu-parser-setup-plan.md](docs/local-cpu-parser-setup-plan.md) — local CPU setup and inference plan for step 1 parser options
- [docs/github-private-repo-publish.md](docs/github-private-repo-publish.md) — instructions for publishing this workspace to the private GitHub repo `midinas/public-ehr-deid-asset-prep` with Git LFS for large files
- [samples/raw](samples/raw) — original evaluation inputs kept local only
- [samples/manifests](samples/manifests) — sample inventory and metadata
- [samples/processed](samples/processed) — normalized copies or derived artifacts
- [evaluations/step1-parsers](evaluations/step1-parsers) — parser-specific notes and scorecards
- [evaluations/step2-deid](evaluations/step2-deid) — de-identification notes and scorecards
- [results](results) — aggregate rankings, charts, and final recommendations
- [tests](tests) — future evaluation or regression tests
- [debug](debug) — helper inspection scripts

## Local CPU parser scaffolding
- [setup_step1_cpu.sh](setup_step1_cpu.sh) provides one common setup section and separate per-parser setup sections.
- Minimal inference wrappers live under [parsers](parsers).
- Current local CPU feasibility is strongest for Marker, PaddleOCR PP-StructureV3, and MinerU.
- MonkeyOCR is scaffolded as an experimental CPU path.
- OLMOCR is routed to a local GB10 machine over SSH and executed there in a dedicated Docker image/container.

## Operating principles
- Keep all medical documents and outputs self-hosted and local.
- Avoid cloud APIs for documents containing PHI.
- Track provenance for every sample and every generated artifact.
- Score both extraction quality and operational fit: speed, resource use, install complexity, and reproducibility.
- Preserve page-level structure when possible because step 2 redaction depends on accurate text-to-image alignment.

## Recommended execution order
1. Build a representative evaluation sample set.
2. Run all step 1 parsers on the same corpus.
3. Score OCR/text, layout, tables, handwriting tolerance, and operational characteristics.
4. Shortlist the best 1-2 step 1 systems.
5. Run step 2 de-identification on shortlisted outputs and source images.
6. Select a combined pipeline for implementation.
