@echo off
chcp 65001 >nul
echo ========================================
echo QQ群年度报告分析器 - 一键启动脚本
echo ========================================
echo.

REM ---------------------------------------------------------------------------
REM 本脚本统一使用同一个虚拟环境 (venv) 的 Python 和 pip
REM - 所有后端依赖安装都走 venv 里的 python -m pip
REM - 启动后端也强制使用 venv\Scripts\python.exe
REM - 避免「装在一处，用在另一处」导致的 No module named XXX
REM ---------------------------------------------------------------------------

REM 当前脚本所在目录（项目根目录）
set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%"

REM 虚拟环境 Python / pip 路径（后面所有操作都用它）
set "VENV_PYTHON=%ROOT_DIR%venv\Scripts\python.exe"
set "VENV_PIP=%VENV_PYTHON% -m pip"

echo 项目根目录：%ROOT_DIR%
echo.

::: 标记是否需要用户配置
set NEED_CONFIG=0

::: 检查Python
echo [1/9] 检查Python环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 错误：未找到Python，请先安装Python 3.8+
    echo 下载地址：https://www.python.org/downloads/
    pause
    exit /b 1
)
echo ✅ Python已安装

::: 检查Node.js
echo.
echo [2/9] 检查Node.js环境...
node --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 错误：未找到Node.js，请先安装Node.js 16+
    echo 下载地址：https://nodejs.org/
    pause
    exit /b 1
)
echo ✅ Node.js已安装

::: 检查并配置后端.env文件
echo.
echo [3/9] 检查后端配置文件...
if not exist "backend\.env" (
    echo ⚠️  未找到backend\.env，正在创建...
    copy "backend\.env.example" "backend\.env"
    echo ✅ 已创建 backend\.env
    set NEED_CONFIG=1
) else (
    echo ✅ backend\.env 已存在
)

::: 检查并创建 config.py（命令行模式需要）
echo.
echo [4/9] 检查命令行模式配置文件...
if not exist "config.py" (
    echo ⚠️  未找到config.py，正在创建...
    copy "config.example.py" "config.py"
    echo ✅ 已创建 config.py
    set NEED_CONFIG=1
) else (
    echo ✅ config.py 已存在
)

::: 如果需要配置，提示用户并退出
if %NEED_CONFIG%==1 (
    echo.
    echo ========================================
    echo ⚠️  首次运行 - 需要配置
    echo ========================================
    echo.
    echo 已为您创建配置文件，请按以下步骤操作：
    echo.
    echo 📝 步骤1：配置 Web 模式（必需）
    echo    文件：backend\.env
    echo    说明：
    echo    - 默认使用JSON存储（无需MySQL）
    echo    - 如需MySQL，设置 STORAGE_MODE=mysql 并配置密码
    echo    - 如需AI功能，配置 OPENAI_API_KEY
    echo.
    echo 📝 步骤2：配置命令行模式（可选）
    echo    文件：config.py
    echo    说明：
    echo    - 用于直接运行 python main.py
    echo    - 修改 INPUT_FILE 为你的聊天记录路径
    echo    - 其他参数可按需调整
    echo.
    echo 💡 提示：
    echo    - 大多数用户使用 Web 模式即可（浏览器访问）
    echo    - 命令行模式适合高级用户和批量处理
    echo    - 配置完成后，再次运行 start.bat 即可
    echo.
    echo ========================================
    echo.
    pause
    exit /b 0
)

::: 继续正常启动流程
echo.
echo ✅ 配置文件检查完成，继续启动...

::: 安装Python依赖（统一使用 venv）
echo.
echo [5/9] 安装Python依赖...

REM 1）创建虚拟环境（如不存在）
if not exist "venv" (
    echo 创建Python虚拟环境...
    python -m venv venv
    if errorlevel 1 (
        echo ❌ 错误：虚拟环境创建失败
        pause
        exit /b 1
    )
)

REM 2）确认虚拟环境 Python 存在
if not exist "%VENV_PYTHON%" (
    echo ❌ 错误：未找到虚拟环境 Python：%VENV_PYTHON%
    echo    请删除 venv 目录后重新运行本脚本
    pause
    exit /b 1
)

echo 使用虚拟环境 Python：%VENV_PYTHON%
echo.
echo 升级 pip / setuptools / wheel...
"%VENV_PYTHON%" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 (
    echo ⚠️  升级 pip 失败（可以忽略），继续安装依赖...
)

REM 3）优先使用 requirements.txt 安装全部后端依赖
echo 安装后端依赖（使用 backend\requirements.txt）...
"%VENV_PYTHON%" -m pip install -r "%ROOT_DIR%backend\requirements.txt" -i https://pypi.tuna.tsinghua.edu.cn/simple
if errorlevel 1 (
    echo ⚠️  使用清华源安装失败，尝试官方源...
    "%VENV_PYTHON%" -m pip install -r "%ROOT_DIR%backend\requirements.txt"
)

REM 4）如果依赖依然有问题，分步安装关键包，并对 jieba_fast 做回退
echo 验证并补充关键依赖（flask / requests 等）...
"%VENV_PYTHON%" -c "import flask, requests" >nul 2>&1
if errorlevel 1 (
    echo - 安装 Flask / requests 等核心依赖...
    "%VENV_PYTHON%" -m pip install flask flask-cors flask-limiter gunicorn jinja2 requests python-dotenv ijson pymysql httpx openai
)

