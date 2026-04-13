#!/usr/bin/env bash
#
# Build claw-code (https://github.com/ultraworkers/claw-code) in Docker
# targeting linux/arm64 and emit a release tarball.
#
# Usage:
#   ./scripts/build_claw_code_arm64.sh [--ref <git-ref>] [--out <dir>]
#
# Requirements:
#   - docker with buildx (>= 0.10)
#   - QEMU set up if building arm64 on a non-arm64 host:
#       docker run --privileged --rm tonistiigi/binfmt --install arm64

set -euo pipefail

REPO_URL="https://github.com/ultraworkers/claw-code.git"
GIT_REF="main"
OUT_DIR="$(pwd)/dist"
IMAGE_TAG="claw-code:arm64-build"
PLATFORM="linux/arm64"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ref) GIT_REF="$2"; shift 2 ;;
    --out) OUT_DIR="$2"; shift 2 ;;
    --tag) IMAGE_TAG="$2"; shift 2 ;;
    -h|--help)
      sed -n '2,14p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

mkdir -p "$OUT_DIR"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT

echo ">> Preparing build context in $WORK_DIR"
cat > "$WORK_DIR/Dockerfile" <<'DOCKERFILE'
# syntax=docker/dockerfile:1.6

FROM --platform=$BUILDPLATFORM rust:1-bookworm AS builder
ARG GIT_REF=main
ARG REPO_URL=https://github.com/ultraworkers/claw-code.git

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git libssl-dev pkg-config \
  && rm -rf /var/lib/apt/lists/*

ENV CARGO_TERM_COLOR=always
WORKDIR /workspace

RUN git clone --depth 1 --branch "${GIT_REF}" "${REPO_URL}" src \
 || (git clone "${REPO_URL}" src && cd src && git checkout "${GIT_REF}")

WORKDIR /workspace/src/rust
RUN --mount=type=cache,target=/usr/local/cargo/registry \
    --mount=type=cache,target=/workspace/src/rust/target \
    cargo build --workspace --release --locked \
 && mkdir -p /out \
 && find target/release -maxdepth 1 -type f -executable \
      ! -name '*.d' ! -name '*.rlib' ! -name '*.so' \
      -exec cp -v {} /out/ \;

FROM debian:bookworm-slim AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates libssl3 \
  && rm -rf /var/lib/apt/lists/*
COPY --from=builder /out/ /usr/local/bin/
ENTRYPOINT ["/usr/local/bin/claw"]

# "export" stage: copy the built binaries to a scratch image so we can
# `docker buildx build --output type=local` them out.
FROM scratch AS export
COPY --from=builder /out/ /
DOCKERFILE

echo ">> Ensuring buildx builder exists"
if ! docker buildx inspect claw-builder >/dev/null 2>&1; then
  docker buildx create --name claw-builder --use >/dev/null
else
  docker buildx use claw-builder >/dev/null
fi

echo ">> Building runtime image: $IMAGE_TAG ($PLATFORM, ref=$GIT_REF)"
docker buildx build \
  --platform "$PLATFORM" \
  --build-arg "GIT_REF=$GIT_REF" \
  --build-arg "REPO_URL=$REPO_URL" \
  --target runtime \
  --tag "$IMAGE_TAG" \
  --load \
  "$WORK_DIR"

echo ">> Exporting arm64 binaries to $OUT_DIR/bin"
rm -rf "$OUT_DIR/bin"
docker buildx build \
  --platform "$PLATFORM" \
  --build-arg "GIT_REF=$GIT_REF" \
  --build-arg "REPO_URL=$REPO_URL" \
  --target export \
  --output "type=local,dest=$OUT_DIR/bin" \
  "$WORK_DIR"

SHORT_REF="$(echo "$GIT_REF" | tr '/' '-' | cut -c1-20)"
TARBALL="$OUT_DIR/claw-code-${SHORT_REF}-linux-arm64.tar.gz"
echo ">> Packaging release tarball: $TARBALL"
tar -czf "$TARBALL" -C "$OUT_DIR/bin" .

(cd "$OUT_DIR" && shasum -a 256 "$(basename "$TARBALL")" > "${TARBALL}.sha256")

echo
echo "Done."
echo "  image:   $IMAGE_TAG  (platform $PLATFORM)"
echo "  bins:    $OUT_DIR/bin/"
echo "  tarball: $TARBALL"
echo "  sha256:  ${TARBALL}.sha256"
