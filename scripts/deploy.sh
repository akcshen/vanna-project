#!/bin/bash
# 线上服务器解压后执行：构建镜像并启动容器
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT_DIR}"

BASE_IMAGE="${BASE_IMAGE:-python:3.10-slim}"

if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "已生成 .env，请先编辑配置后再执行本脚本"
  exit 1
fi

mkdir -p data

if ! command -v docker-compose >/dev/null 2>&1; then
  echo "未找到 docker-compose，请先安装"
  exit 1
fi

if ! docker image inspect "${BASE_IMAGE}" >/dev/null 2>&1; then
  echo "错误: 本地不存在基础镜像 ${BASE_IMAGE}"
  echo ""
  echo "test155 无法直连 Docker Hub，需先在能上网的机器导出镜像再传过来："
  echo ""
  echo "  # 本机 Mac（可开代理）"
  echo "  export HTTP_PROXY=http://192.200.125.170:10808"
  echo "  export HTTPS_PROXY=http://192.200.125.170:10808"
  echo "  ./scripts/export-base-image.sh"
  echo "  scp dist/python-3.10-slim.tar.gz nobd@test155:~/"
  echo ""
  echo "  # test155"
  echo "  ./scripts/load-base-image.sh ~/python-3.10-slim.tar.gz"
  echo "  ./scripts/deploy.sh"
  exit 1
fi

# 构建时 apt/pip 走代理（仅当前终端 export 生效）
# export HTTP_PROXY=http://192.200.125.170:10808
# export HTTPS_PROXY=http://192.200.125.170:10808

echo ">>> 使用本地镜像 ${BASE_IMAGE}，开始 docker-compose build"
docker-compose build

echo ">>> docker-compose up -d"
docker-compose up -d

echo ""
echo "部署完成。首次请训练向量库:"
echo "  docker-compose exec vanna-api python scripts/train.py"
echo ""
echo "验证:"
echo "  curl http://127.0.0.1:8080/health"
echo "  docker-compose logs -f vanna-api"
