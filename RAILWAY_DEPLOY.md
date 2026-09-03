# 🚀 Railway 快速部署指南（5分钟）

最简单的部署方式，适合快速给朋友演示使用。

## 📋 前提条件

- ✅ GitHub 账号
- ✅ OpenAI 或腾讯云 API 密钥

## 🎯 部署步骤

### 步骤 1: 推送代码到 GitHub（如果还没有）

```bash
# 1. 在 GitHub 创建新仓库
# 访问: https://github.com/new
# 仓库名: unsticker (或其他名字)
# 设为 Public（公开）或 Private（私有）都可以

# 2. 添加远程仓库
git remote add origin https://github.com/你的用户名/unsticker.git

# 3. 推送代码
git push -u origin master
```

### 步骤 2: 在 Railway 部署

#### 1. 注册/登录 Railway

访问: https://railway.app

点击右上角 **"Login"** → 用 **GitHub 账号**登录

#### 2. 创建新项目

- 点击 **"New Project"**
- 选择 **"Deploy from GitHub repo"**
- 选择你的 `unsticker` 仓库
- Railway 会自动开始构建

#### 3. 添加环境变量（重要！）

构建完成后：
- 点击项目卡片进入详情
- 点击顶部的 **"Variables"** 标签
- 点击 **"+ New Variable"**

**至少添加以下一组：**

##### 选项 A: 使用 OpenAI
```
OPENAI_API_KEY=sk-你的OpenAI密钥
OPENAI_API_URL=https://api.openai.com/v1/images/edits
```

##### 选项 B: 使用腾讯云
```
TENCENTCLOUD_SECRET_ID=你的腾讯云ID
TENCENTCLOUD_SECRET_KEY=你的腾讯云密钥
TENCENTCLOUD_REGION=ap-guangzhou
```

**注意：** 添加完环境变量后，Railway 会自动重新部署。

#### 4. 生成公网访问域名

- 点击 **"Settings"** 标签
- 找到 **"Networking"** 部分
- 点击 **"Generate Domain"** 按钮
- 会生成类似：`unsticker-production.up.railway.app`

#### 5. 访问服务

```
https://unsticker-production.up.railway.app
```

把这个链接分享给你的朋友即可！

---

## ✅ 验证部署成功

访问健康检查端点：
```
https://你的域名.up.railway.app/health
```

应该看到：
```json
{"status": "ok", "service": "unsticker"}
```

---

## 💰 费用说明

- **免费额度**: $5/月
- **计费方式**: 按使用量计费
- **预估成本**: 
  - 轻度使用（几个朋友偶尔用）: $0-2/月
  - 中度使用: $3-10/月

---

## 🔧 常见问题

### 1. 构建失败

**检查点：**
- Dockerfile 是否正确
- requirements.txt 是否存在
- scripts 目录是否已提交

**解决方法：**
```bash
# 确保所有文件已提交
git status
git add .
git commit -m "fix: 补充缺失文件"
git push
```

Railway 会自动重新构建。

### 2. 访问报错 503

**原因：** 环境变量未配置或应用未启动

**解决方法：**
- 检查 Variables 中是否添加了 API 密钥
- 查看 Deployments → 点击最新部署 → 查看日志

### 3. 图片处理失败

**原因：** API 密钥配置错误

**解决方法：**
- 重新检查环境变量的值
- 确保 OpenAI API Key 有效
- 确保腾讯云 SecretId/Key 正确

### 4. 想更新代码

```bash
# 本地修改后
git add .
git commit -m "更新说明"
git push

# Railway 会自动检测并重新部署
```

---

## 🎨 自定义域名（可选）

如果你有自己的域名：

1. 在 Railway 项目 Settings → Networking
2. 点击 "Custom Domain"
3. 输入你的域名：`unsticker.yourdomain.com`
4. 在域名 DNS 设置中添加 CNAME 记录：
   ```
   unsticker -> 你的railway域名.up.railway.app
   ```

---

## 📊 监控使用情况

在 Railway 项目页面可以看到：
- **Deployments**: 部署历史和日志
- **Metrics**: CPU、内存、网络使用情况
- **Usage**: 本月费用

---

## 🛑 停止/删除项目

不用了可以随时删除：

1. 进入项目 Settings
2. 滚动到最底部
3. 点击 "Delete Project"

---

## 🎉 完成！

现在你有了一个公网可访问的贴纸移除服务！

**分享链接：** `https://你的项目名.up.railway.app`

**预计完成时间：** 5-10 分钟

有问题随时在 Railway 的 Deployments 查看日志排查。
