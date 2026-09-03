# UNSTICKER Web 部署 - 快速开始

## 🚀 三种部署方式

### 1️⃣ Docker 一键部署（最简单）

```bash
# 1. 配置 API 密钥
cp .env.example .env.production
vim .env.production  # 填入你的密钥

# 2. 一键部署
./deploy.sh

# 3. 访问
# http://你的服务器IP:8000
```

### 2️⃣ 云服务器部署

```bash
# 连接到你的服务器
ssh user@your-server

# 克隆项目
git clone <your-repo> /opt/unsticker
cd /opt/unsticker

# 安装依赖
pip3 install -r requirements.txt

# 配置环境变量
cp .env.example .env.production
vim .env.production

# 安装 systemd 服务
sudo cp unsticker.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable unsticker
sudo systemctl start unsticker

# 安装 Nginx（可选）
sudo apt install nginx
sudo cp nginx.conf /etc/nginx/sites-available/unsticker
sudo ln -s /etc/nginx/sites-available/unsticker /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# 配置 HTTPS（推荐）
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

### 3️⃣ Railway/Vercel 等平台

1. 连接 GitHub 仓库
2. 在平台添加环境变量
3. 自动部署

---

## 📋 部署前检查清单

- [ ] 已准备好 OpenAI 或腾讯云 API 密钥
- [ ] 有公网 IP 或域名（如果需要公开访问）
- [ ] 服务器至少 2GB 内存
- [ ] 已安装 Docker（Docker 部署方式）
- [ ] 已开放 8000 端口（或自定义端口）

---

## 🔑 获取 API 密钥

### OpenAI
1. 访问 https://platform.openai.com/api-keys
2. 创建新的 API Key
3. 复制密钥到 `.env.production`

### 腾讯云
1. 访问 https://console.cloud.tencent.com/cam/capi
2. 获取 SecretId 和 SecretKey
3. 复制到 `.env.production`

---

## 🧪 本地测试

在部署到服务器前，建议先在本地测试：

```bash
# 使用生产配置本地测试
export $(cat .env.production | xargs)
python3 app/server_production.py

# 访问 http://localhost:8000
```

---

## 📊 监控和维护

### 查看服务状态
```bash
# Docker 方式
docker-compose ps
docker-compose logs -f

# Systemd 方式
sudo systemctl status unsticker
sudo journalctl -u unsticker -f
```

### 重启服务
```bash
# Docker 方式
docker-compose restart

# Systemd 方式
sudo systemctl restart unsticker
```

### 更新代码
```bash
# Docker 方式
git pull
docker-compose build
docker-compose up -d

# Systemd 方式
git pull
sudo systemctl restart unsticker
```

---

## ⚠️ 常见问题

### 端口被占用
```bash
# 修改 docker-compose.yml 中的端口映射
ports:
  - "8080:8000"  # 改为 8080
```

### 内存不足
```bash
# 减少并发数量
# 编辑 scripts 中的 --concurrency 参数
```

### 图片上传失败
```bash
# 检查 Nginx 配置的 client_max_body_size
# 或在 server_production.py 中调整上传限制
```

---

## 💰 成本估算

### 服务器（按月）
- 阿里云 2核4G: ¥100
- 腾讯云 2核4G: ¥95
- AWS t3.small: $15
- Railway 免费额度: $5

### API 调用
- OpenAI: $0.02/图
- 腾讯云: ¥0.10/图

处理 1000 张图片：
- OpenAI: $20
- 腾讯云: ¥100

---

## 📞 获取帮助

- 查看详细文档: [DEPLOYMENT.md](./DEPLOYMENT.md)
- 提交问题: GitHub Issues
- 查看示例: [README.md](./README.md)
