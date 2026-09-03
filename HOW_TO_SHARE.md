# 🌐 如何让别人访问你的 UNSTICKER 服务

## 问题：localhost 只能自己访问

`localhost` 或 `127.0.0.1` 只能在你自己的电脑上访问。要让别人通过互联网访问，需要将服务部署到有**公网 IP** 的服务器上。

---

## 📊 三种方案对比

| 方案 | 成本 | 难度 | 适用场景 | 稳定性 |
|------|------|------|----------|--------|
| **云服务器** | ¥100/月 | ⭐⭐⭐ | 正式使用 | ⭐⭐⭐⭐⭐ |
| **PaaS 平台** | $0-20/月 | ⭐ | 快速上线 | ⭐⭐⭐⭐ |
| **内网穿透** | 免费 | ⭐ | 临时演示 | ⭐⭐ |

---

## 方案 1: 云服务器部署（推荐 ⭐）

### 步骤详解

#### 1. 购买云服务器

**国内推荐：**
- [阿里云 ECS](https://www.aliyun.com) - 新用户有优惠
- [腾讯云 CVM](https://cloud.tencent.com) - 学生优惠
- [华为云](https://www.huaweicloud.com)

**国外推荐：**
- [AWS EC2](https://aws.amazon.com) - 免费套餐 12 个月
- [DigitalOcean](https://www.digitalocean.com) - $5/月起
- [Vultr](https://www.vultr.com) - $5/月起

**配置建议：**
- CPU: 2 核
- 内存: 4GB
- 系统: Ubuntu 22.04 LTS
- 带宽: 5Mbps

#### 2. 获取公网 IP

购买后会自动分配，例如：`123.45.67.89`

#### 3. 上传代码

**方式 A: 使用 Git（推荐）**
```bash
# 先把代码推送到 GitHub
git push origin master

# 登录服务器
ssh root@123.45.67.89

# 克隆代码
cd /opt
git clone https://github.com/你的用户名/仓库名.git unsticker
cd unsticker
```

**方式 B: 直接上传**
```bash
# 从你的电脑上传
scp -r /Users/anthony/_sticker_jobs root@123.45.67.89:/opt/unsticker
```

#### 4. 安装 Docker（推荐）

```bash
# 登录服务器
ssh root@123.45.67.89

# 安装 Docker
curl -fsSL https://get.docker.com | sh
systemctl enable docker
systemctl start docker

# 安装 Docker Compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
```

#### 5. 部署应用

```bash
cd /opt/unsticker

# 配置环境变量
cp .env.example .env.production
vim .env.production  # 填入你的 API 密钥

# 一键部署
./deploy.sh
```

#### 6. 开放防火墙端口

**阿里云/腾讯云控制台：**
1. 进入"安全组"设置
2. 添加入站规则：
   - 端口：8000
   - 协议：TCP
   - 源地址：0.0.0.0/0

**服务器防火墙：**
```bash
# Ubuntu (ufw)
sudo ufw allow 8000
sudo ufw reload

# CentOS (firewalld)
sudo firewall-cmd --add-port=8000/tcp --permanent
sudo firewall-cmd --reload
```

#### 7. 访问

✅ **你和其他人都可以访问：**
```
http://123.45.67.89:8000
```

---

## 方案 2: 配置域名（更专业）

### 为什么要用域名？
- ✅ 好记：`unsticker.com` 比 `123.45.67.89:8000` 好记
- ✅ 专业：看起来更正式
- ✅ HTTPS：免费 SSL 证书

### 步骤

#### 1. 购买域名（约 ¥50/年）

- [阿里云万网](https://wanwang.aliyun.com)
- [腾讯云](https://dnspod.cloud.tencent.com)
- [GoDaddy](https://www.godaddy.com)
- [Namecheap](https://www.namecheap.com)

#### 2. 配置 DNS 解析

在域名控制台添加 A 记录：
```
主机记录: @
记录类型: A
记录值: 123.45.67.89
TTL: 600
```

#### 3. 配置 Nginx

```bash
# 登录服务器
ssh root@123.45.67.89

# 安装 Nginx
sudo apt update
sudo apt install nginx -y

# 复制配置
cd /opt/unsticker
sudo cp nginx.conf /etc/nginx/sites-available/unsticker

# 修改域名
sudo vim /etc/nginx/sites-available/unsticker
# 将 your-domain.com 改为你的域名

# 启用配置
sudo ln -s /etc/nginx/sites-available/unsticker /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

#### 4. 配置 HTTPS（免费）

```bash
# 安装 Certbot
sudo apt install certbot python3-certbot-nginx -y

# 自动配置 HTTPS
sudo certbot --nginx -d unsticker.com

# 自动续期
sudo certbot renew --dry-run
```

#### 5. 访问

✅ **安全的 HTTPS 访问：**
```
https://unsticker.com
```

---

## 方案 3: PaaS 平台（最简单）

### Railway (推荐新手)

1. **注册** [Railway.app](https://railway.app)
2. **连接 GitHub** 仓库
3. **添加环境变量** 在 Railway 控制台：
   ```
   OPENAI_API_KEY=你的密钥
   OPENAI_API_URL=https://api.openai.com/v1/images/edits
   ```
4. **自动部署** - Railway 会自动检测 Dockerfile
5. **获取 URL** - Railway 会生成：`your-app.railway.app`

### 其他 PaaS 平台

- **Render** - https://render.com
- **Fly.io** - https://fly.io
- **Heroku** - https://heroku.com (需付费)

---

## 方案 4: 内网穿透（临时演示）

### 适用场景
- ❌ 不适合正式使用
- ✅ 适合快速演示给朋友看
- ✅ 适合开发测试

### 使用 ngrok

#### 1. 安装 ngrok

```bash
# macOS
brew install ngrok

# 或下载
# https://ngrok.com/download
```

#### 2. 注册并获取 token

访问 https://dashboard.ngrok.com/get-started/your-authtoken

```bash
ngrok config add-authtoken YOUR_TOKEN
```

#### 3. 启动本地服务

```bash
python3 app/server_production.py
```

#### 4. 启动 ngrok

```bash
# 方式 A: 直接运行
ngrok http 8000

# 方式 B: 使用脚本
./ngrok_share.sh
```

#### 5. 分享 URL

ngrok 会生成临时 URL：
```
https://abc123.ngrok.io
```

分享这个 URL 给其他人即可访问。

⚠️ **注意：**
- 免费版 URL 每次都会改变
- 连接限制：40 个/分钟
- 不适合长期使用

---

## 🎯 推荐方案选择

### 个人学习/演示
→ **内网穿透（ngrok）** - 免费，5 分钟搞定

### 小型项目/创业
→ **Railway/Render** - 简单，$5-20/月

### 正式产品
→ **云服务器 + 域名 + HTTPS** - 专业，¥150/月

---

## 💰 成本对比

| 方案 | 服务器 | 域名 | 总计/月 |
|------|--------|------|---------|
| 内网穿透 | 免费 | - | ¥0 |
| Railway | $5-20 | 可选 ¥50/年 | ¥35-140 |
| 阿里云 | ¥100 | ¥50/年 | ¥104 |
| AWS | $15 | $12/年 | ¥110 |

API 调用费另算：
- OpenAI: $0.02/图
- 腾讯云: ¥0.10/图

---

## 🔒 安全建议

### 1. 不要暴露 .env 文件
```bash
# 确认已添加到 .gitignore
cat .gitignore | grep .env
```

### 2. 使用 HTTPS
```bash
# 免费 Let's Encrypt 证书
sudo certbot --nginx -d your-domain.com
```

### 3. 限制访问（可选）
如果只想让特定人访问，可以添加简单的密码保护：

在 `server_production.py` 中添加：
```python
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials

security = HTTPBasic()

def verify_auth(credentials: HTTPBasicCredentials = Depends(security)):
    if credentials.username != "admin" or credentials.password != "your-password":
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return credentials

@app.get("/", dependencies=[Depends(verify_auth)])
async def index():
    return FileResponse(APP_DIR / "index.html")
```

---

## 📞 需要帮助？

1. 云服务器购买不会操作 → 查看云服务商的新手教程
2. 部署出错 → 查看日志：`docker-compose logs -f`
3. 访问不了 → 检查防火墙端口是否开放
4. 其他问题 → 提 GitHub Issue

---

## ✅ 快速检查清单

- [ ] 选择部署方案
- [ ] 准备服务器/平台账号
- [ ] 配置 API 密钥
- [ ] 上传代码并部署
- [ ] 开放防火墙端口
- [ ] 测试访问
- [ ] （可选）配置域名
- [ ] （可选）配置 HTTPS
- [ ] 分享访问地址

---

**开始部署吧！🚀**
