#!/bin/bash
# 打包项目用于上传线上部署（排除 venv、.env、运行时 data 等）
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PROJECT_NAME="$(basename "$ROOT_DIR")"
VERSION="$(date +%Y%m%d-%H%M%S)"
DIST_DIR="${ROOT_DIR}/dist"
ARCHIVE_NAME="${PROJECT_NAME}-${VERSION}.tar.gz"
ARCHIVE_PATH="${DIST_DIR}/${ARCHIVE_NAME}"

mkdir -p "${DIST_DIR}"

cd "$(dirname "${ROOT_DIR}")"

tar czf "${ARCHIVE_PATH}" \
  --exclude="${PROJECT_NAME}/venv" \
  --exclude="${PROJECT_NAME}/.env" \
  --exclude="${PROJECT_NAME}/.git" \
  --exclude="${PROJECT_NAME}/__pycache__" \
  --exclude="${PROJECT_NAME}/*.pyc" \
  --exclude="${PROJECT_NAME}/.pytest_cache" \
  --exclude="${PROJECT_NAME}/.DS_Store" \
  --exclude="${PROJECT_NAME}/.codegraph" \
  --exclude="${PROJECT_NAME}/dist" \
  --exclude="${PROJECT_NAME}/data/chroma" \
  --exclude="${PROJECT_NAME}/data/*.db" \
  --exclude="${PROJECT_NAME}/data/*.db-wal" \
  --exclude="${PROJECT_NAME}/data/*.db-shm" \
  "${PROJECT_NAME}"

LATEST_LINK="${DIST_DIR}/${PROJECT_NAME}-latest.tar.gz"
ln -sfn "${ARCHIVE_NAME}" "${LATEST_LINK}"

echo "打包完成:"
echo "  ${ARCHIVE_PATH}"
echo "  ${LATEST_LINK} -> ${ARCHIVE_NAME}"
echo ""
echo "上传到服务器:"
echo "  scp ${ARCHIVE_PATH} nobd@test155:~/"
echo ""
echo "服务器解压部署:"
echo "  tar xzf ${ARCHIVE_NAME}"
echo "  cd ${PROJECT_NAME}"
echo "  cp .env.example .env && vim .env"
echo "  ./scripts/deploy.sh"
