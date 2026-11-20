#!/bin/bash
set -euo pipefail
if [ "$#" != 2 ]; then
    echo "usage: scripts/build.sh LOCAL_INPUTS OUTPUT_DIR" >&2
    exit 2
fi
root=$(cd "$(dirname "$0")/.." && pwd)
inputs=$(cd "$1" && pwd)
mkdir -p "$2"
output=$(cd "$2" && pwd)
test -z "$(git -C "$root" status --porcelain)"
commit=$(git -C "$root" rev-parse HEAD)
: "${TOOLCHAIN_IMAGE:?Set TOOLCHAIN_IMAGE to the verified Linux arm64 kernel build container}"
docker run --rm --pull never --network none --platform linux/arm64 \
    -e "SOURCE_COMMIT=$commit" -e "JOBS=${JOBS:-6}" \
    -v "$root:/release:ro" -v "$inputs:/inputs:ro" -v "$output:/artifacts" \
    "$TOOLCHAIN_IMAGE" /release/scripts/build-in-container.sh
