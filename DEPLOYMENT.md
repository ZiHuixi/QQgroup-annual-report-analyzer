# QQ群年度报告分析器 - 线上版部署指南

## 系统架构

这是一个完整的线上分析系统，包含以下组件：

1. **前端** (Vue 3 + Vite)：提供用户上传、选词、查看历史等交互界面
2. **后端** (Flask)：处理文件上传、分析、数据库操作
3. **MySQL 数据库**：存储报告元数据和用户选择的词汇

## 工作流程

**完整流程：**

1. 用户在前端选择 QQ 群聊 JSON 文件
2. 前端上传文件到后端
3. 后端保存到本地临时目录并分析 JSON 文件，提取热词和统计数据
4. 分析完成后删除本地临时文件
5. 将分析结果保存到 MySQL 数据库，返回 report_id 和热词列表给前端
6. 用户从热词列表中选择想要展示的词汇
7. 后端根据用户选择生成 AI 点评
8. 将完整报告数据保存到 MySQL 数据库
9. 前端动态渲染报告，用户可随时查看历史记录

## 环境要求

### 服务器要求

- Python 3.8+
- Node.js 16+
- MySQL 5.7+ 或 8.0+

### 系统依赖

- Linux/Windows Server
- 至少 2GB RAM
- 至少 10GB 磁盘空间

## 部署步骤

### 1. 准备 MySQL 数据库

```bash
# 登录 MySQL
mysql -u root -p

# 创建数据库（可选，初始化脚本会自动创建）
CREATE DATABASE qq_reports CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 2. 克隆项目

```bash
git clone https://github.com/ZiHuixi/QQgroup-annual-report-analyzer.git
cd QQgroup-annual-report-analyzer
```

### 3. 配置后端

```bash
cd backend

# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，填入实际配置
nano .env
```

`.env` 配置示例：

```ini
# MySQL 配置
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_mysql_password
MYSQL_DATABASE=qq_reports
MYSQL_CHARSET=utf8mb4

# Flask 配置
FLASK_SECRET_KEY=your_random_secret_key_here
FLASK_ENV=production
FLASK_PORT=5000
```

### 4. 安装后端依赖

```bash
# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 如果需要图片生成功能，安装 Playwright
playwright install chromium
```

### 5. 初始化数据库

```bash
# 运行数据库初始化脚本
python init_db.py
```

成功后会看到：
```
连接到 MySQL 服务器 localhost:3306...
创建数据库 qq_reports...
✓ 数据库 qq_reports 已创建或已存在
创建报告表...
✓ 报告表已创建

✅ 数据库初始化完成！
```

### 6. 启动后端服务

```bash
# 开发模式
python app.py

# 生产模式（使用 gunicorn）
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### 7. 配置前端

```bash
cd ../frontend

# 复制环境变量模板
cp .env.example .env

# 编辑 .env（如果后端不在同一服务器，需要修改 API 地址）
nano .env
```

`.env` 配置：

```ini
# 生产环境需要修改为实际的后端地址
VITE_API_BASE=http://your-server-ip:5000/api
```

### 8. 安装前端依赖并构建

```bash
# 安装依赖
npm install

# 开发模式
npm run dev

# 生产构建
npm run build
```

### 9. 部署前端（生产环境）

#### 方案 A：使用 Nginx

```bash
# 安装 Nginx
sudo apt install nginx  # Ubuntu/Debian
# 或
sudo yum install nginx  # CentOS/RHEL

# 配置 Nginx
sudo nano /etc/nginx/sites-available/qq-reports
```

Nginx 配置示例：

```nginx
server {
    listen 80;
    server_name your-domain.com;  # 替换为你的域名

    # 前端静态文件
    root /path/to/QQgroup-annual-report-analyzer/frontend/dist;
    index index.html;

    # 前端路由
    location / {
        try_files $uri $uri/ /index.html;
    }

    # 代理后端 API
    location /api/ {
        proxy_pass http://localhost:5000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # 增加超时时间（分析可能需要较长时间）
        proxy_read_timeout 300s;
        proxy_connect_timeout 300s;
    }

    # 文件上传大小限制
    client_max_body_size 100M;
}
```

启用配置：

```bash
sudo ln -s /etc/nginx/sites-available/qq-reports /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

#### 方案 B：使用 Docker（推荐）

创建 `docker-compose.yml`：

```yaml
version: '3.8'

services:
  backend:
    build: ./backend
    ports:
      - "5000:5000"
    environment:
      - MYSQL_HOST=mysql
      - MYSQL_PASSWORD=${MYSQL_PASSWORD}
    depends_on:
      - mysql
    volumes:
      - ./backend:/app
      - ./runtime_outputs:/app/runtime_outputs

  frontend:
    build: ./frontend
    ports:
      - "80:80"
    depends_on:
      - backend

  mysql:
    image: mysql:8.0
    environment:
      - MYSQL_ROOT_PASSWORD=${MYSQL_PASSWORD}
      - MYSQL_DATABASE=qq_reports
    volumes:
      - mysql_data:/var/lib/mysql
    ports:
      - "3306:3306"

