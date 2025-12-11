# 🎉 QQ群聊年度报告分析器

一个用于分析QQ群聊记录并生成年度热词报告的工具。支持热词发现、趣味统计、可视化报告生成等功能。前后端一体：上传 qq-chat-exporter 导出的 JSON，即可在 Web 端完成分析，也可命令行直接运行。

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

## ✨ 功能特点

- 🔍 **智能分词**：基于 jieba，支持新词发现与高频词组合并
- 📊 **热词统计**：高频词、贡献者、样例句
- 🎮 **趣味榜单**：话痨/字数/长文/表情/图片/深夜党/早起鸟/复读机等
- ⏰ **时段分析**：24 小时活跃分布
- 🖼️ **可视化报告**：生成 HTML，可选 PNG
- 🤖 **AI 锐评**：支持 OpenAI 接口（可选）

## 📦 安装

### 1. 克隆项目
```bash
git clone https://github.com/ZiHuixi/QQgroup-annual-report-analyzer.git
cd QQgroup-annual-report-analyzer
```

### 2. 后端依赖
```bash
cd backend
pip install -r requirements.txt
```

### 3. 前端依赖
```bash
cd ../frontend
npm install
```

### 4. 可选：图片导出（Playwright）
```bash
pip install playwright
playwright install chromium
```

## 🚀 使用方法

### 获取群聊数据
推荐使用 [qq-chat-exporter](https://github.com/shuakami/qq-chat-exporter) 导出 QQ 群聊记录为 JSON。

### A. 本地前后端模式（推荐）
1) 后端
```bash
cd backend
python app.py         # 若 5000 占用会自动尝试 5001
```
2) 前端（新终端）
```bash
cd frontend
npm run dev           # 默认 5173，已代理到 http://localhost:5000
```
3) 浏览器打开 `http://localhost:5173`，上传 JSON，调整参数后点击分析。

### B. 纯命令行模式
```bash
# 默认读取 config.py 中的 INPUT_FILE
python main.py
# 或指定文件
python main.py your_chat.json
```

## ⚙️ 配置说明（核心项）
编辑 `config.py`（后端 API 可通过 options 覆盖）：
```python
INPUT_FILE = "chat.json"
TOP_N = 200
NEW_WORD_MIN_FREQ = 20
PMI_THRESHOLD = 2.0
ENTROPY_THRESHOLD = 0.5
MERGE_MIN_FREQ = 30
MERGE_MIN_PROB = 0.3
ENABLE_IMAGE_EXPORT = False  # 服务端无 chromium 时建议 False
OPENAI_API_KEY = ""          # 可选，用于 AI 锐评
OPENAI_BASE_URL = ""
OPENAI_MODEL = ""
```

## 🖥️ 前端可调参数
- TOP_N、新词频次、PMI/熵阈值、合并频次/概率
- 是否生成图片（需后端 Playwright + Chromium）

## 📋 输出文件
- `xxx_年度热词报告.txt`：文本报告
- `xxx_分析结果.json`：结构化数据（含榜单/时段分布/样例）
- `xxx_年度热词报告.html`：HTML 可视化报告
- `xxx_年度热词报告.png`：图片报告（可选）

## ☁️ 部署示例（Render 免费）
- Build: `cd frontend && npm install && npm run build && cd ../backend && pip install -r requirements.txt`
- Start: `cd backend && gunicorn app:app --bind 0.0.0.0:$PORT`
- 如需一体化托管，可将 `frontend/dist` 作为 Flask 静态目录提供。
- 若无 Chromium，请设 `ENABLE_IMAGE_EXPORT=false`。

## ⚠️ 注意事项
- 分词基于统计方法，建议配置 `BLACKLIST`/`WHITELIST` 过滤无意义词。
- AI 锐评需配置 OpenAI Key；未配置会使用默认文案。
- 大文件上传受部署平台限制，必要时调大请求体大小或改用对象存储。

## 🛠️ 项目结构
```
QQgroup-annual-report-analyzer/
├── backend/            # Flask API
├── frontend/           # Vite + Vue 前端
├── main.py             # CLI 入口
├── analyzer.py         # 核心分析
├── report_generator.py # 文本报告
├── image_generator.py  # HTML/PNG 报告
├── config.py|example   # 配置
├── templates/          # HTML 模板
└── README.md
```

## 📄 许可证
MIT License

## 🤝 贡献
欢迎 Issue / PR！

