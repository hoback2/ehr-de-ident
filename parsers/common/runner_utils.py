from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Mapping, Sequence


def build_parser(tool_name: str, default_output_dir: Path) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=f"Run {tool_name} on a single PDF document.",
    )
    parser.add_argument("input_pdf", help="Path to the input PDF file")
    parser.add_argument(
        "--output-dir",
        default=str(default_output_dir),
        help="Directory where outputs will be written",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow writing into an existing non-empty output directory",
    )
    return parser


def resolve_io(input_pdf: str, output_dir: str, overwrite: bool) -> tuple[Path, Path]:
    pdf_path = Path(input_pdf).expanduser().resolve()
    if not pdf_path.exists():
        raise FileNotFoundError(f"Input PDF not found: {pdf_path}")
    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError(f"Expected a PDF input, got: {pdf_path}")

    output_path = Path(output_dir).expanduser().resolve()
    output_path.mkdir(parents=True, exist_ok=True)

    if any(output_path.iterdir()) and not overwrite:
        raise FileExistsError(
            f"Output directory is not empty: {output_path}. Use --overwrite to reuse it."
        )

    return pdf_path, output_path


def run_command(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a command, capture output, and raise on failure with visible logs."""
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)

    print("$", " ".join(shlex.quote(part) for part in command), flush=True)
    result = subprocess.run(
        list(command),
        cwd=str(cwd) if cwd else None,
        env=merged_env,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        # Print captured output so the user can see what went wrong
        if result.stdout:
            print("--- stdout ---", flush=True)
            print(result.stdout.rstrip(), flush=True)
        if result.stderr:
            print("--- stderr ---", flush=True)
            print(result.stderr.rstrip(), flush=True)
        print(f"Command exited with code {result.returncode}", flush=True)
        raise subprocess.CalledProcessError(
            result.returncode, result.args, result.stdout, result.stderr,
        )
    return result


def run_command_stream(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    label: str = "",
) -> subprocess.CompletedProcess[str]:
    """Run a command with real-time stdout/stderr streaming (for long tasks)."""
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)

    tag = f"[{label}] " if label else ""
    print(f"{tag}$", " ".join(shlex.quote(part) for part in command), flush=True)
    proc = subprocess.Popen(
        list(command),
        cwd=str(cwd) if cwd else None,
        env=merged_env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    lines: list[str] = []
    assert proc.stdout is not None
    for line in proc.stdout:
        stripped = line.rstrip("\n")
        print(f"{tag}{stripped}", flush=True)
        lines.append(stripped)
    proc.wait()
    combined = "\n".join(lines)
    if proc.returncode != 0:
        print(f"{tag}Command exited with code {proc.returncode}", flush=True)
        raise subprocess.CalledProcessError(
            proc.returncode, proc.args, combined, "",
        )
    return subprocess.CompletedProcess(proc.args, proc.returncode, combined, "")


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_run_manifest(
    output_dir: Path,
    *,
    tool: str,
    input_pdf: Path,
    command: Sequence[str] | None = None,
    extra: Mapping[str, object] | None = None,
) -> None:
    manifest = {
        "tool": tool,
        "input_pdf": str(input_pdf),
        "timestamp_epoch": time.time(),
        "python": sys.executable,
    }
    if command is not None:
        manifest["command"] = list(command)
    if extra:
        manifest.update(extra)
    write_json(output_dir / "run_manifest.json", manifest)


def find_first(root: Path, pattern: str) -> Path | None:
    matches = sorted(root.rglob(pattern))
    return matches[0] if matches else None
