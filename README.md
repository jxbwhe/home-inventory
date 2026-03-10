# Home Inventory Manager (家庭消耗品管理工具)

这是一个专为家庭打造的轻量级消耗品（如纸巾、洗护用品、清洁剂等）库存与成本管理系统。它旨在帮助你追踪家中物品的使用情况，提醒补充时机，并清晰地展示各项日用品的使用成本。

## ✨ 功能特性

- 📦 **物品录入与使用管理**：轻松记录消耗品的购买与使用情况，支持上传购买记录的图片凭证。
- 💰 **成本计算与日均追踪**：自动根据购买总价和使用时长，计算并展示每项消耗品的“日均使用成本”。
- 📱 **移动端优先体验**：前端采用响应式设计，完美适配手机端浏览器，提供类似原生 App 的底部导航栏体验，方便随时随地记录。
- 🐳 **Docker 容器化支持**：提供标准化的 `docker-compose` 配置，数据（数据库与图片）挂载至宿主机，完美适配群晖、威联通等家庭 NAS 环境部署。

## 🛠️ 技术栈

- **后端**：Python 3 + FastAPI + SQLAlchemy
- **数据库**：SQLite（轻量级，无需额外部署数据库服务）
- **前端**：HTML5 + 原生 JavaScript + Bootstrap 5
- **部署**：Docker + Docker Compose

---

## 🚀 部署指南

### 方式一：Docker 一键部署（推荐，适合 NAS）

项目包含完整的 `Dockerfile` 和 `docker-compose.yml`，你可以非常方便地将它部署到任何支持 Docker 的环境中。

1. 克隆或下载本项目到你的服务器 / NAS 中：
   ```bash
   git clone https://github.com/yourusername/home-inventory.git
   cd home-inventory
   ```

2. 运行 Docker Compose 启动服务：
   ```bash
   docker-compose up -d --build
   ```
   *(注：部分新版 Docker 环境可能使用 `docker compose up -d --build`)*

3. 访问应用：
   打开浏览器，访问 `http://<服务器或NAS的局域网IP>:8000` 即可开始使用。

> **数据持久化说明**：容器内的数据库文件 `inventory.db` 和上传的图片文件 `/app/data` 目录已经通过 `docker-compose.yml` 映射到了宿主机的 `./data` 目录下。这意味着即使你重启或更新容器，你的数据和图片也绝对安全，不会丢失。

---

### 方式二：源码本地开发部署

如果你想对源码进行修改或在本地进行开发测试，可以按照以下步骤启动：

1. **环境要求**：确保你的系统已安装 Python 3.8+。

2. **克隆项目并进入目录**：
   ```bash
   git clone https://github.com/yourusername/home-inventory.git
   cd home-inventory
   ```

3. **创建并激活虚拟环境**（推荐）：
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # Windows 用户请使用 venv\Scripts\activate
   ```

4. **安装依赖**：
   ```bash
   pip install -r requirements.txt
   ```

5. **运行 FastAPI 服务**：
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

6. **访问应用**：
   打开浏览器，访问 `http://localhost:8000`。
   *(API 交互文档可以直接访问 `http://localhost:8000/docs` 查阅)*

## 🤝 贡献与反馈

欢迎提交 Issue 和 Pull Request 来帮助完善这个家庭小工具！如果觉得好用，别忘了点个 ⭐️ Star！