## 致谢
- [jieba](https://github.com/fxsjy/jieba) - 中文分词
- [qq-chat-exporter](https://github.com/shuakami/qq-chat-exporter) - QQ聊天记录导出
- [Playwright](https://playwright.dev/) - 网页截图
# 🎉 QQ群聊年度报告生成器

一个用于分析QQ群聊记录并生成年度热词报告的工具。支持热词发现、趣味统计、可视化报告生成等功能。

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

## ✨ 功能特点

- 🔍 **智能分词** - 基于jieba分词，支持新词发现和词组合并
- 📊 **热词统计** - 自动统计群聊高频词汇及其贡献者
- 🎮 **趣味榜单** - 话痨榜、深夜党、复读机等多种有趣排行
- ⏰ **时段分析** - 24小时活跃度分布统计
- 🖼️ **可视化报告** - 生成HTML/图片报告
- 🤖 **AI锐评** - 支持调用OpenAI为热词生成有趣点评（可选）

## 📦 安装

### 1. 克隆项目

```bash
git clone https://github.com/ZiHuixi/QQgroup-annual-report-analyzer.git
cd QQgroup-annual-report-analyzer
```
### 2. 安装依赖
```bash
pip install -r requirements.txt
```
### 3. 配置

```bash
# 复制配置模板
cp config.example.py config.py

# 编辑配置文件
vim config.py  # 或用其他编辑器
```

### 4. 安装图片导出功能
如需将报告导出为图片，还需安装 Playwright：
```bash
pip install playwright
playwright install chromium
```


## 🚀 使用方法

### 获取群聊数据

**推荐使用 [qq-chat-exporter](https://github.com/shuakami/qq-chat-exporter) 导出QQ群聊记录为JSON格式。**

### 运行分析

```bash
# 方式1：使用默认配置文件
python main.py

# 方式2：指定输入文件
python main.py your_chat.json
```

### 配置说明

编辑 `config.py` 进行配置：

```python
# 输入文件路径
INPUT_FILE = "chat.json"

# 热词数量
TOP_N = 200

# 新词发现参数
NEW_WORD_MIN_FREQ = 20        # 新词最小出现次数
PMI_THRESHOLD = 2.0           # PMI阈值
ENTROPY_THRESHOLD = 0.5       # 熵阈值

# 可视化报告
ENABLE_IMAGE_EXPORT = True

# OpenAI配置（用于AI锐评，可选）
OPENAI_API_KEY = "your-api-key"
OPENAI_BASE_URL = "https://api.openai.com/v1"
OPENAI_MODEL = "gpt-4o-mini"
```

---

## 📋 输出文件

运行后会在输入文件同目录下生成：

| 文件 | 说明 |
|------|------|
| `xxx_年度热词报告.txt` | 详细文本报告 |
| `xxx_分析结果.json` | 结构化JSON数据 |
| `xxx_年度热词报告.html` | 可视化HTML报告 |
| `xxx_年度热词报告.png` | 图片报告（可选） |

---

## ⚠️ 注意事项

### 关于分词准确性

**本项目的分词功能基于jieba和统计算法，准确性有限，生成的热词结果可能包含一些无意义或错误的词组。**

建议：
- 生成报告时选择 **交互式选词模式**，手动挑选有意义的热词
- 可以在 `config.py` 中配置 `BLACKLIST` 过滤不需要的词
- 可以在 `config.py` 中配置 `WHITELIST` 保留特定词汇

### 关于AI锐评

- AI锐评功能需要配置 OpenAI API Key
- 支持兼容 OpenAI 接口的第三方服务
- 不配置则使用默认文案

---

## 📊 示例输出

### 趣味榜单

| 榜单 | 说明 |
|------|------|
| 🏆 话痨榜 | 发言条数最多 |
| 📝 字数榜 | 总字数最多 |
| 📖 长文王 | 平均每条消息字数最多 |
| 😂 表情帝 | 发送表情最多 |
| 🖼️ 图片狂魔 | 发送图片最多 |
| 🌙 深夜党 | 0-6点发言最多 |
| 🌅 早起鸟 | 6-9点发言最多 |
| 🔄 复读机 | 复读次数最多 |

---

## 🛠️ 项目结构

```
QQgroup-annual-report-analyzer/
├── main.py              # 主入口
├── analyzer.py          # 核心分析器
├── report_generator.py  # 文本报告生成
├── image_generator.py   # 可视化报告生成
├── config.py            # 配置文件
├── utils.py             # 工具函数
├── templates/           # HTML模板目录
│   └── report_template.html
├── requirements.txt
└── README.md
```

---

## 📄 许可证

MIT License


## 🤝 贡献

欢迎提交 Issue 和 Pull Request！


## 致谢

- [jieba](https://github.com/fxsjy/jieba) - 中文分词
- [qq-chat-exporter](https://github.com/shuakami/qq-chat-exporter) - QQ聊天记录导出
- [Playwright](https://playwright.dev/) - 网页截图