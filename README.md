# UNSTICKER - 贴纸移除工具

一个基于 AI 的智能贴纸移除工具，支持批量处理图片，去除价格标签等贴纸。

## 功能特性

- 🎯 智能识别并移除图片中的贴纸
- 🚀 支持批量处理
- 🔄 支持两种 AI 引擎：OpenAI 和腾讯云
- 🖥️ 美观的 Web 界面
- 📊 实时处理进度显示
- 🔍 结果预览和对比

## 本地开发

### 快速开始

1. 克隆项目
```bash
git clone <repository-url>
cd _sticker_jobs
```

2. 安装依赖
```bash
pip install -r requirements.txt
```

3. 配置环境变量
```bash
cp .env.example .env
# 编辑 .env 文件，填入你的 API 密钥
```

4. 启动服务
```bash
cd app
python3 server.py
```

5. 访问 http://localhost:7788

## Web 部署

详细的 Web 部署指南请查看 [DEPLOYMENT.md](./DEPLOYMENT.md)

### 快速部署（Docker）

```bash
# 1. 配置环境变量
cp .env.example .env.production
# 编辑 .env.production 填入真实密钥

# 2. 启动服务
docker-compose up -d

# 3. 访问服务
# http://your-server-ip:8000
```

## 技术栈

- **后端**: Python + FastAPI
- **前端**: 原生 HTML/CSS/JavaScript
- **AI 引擎**: OpenAI Image Edit API / 腾讯云图像修复
- **部署**: Docker / Docker Compose

## API 文档

启动服务后访问：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 主要接口

- `POST /api/upload` - 上传图片
- `POST /api/prepare` - 准备处理任务
- `POST /api/repair` - 执行图像修复
- `GET /api/results` - 获取处理结果
- `GET /api/config` - 获取配置信息

## 环境变量

| 变量名 | 说明 | 必需 |
|--------|------|------|
| `OPENAI_API_KEY` | OpenAI API 密钥 | 使用 OpenAI 时必需 |
| `OPENAI_API_URL` | OpenAI API 地址 | 可选 |
| `TENCENTCLOUD_SECRET_ID` | 腾讯云密钥 ID | 使用腾讯云时必需 |
| `TENCENTCLOUD_SECRET_KEY` | 腾讯云密钥 Key | 使用腾讯云时必需 |
| `TENCENTCLOUD_REGION` | 腾讯云地域 | 可选，默认 ap-guangzhou |

## 目录结构

```
_sticker_jobs/
├── app/
│   ├── index.html              # Web 界面
│   ├── server.py               # 本地开发服务器
│   └── server_production.py    # 生产环境服务器
├── scripts/                    # 处理脚本
│   ├── remove_sticker_prepare_price_tag.py
│   ├── repair_with_openai.py
│   └── repair_with_tencent.py
├── data/                       # 数据目录（自动创建）
│   ├── uploads/               # 上传的图片
│   └── outputs/               # 处理结果
├── Dockerfile                  # Docker 镜像配置
├── docker-compose.yml         # Docker Compose 配置
├── requirements.txt           # Python 依赖
├── .env.example              # 环境变量示例
├── DEPLOYMENT.md             # 部署指南
└── README.md                 # 本文件
```

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！

## 支持

如有问题，请提交 Issue 或联系开发者。
