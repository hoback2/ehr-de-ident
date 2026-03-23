from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNNER_UTILS_PATH = ROOT / "parsers/common/runner_utils.py"
spec = importlib.util.spec_from_file_location("runner_utils", RUNNER_UTILS_PATH)
if spec is None or spec.loader is None:
    raise ImportError(f"Unable to load runner utilities from {RUNNER_UTILS_PATH}")
runner_utils = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner_utils)

build_parser = runner_utils.build_parser
resolve_io = runner_utils.resolve_io
write_json = runner_utils.write_json
write_run_manifest = runner_utils.write_run_manifest


def main() -> int:
    default_output_dir = ROOT / "results/step1-local-cpu/paddleocr"
    parser = build_parser("PaddleOCR PP-StructureV3", default_output_dir)
    args = parser.parse_args()

    input_pdf, output_dir = resolve_io(args.input_pdf, args.output_dir, args.overwrite)

    from paddleocr import PPStructureV3

    pipeline = PPStructureV3(
        text_detection_model_name="PP-OCRv5_server_det",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        device="cpu",
    )
    results = list(pipeline.predict(str(input_pdf)))

    combined_markdown_parts: list[str] = []
    page_summaries: list[dict[str, object]] = []

    for page_index, result in enumerate(results, start=1):
        page_dir = output_dir / f"page_{page_index:03d}"
        page_dir.mkdir(parents=True, exist_ok=True)

        markdown_text = ""
        markdown_payload = getattr(result, "markdown", None)
        if isinstance(markdown_payload, dict):
            markdown_text = markdown_payload.get("markdown_texts", "") or ""
        if markdown_text:
            (page_dir / "page.md").write_text(markdown_text, encoding="utf-8")
            combined_markdown_parts.append(f"<!-- page {page_index} -->\n{markdown_text}\n")

        if hasattr(result, "save_to_json"):
            result.save_to_json(str(page_dir))
        if hasattr(result, "save_to_img"):
            result.save_to_img(str(page_dir))

        summary = {
            "page": page_index,
            "page_dir": str(page_dir),
            "markdown_file": str(page_dir / "page.md") if markdown_text else None,
        }
        page_summaries.append(summary)

    combined_markdown = "\n".join(combined_markdown_parts).strip()
    if combined_markdown:
        (output_dir / "document.md").write_text(combined_markdown + "\n", encoding="utf-8")

    write_json(output_dir / "pages.json", page_summaries)
    write_run_manifest(
        output_dir,
        tool="paddleocr_pp_structurev3",
        input_pdf=input_pdf,
        extra={
            "device": "cpu",
            "page_count": len(page_summaries),
            "primary_output": str(output_dir / "document.md") if combined_markdown else None,
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
