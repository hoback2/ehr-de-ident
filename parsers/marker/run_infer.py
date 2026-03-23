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
find_first = runner_utils.find_first
resolve_io = runner_utils.resolve_io
run_command = runner_utils.run_command
write_run_manifest = runner_utils.write_run_manifest


def main() -> int:
    default_output_dir = ROOT / "results/step1-local-cpu/marker"
    parser = build_parser("Marker", default_output_dir)
    parser.add_argument("--force-ocr", action="store_true", help="Force OCR on all pages")
    args = parser.parse_args()

    input_pdf, output_dir = resolve_io(args.input_pdf, args.output_dir, args.overwrite)

    command = [
        "marker_single",
        str(input_pdf),
        "--output_format",
        "json",
        "--output_dir",
        str(output_dir),
    ]
    if args.force_ocr:
        command.append("--force_ocr")

    result = run_command(command, env={"TORCH_DEVICE": "cpu"})
    primary_output = find_first(output_dir, "*.json")

    write_run_manifest(
        output_dir,
        tool="marker",
        input_pdf=input_pdf,
        command=command,
        extra={
            "device": "cpu",
            "stdout": result.stdout,
            "stderr": result.stderr,
            "primary_output": str(primary_output) if primary_output else None,
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
