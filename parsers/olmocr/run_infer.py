from __future__ import annotations

import importlib.util
import shlex
import uuid
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
run_command_stream = runner_utils.run_command_stream
write_run_manifest = runner_utils.write_run_manifest


def main() -> int:
    default_output_dir = ROOT / "results/step1-local-cpu/olmocr"
    parser = build_parser("OLMOCR", default_output_dir)
    parser.add_argument("--ssh-host", default="midin@gx10-4f0c.local", help="Remote SSH host for OLMOCR")
    parser.add_argument("--remote-root", default="~/ehr-deid-olmocr", help="Remote root directory for jobs")
    parser.add_argument("--image", default="ehr-olmocr:latest", help="Remote docker image name")
    parser.add_argument("--keep-remote-job", action="store_true", help="Keep remote job artifacts after download")
    args = parser.parse_args()

    input_pdf, output_dir = resolve_io(args.input_pdf, args.output_dir, args.overwrite)

    print(f"[olmocr] Remote host: {args.ssh_host}", flush=True)
    print(f"[olmocr] Docker image: {args.image}", flush=True)
    print(f"[olmocr] Input PDF:   {input_pdf}", flush=True)
    print(f"[olmocr] Output dir:  {output_dir}", flush=True)
    print(flush=True)

    # Resolve ~ to the actual remote home directory so shlex.quote won't
    # prevent tilde expansion on the remote shell.
    remote_root = args.remote_root
    if remote_root.startswith("~"):
        print("[olmocr] Step 1/5: Resolving remote home directory …", flush=True)
        home_result = run_command(["ssh", args.ssh_host, "echo $HOME"])
        remote_home = home_result.stdout.strip()
        remote_root = remote_root.replace("~", remote_home, 1)

    job_id = f"olmocr_{uuid.uuid4().hex[:12]}"
    remote_job_root = f"{remote_root.rstrip('/')}/jobs/{job_id}"
    remote_input_dir = f"{remote_job_root}/input"
    remote_output_dir = f"{remote_job_root}/output"
    remote_pdf_path = f"{remote_input_dir}/{input_pdf.name}"
    quoted_remote_job_root = shlex.quote(remote_job_root)
    quoted_remote_input_dir = shlex.quote(remote_input_dir)
    quoted_remote_output_dir = shlex.quote(remote_output_dir)
    quoted_remote_pdf_path = shlex.quote(remote_pdf_path)

    print(f"[olmocr] Step 2/5: Creating remote job directory ({job_id}) …", flush=True)
    run_command([
        "ssh",
        args.ssh_host,
        f"mkdir -p {quoted_remote_input_dir} {quoted_remote_output_dir}",
    ])

    print(f"[olmocr] Step 3/5: Uploading PDF to remote …", flush=True)
    run_command([
        "scp",
        str(input_pdf),
        f"{args.ssh_host}:{remote_pdf_path}",
    ])

    print(f"[olmocr] Step 4/5: Running OLMOCR container on {args.ssh_host} …", flush=True)
    docker_cmd = (
        f"docker run --rm --gpus all "
        f"-v {quoted_remote_input_dir}:/input "
        f"-v {quoted_remote_output_dir}:/output "
        f"{shlex.quote(args.image)} /input/{shlex.quote(input_pdf.name)} /output"
    )
    result = run_command_stream([
        "ssh",
        args.ssh_host,
        docker_cmd,
    ], label="olmocr")

    print(f"[olmocr] Step 5/5: Downloading results …", flush=True)
    run_command([
        "scp",
        "-r",
        f"{args.ssh_host}:{remote_output_dir}/.",
        str(output_dir),
    ])

    primary_output = find_first(output_dir, "*.md")
    write_run_manifest(
        output_dir,
        tool="olmocr",
        input_pdf=input_pdf,
        extra={
            "execution": "remote_ssh_docker",
            "ssh_host": args.ssh_host,
            "remote_root": remote_root,
            "remote_job_root": remote_job_root,
            "docker_image": args.image,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "primary_output": str(primary_output) if primary_output else None,
        },
    )

    if not args.keep_remote_job:
        run_command([
            "ssh",
            args.ssh_host,
            f"rm -rf {quoted_remote_job_root}",
        ])

    print(flush=True)
    if primary_output:
        print(f"[olmocr] Done. Primary output: {primary_output}", flush=True)
    else:
        print("[olmocr] Done. (no markdown output found)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