REM 5）单独处理分词库：优先 jieba_fast，失败则回退 jieba
"%VENV_PYTHON%" -c "import jieba_fast" >nul 2>&1
if errorlevel 1 (
    echo - 尝试安装 jieba_fast（如失败将自动回退 jieba）...
    "%VENV_PYTHON%" -m pip install jieba_fast -i https://pypi.tuna.tsinghua.edu.cn/simple >nul 2>&1
    if errorlevel 1 (
        echo   ⚠️  jieba_fast 安装失败，使用标准版 jieba 代替...
        "%VENV_PYTHON%" -m pip install jieba
    )
)

REM 6）最终检查 flask / requests 是否在 venv 中
"%VENV_PYTHON%" -c "import flask, requests" >nul 2>&1
if errorlevel 1 (
    echo ❌ 错误：虚拟环境中缺少关键模块（flask 或 requests），请检查网络或手动执行：
    echo    "%VENV_PYTHON%" -m pip install flask requests
    pause
    exit /b 1
)

echo ✅ Python 依赖安装并验证完成

::: 安装Playwright浏览器（确保在虚拟环境中）
echo.
echo [6/9] 检查Playwright浏览器...
"%VENV_PYTHON%" -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); p.chromium.launch(headless=True); p.stop()" >nul 2>&1
if errorlevel 1 (
    echo ⚠️  Playwright浏览器未安装，正在安装...
    echo    （首次运行需要下载约100MB，请耐心等待）
    echo    使用虚拟环境中的 Python：%VENV_PYTHON%

    "%VENV_PYTHON%" -m playwright install chromium

    if errorlevel 1 (
        echo.
        echo ⚠️  Playwright浏览器安装失败
        echo    图片生成功能可能无法使用，但Web界面仍可正常运行
        echo    如果问题持续，请手动运行：%VENV_PYTHON% -m playwright install chromium
        echo.
    ) else (
        echo ✅ Playwright浏览器安装完成
    )
) else (
    echo ✅ Playwright浏览器已就绪
)

::: 安装前端依赖
echo.
echo [7/9] 安装前端依赖...
cd "%ROOT_DIR%frontend"
if not exist "node_modules" (
    echo 安装前端依赖包（这可能需要几分钟）...
    call npm install
    if errorlevel 1 (
        echo ❌ 错误：前端依赖安装失败
        echo 请检查网络连接或尝试使用国内镜像：
        echo npm install --registry=https://registry.npmmirror.com
        cd ..
        pause
        exit /b 1
    )
) else (
    echo ✅ 前端依赖已安装
)
cd "%ROOT_DIR%"
echo ✅ 前端依赖就绪

::: 检查存储模式并初始化（自动检测是否已初始化）
echo.
echo [8/9] 初始化存储...
findstr /C:"STORAGE_MODE=mysql" backend\.env >nul 2>&1
if errorlevel 1 (
    echo ✅ 使用JSON文件存储（无需数据库）
    echo    数据将保存在：runtime_outputs\reports_db\
) else (
    echo 检测到MySQL存储模式
    echo ⚠️  请确保MySQL服务已启动！
    echo.
    echo 正在检测并初始化MySQL数据库（如需强制重置，请手动运行 "%VENV_PYTHON% backend\init_db.py --force"）...
    "%VENV_PYTHON%" "%ROOT_DIR%backend\init_db.py"
    if errorlevel 1 (
        echo.
        echo ⚠️  MySQL初始化失败！
        echo    系统将自动回退到JSON文件存储模式
        echo    如需使用MySQL，请检查：
        echo    1. MySQL服务是否已启动
        echo    2. backend\.env 中的数据库配置是否正确
        echo    3. MySQL用户是否有创建数据库的权限
        echo.
        pause
        exit /b 1
    ) else (
        echo ✅ MySQL数据库初始化完成或已存在，无需重置
    )
)

::: 启动后端（使用虚拟环境中的 Python 完整路径）
echo.
echo [9/9] 启动服务...
echo 正在启动后端服务...
echo    使用虚拟环境 Python：%VENV_PYTHON%
echo    后端启动命令：%VENV_PYTHON% backend\app.py

REM 在新 cmd 窗口中切到 backend 目录，使用相对路径调用 venv Python
start "QQ群年度报告-后端" cmd /k "cd /d %ROOT_DIR%backend && ..\venv\Scripts\python.exe app.py"

::: 等待后端完全启动（健康检查）
echo 等待后端服务就绪...
set RETRY_COUNT=0
set MAX_RETRIES=30

:wait_backend
set /a RETRY_COUNT+=1
if %RETRY_COUNT% gtr %MAX_RETRIES% (
    echo.
    echo ⚠️  警告：后端服务启动超时（已等待30秒）
    echo    前端可能会出现连接错误
    echo    请检查后端窗口是否有错误信息
    echo.
    goto start_frontend
)

powershell -Command "try { $response = Invoke-WebRequest -Uri 'http://localhost:5000/api/health' -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop; exit 0 } catch { exit 1 }" >nul 2>&1
if errorlevel 1 (
    timeout /t 1 /nobreak >nul
    goto wait_backend
)

echo ✅ 后端服务已就绪（端口：5000）

:start_frontend
::: 启动前端
echo 正在启动前端服务...
start "QQ群年度报告-前端" cmd /k "cd /d %ROOT_DIR%frontend && npm run dev"
timeout /t 3 /nobreak >nul
echo ✅ 前端服务已启动（端口：5173）

echo.
echo ========================================
echo 🎉 启动完成！
echo ========================================
echo 📱 前端访问地址：http://localhost:5173
echo 🔧 后端API地址：http://localhost:5000
echo.
echo 💡 使用提示：
echo    - 两个服务窗口将保持打开状态
echo    - 关闭窗口即停止对应服务
echo    - 按Ctrl+C可停止服务
echo.
echo 📖 详细文档：README.md
echo ========================================
echo.
pause