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
    default_output_dir = ROOT / "results/step1-local-cpu/monkeyocr"
    parser = build_parser("MonkeyOCR", default_output_dir)
    args = parser.parse_args()

    input_pdf, output_dir = resolve_io(args.input_pdf, args.output_dir, args.overwrite)

    repo_dir = ROOT / "vendor/MonkeyOCR"
    config_path = ROOT / "parsers/monkeyocr/model_configs.cpu.yaml"
    if not repo_dir.exists():
        raise FileNotFoundError(
            f"MonkeyOCR repository not found at {repo_dir}. Run setup_step1_cpu.sh monkeyocr first."
        )

    command = [
        sys.executable,
        "parse.py",
        str(input_pdf),
        "-o",
        str(output_dir),
        "-c",
        str(config_path),
    ]
    result = run_command(command, cwd=repo_dir)
    primary_output = find_first(output_dir, "*.md")

    write_run_manifest(
        output_dir,
        tool="monkeyocr",
        input_pdf=input_pdf,
        command=command,
        extra={
            "device": "cpu",
            "repo_dir": str(repo_dir),
            "config_path": str(config_path),
            "stdout": result.stdout,
            "stderr": result.stderr,
            "primary_output": str(primary_output) if primary_output else None,
            "note": "CPU mode is expected to be very slow for full PDFs.",
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