volumes:
  mysql_data:
```

### 10. 使用进程管理器（生产环境）

#### 使用 Supervisor

```bash
sudo apt install supervisor

# 创建配置文件
sudo nano /etc/supervisor/conf.d/qq-reports.conf
```

配置内容：

```ini
[program:qq-reports-backend]
command=/path/to/venv/bin/gunicorn -w 4 -b 0.0.0.0:5000 app:app
directory=/path/to/QQgroup-annual-report-analyzer/backend
user=www-data
autostart=true
autorestart=true
stderr_logfile=/var/log/qq-reports-backend.err.log
stdout_logfile=/var/log/qq-reports-backend.out.log
```

启动：

```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start qq-reports-backend
```

#### 使用 systemd

```bash
sudo nano /etc/systemd/system/qq-reports.service
```

配置内容：

```ini
[Unit]
Description=QQ Reports Backend
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/QQgroup-annual-report-analyzer/backend
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/gunicorn -w 4 -b 0.0.0.0:5000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

启动：

```bash
sudo systemctl daemon-reload
sudo systemctl enable qq-reports
sudo systemctl start qq-reports
```

## 使用说明

### 用户操作流程

1. **上传分析**
   - 访问网站，点击"上传分析"标签
   - 调整分析参数（可选）
   - 选择 QQ 群聊 JSON 文件并上传
   - 等待分析完成（通常需要 30-60 秒）

2. **选择热词**
   - 系统显示分析出的热词列表
   - 点击词汇进行选择（建议选择 10-20 个）
   - 点击"确认选择并生成报告"

3. **查看报告**
   - 生成完成后可直接查看
   - 也可以在"历史记录"中查看所有报告

4. **历史记录**
   - 查看所有生成的报告
   - 支持按群聊名称搜索
   - 支持删除报告

### API 接口说明

#### 1. 上传并分析

```
POST /api/upload
Content-Type: multipart/form-data

参数：
- file: JSON 文件
- options: JSON 字符串（可选）

返回：
{
  "report_id": "uuid",
  "chat_name": "群聊名称",
  "message_count": 1000,
  "top_words": [{"word": "词汇", "freq": 100}, ...],
  "analysis_summary": {...}
}
```

#### 2. 完成报告（用户选词后）

```
POST /api/finalize
Content-Type: application/json

{
  "report_id": "uuid",
  "selected_words": ["词1", "词2", ...]
}

返回：
{
  "success": true,
  "report_id": "uuid",
  "report_url": "/report/{report_id}",
  "message": "报告已生成"
}
```

#### 4. 查询报告列表

```
GET /api/reports?page=1&page_size=20&chat_name=搜索关键词
```

#### 5. 获取报告详情

```
GET /api/reports/{report_id}
```

#### 6. 查看报告 HTML

```
GET /api/reports/{report_id}/html
```

#### 7. 删除报告

```
DELETE /api/reports/{report_id}
```

## 故障排查

### 后端启动失败

1. **数据库连接失败**
   ```
   检查 MySQL 服务是否运行
   检查用户名密码是否正确
   检查数据库是否已创建
   ```

2. **端口占用**
   ```bash
   # 查看端口占用
   netstat -tuln | grep 5000
   
   # 修改端口
   export FLASK_PORT=5001
   ```

### 前端访问问题

1. **API 请求失败**
   ```
   检查后端是否正常运行
   检查 CORS 配置
   检查防火墙设置
   ```

2. **文件上传失败**
   ```
   检查文件大小限制
   检查 Nginx client_max_body_size 设置
   ```

## 安全建议

1. **生产环境必须配置**：
   - 使用 HTTPS（SSL 证书）
   - 配置防火墙规则
   - 限制 API 访问频率
   - 定期备份数据库

2. **敏感信息保护**：
   - 不要提交 .env 文件到代码仓库
   - 使用强密码

3. **数据库安全**：
   - 不要使用 root 账户
   - 创建专用数据库用户
   - 限制远程访问

## 性能优化

1. **启用缓存**
2. **使用 CDN 加速静态资源**
3. **数据库索引优化**
4. **增加 Gunicorn worker 数量**
5. **配置 Redis 缓存（可选）**

## 维护建议

1. **定期备份**：
   - MySQL 数据库

2. **日志管理**：
   ```bash
   # 查看后端日志
   tail -f /var/log/qq-reports-backend.out.log
   
   # 查看 Nginx 日志
   tail -f /var/log/nginx/access.log
   ```

3. **监控**：
   - 磁盘空间
   - 内存使用
   - API 响应时间

## 支持

如有问题，请：
1. 查看 [GitHub Issues](https://github.com/ZiHuixi/QQgroup-annual-report-analyzer/issues)
2. 提交新的 Issue
3. 联系项目维护者

## 许可证

本项目采用 MIT 许可证。
