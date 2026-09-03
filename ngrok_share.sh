#!/bin/bash
# 使用 ngrok 内网穿透 - 快速演示方案

echo "====================================="
echo "  UNSTICKER 临时公网访问（ngrok）"
echo "====================================="
echo ""

# 检查 ngrok
if ! command -v ngrok &> /dev/null; then
    echo "❌ 未安装 ngrok"
    echo ""
    echo "安装步骤："
    echo "1. 访问 https://ngrok.com/download"
    echo "2. 下载并安装 ngrok"
    echo "3. 注册账号获取 token"
    echo "4. 运行: ngrok config add-authtoken YOUR_TOKEN"
    echo ""
    exit 1
fi

echo "✅ ngrok 已安装"
echo ""
echo "请确保你的应用已在本地运行："
echo "  python3 app/server_production.py"
echo ""
echo "按回车键继续..."
read

echo ""
echo "正在启动 ngrok 隧道..."
echo ""
echo "⚠️  生成的 URL 会在下方显示，分享给其他人即可访问"
echo "⚠️  免费版 URL 每次启动都会改变"
echo "⚠️  按 Ctrl+C 停止"
echo ""

ngrok http 8000
