FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY app/ ./app/
COPY scripts/ ./scripts/

# 创建必要的目录
RUN mkdir -p /app/data/uploads /app/data/outputs

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV PYTHON_BIN=python3

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# 启动应用（Railway 会通过 PORT 环境变量指定端口）
CMD python3 -m uvicorn app.server_production:app --host 0.0.0.0 --port ${PORT:-8000}
