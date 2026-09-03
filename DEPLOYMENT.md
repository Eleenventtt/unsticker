# UNSTICKER Web 部署指南

## 项目概述

UNSTICKER 是一个基于 AI 的贴纸移除工具，支持 OpenAI 和腾讯云两种图像修复引擎。

## 部署方案

### 方案一：Docker 部署（推荐）

#### 前置要求
- 安装 Docker 和 Docker Compose
- 有公网 IP 或域名的服务器

#### 步骤

1. **准备环境变量**

创建 `.env.production` 文件：

```bash
OPENAI_API_KEY=你的_OpenAI_API_密钥
OPENAI_API_URL=https://api.openai.com/v1/images/edits
TENCENTCLOUD_SECRET_ID=你的腾讯云SecretId
TENCENTCLOUD_SECRET_KEY=你的腾讯云SecretKey
TENCENTCLOUD_REGION=ap-guangzhou
```

2. **构建并启动**

```bash
# 构建镜像
docker-compose build

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f
```

3. **访问服务**

浏览器打开：`http://你的服务器IP:8000`

#### 停止服务

```bash
docker-compose down
```

---

### 方案二：云服务器直接部署

#### 适用场景
- 阿里云 ECS
- 腾讯云 CVM
- AWS EC2
- 其他 Linux 服务器

#### 步骤

1. **安装依赖**

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3 python3-pip git -y

# CentOS/RHEL
sudo yum install python3 python3-pip git -y
```

2. **克隆项目**

```bash
cd /opt
git clone <你的仓库地址> unsticker
cd unsticker
```

3. **安装 Python 依赖**

```bash
pip3 install -r requirements.txt
```

4. **配置环境变量**

```bash
export OPENAI_API_KEY="你的密钥"
export OPENAI_API_URL="https://api.openai.com/v1/images/edits"
export TENCENTCLOUD_SECRET_ID="你的ID"
export TENCENTCLOUD_SECRET_KEY="你的密钥"
export TENCENTCLOUD_REGION="ap-guangzhou"
```

或者创建 `.env.production` 文件并使用：

```bash
source .env.production
```

5. **使用 systemd 创建服务**

创建 `/etc/systemd/system/unsticker.service`：

```ini
[Unit]
Description=UNSTICKER Service
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/unsticker
EnvironmentFile=/opt/unsticker/.env.production
ExecStart=/usr/bin/python3 -m uvicorn app.server_production:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

6. **启动服务**

```bash
sudo systemctl daemon-reload
sudo systemctl enable unsticker
sudo systemctl start unsticker
sudo systemctl status unsticker
```

7. **配置 Nginx 反向代理（可选）**

安装 Nginx：

```bash
sudo apt install nginx -y
```

创建 Nginx 配置 `/etc/nginx/sites-available/unsticker`：

```nginx
server {
    listen 80;
    server_name your-domain.com;

    client_max_body_size 100M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

启用配置：

```bash
sudo ln -s /etc/nginx/sites-available/unsticker /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

8. **配置 HTTPS（推荐）**

使用 Let's Encrypt：

```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d your-domain.com
```

---

### 方案三：Vercel/Railway 等 PaaS 平台

#### Railway 部署

1. 在 Railway 官网创建新项目
2. 连接 GitHub 仓库
3. 添加环境变量（在 Railway 控制台）
4. Railway 会自动检测 Dockerfile 并部署

#### 注意事项
- PaaS 平台通常有文件上传大小限制
- 需要配置持久化存储卷

---

## 安全建议

### 1. API 密钥保护

❌ **不要**将 API 密钥提交到 Git 仓库

✅ **使用环境变量或密钥管理服务**

### 2. 文件上传限制

在 `server_production.py` 中添加文件大小限制：

```python
from fastapi import UploadFile, File, HTTPException

@app.post("/api/upload")
async def upload_files(files: list[UploadFile] = File(...)) -> JSONResponse:
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    
    for file in files:
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail="File too large")
        # ... 其余代码
```

### 3. CORS 配置

生产环境应限制允许的域名：

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-domain.com"],  # 指定域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 4. 身份验证（可选）

如果需要限制访问，可以添加简单的 API Key 验证：

```python
from fastapi import Header, HTTPException

API_KEY = os.getenv("API_KEY", "your-secret-key")

async def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")

@app.post("/api/upload", dependencies=[Depends(verify_api_key)])
async def upload_files(...):
    # ...
```

---

## 性能优化

### 1. 并发处理

调整 uvicorn 的 worker 数量：

```bash
uvicorn app.server_production:app --host 0.0.0.0 --port 8000 --workers 4
```

### 2. 使用 Redis 缓存

可以添加 Redis 来缓存处理结果：

```bash
pip install redis
```

### 3. CDN 加速

将处理后的图片上传到 CDN（如阿里云 OSS、腾讯云 COS）

---

## 监控和日志

### 查看日志

Docker 方式：
```bash
docker-compose logs -f unsticker
```

Systemd 方式：
```bash
sudo journalctl -u unsticker -f
```

### 健康检查

访问 `http://your-server:8000/health` 检查服务状态

---

## 故障排查

### 1. 端口被占用

```bash
# 查看端口占用
sudo lsof -i :8000

# 更换端口
docker-compose up -d -e PORT=8080
```

### 2. 权限问题

```bash
# 确保数据目录有写权限
sudo chown -R www-data:www-data /opt/unsticker/data
```

### 3. Python 依赖问题

```bash
# 重新安装依赖
pip3 install -r requirements.txt --force-reinstall
```

---

## 成本估算

### 服务器成本
- **阿里云 ECS**: 2核4G 约 ¥100/月
- **腾讯云 CVM**: 2核4G 约 ¥95/月
- **Railway**: 免费套餐 $5/月，按量付费

### API 调用成本
- **OpenAI Image Edit**: 约 $0.02/张
- **腾讯云图像修复**: 约 ¥0.10/张

---

## 联系和支持

如有问题，请提交 Issue 或联系开发者。
