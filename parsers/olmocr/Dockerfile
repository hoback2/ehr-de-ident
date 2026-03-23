# ARM64-native Dockerfile for OLMOCR on NVIDIA GB10 (Grace Blackwell).
# The pre-built alleninstituteforai/olmocr image is amd64-only.
# Uses NVIDIA NGC PyTorch base which ships PyTorch+CUDA pre-built for ARM64
# (sbsa) and includes Python 3.12 (olmocr requires >=3.11).
#
# Requires:  NVIDIA Container Toolkit on the host
# Override tag with:  docker build --build-arg PYTORCH_TAG=25.02-py3 ...

ARG PYTORCH_TAG=25.01-py3
FROM nvcr.io/nvidia/pytorch:${PYTORCH_TAG}

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# ---- system packages needed by OLMOCR / poppler ----
RUN apt-get update && apt-get install -y --no-install-recommends \
      poppler-utils qpdf ghostscript \
    && rm -rf /var/lib/apt/lists/*

# ---- install OLMOCR (torch/CUDA already provided by the base image) ----
RUN pip install --no-cache-dir "olmocr[gpu]"

# ---- pre-download model weights into the image ----
ARG OLMOCR_MODEL=allenai/olmOCR-2-7B-1025-FP8
RUN python3 -c "\
from huggingface_hub import snapshot_download; \
snapshot_download('${OLMOCR_MODEL}')"

WORKDIR /workspace

COPY remote_entrypoint.sh /usr/local/bin/ehr-olmocr-entrypoint
RUN chmod +x /usr/local/bin/ehr-olmocr-entrypoint

ENTRYPOINT ["/usr/local/bin/ehr-olmocr-entrypoint"]