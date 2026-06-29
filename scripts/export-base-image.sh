#!/bin/bash
# 在能访问 Docker Hub 的机器上执行（本机 Mac），导出基础镜像供线上 load
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
IMAGE="${BASE_IMAGE:-python:3.10-slim-bookworm}"
DIST_DIR="${ROOT_DIR}/dist"
ARCHIVE="${DIST_DIR}/python-3.10-slim.tar.gz"

mkdir -p "${DIST_DIR}"

echo ">>> 拉取基础镜像: ${IMAGE}"
echo "    若网络慢，可先 export 代理，例如："
echo "    export HTTP_PROXY=http://192.200.125.170:10808"
echo "    export HTTPS_PROXY=http://192.200.125.170:10808"
echo ""

docker pull "${IMAGE}"

echo ">>> 导出到 ${ARCHIVE}"
docker save "${IMAGE}" | gzip > "${ARCHIVE}"

echo ""
echo "完成。上传到服务器并导入："
echo "  scp ${ARCHIVE} nobd@test155:~/"
echo "  ssh nobd@test155 './vanna-project/scripts/load-base-image.sh ~/python-3.10-slim.tar.gz'"
