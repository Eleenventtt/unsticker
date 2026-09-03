#!/bin/bash
# 快速部署脚本

set -e

echo "==================================="
echo "UNSTICKER Web 部署脚本"
echo "==================================="
echo ""

# 检查 Docker
if ! command -v docker &> /dev/null; then
    echo "❌ 未检测到 Docker，请先安装 Docker"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ 未检测到 Docker Compose，请先安装"
    exit 1
fi

echo "✅ Docker 环境检查通过"
echo ""

# 检查环境变量文件
if [ ! -f .env.production ]; then
    echo "⚠️  未找到 .env.production 文件"
    echo "是否从示例文件创建？(y/n)"
    read -r create_env

    if [ "$create_env" = "y" ]; then
        cp .env.example .env.production
        echo "✅ 已创建 .env.production 文件"
        echo "⚠️  请编辑 .env.production 文件，填入真实的 API 密钥"
        echo ""
        echo "按任意键继续..."
        read -r
    else
        echo "❌ 部署已取消"
        exit 1
    fi
fi

echo "正在构建 Docker 镜像..."
docker-compose build

echo ""
echo "正在启动服务..."
docker-compose up -d

echo ""
echo "==================================="
echo "✅ 部署成功！"
echo "==================================="
echo ""
echo "服务信息："
echo "  - 访问地址: http://localhost:8000"
echo "  - 健康检查: http://localhost:8000/health"
echo "  - API 文档: http://localhost:8000/docs"
echo ""
echo "常用命令："
echo "  - 查看日志: docker-compose logs -f"
echo "  - 停止服务: docker-compose down"
echo "  - 重启服务: docker-compose restart"
echo ""
echo "如需在公网访问，请配置防火墙和域名"
echo ""
