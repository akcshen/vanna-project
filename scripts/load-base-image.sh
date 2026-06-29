#!/bin/bash
# 在线上服务器执行，导入本机 export 的基础镜像（无需访问 Docker Hub）
set -euo pipefail

ARCHIVE="${1:-}"

if [ -z "${ARCHIVE}" ] || [ ! -f "${ARCHIVE}" ]; then
  echo "用法: $0 <python-3.10-slim.tar.gz>"
  echo "示例: $0 ~/python-3.10-slim.tar.gz"
  exit 1
fi

echo ">>> 导入基础镜像: ${ARCHIVE}"
gunzip -c "${ARCHIVE}" | docker load

echo ""
echo ">>> 已导入镜像:"
docker images python

echo ""
echo "现在可以构建项目:"
echo "  cd vanna-project"
echo "  export HTTP_PROXY=http://192.200.125.170:10808"
echo "  export HTTPS_PROXY=http://192.200.125.170:10808"
echo "  ./scripts/deploy.sh"
