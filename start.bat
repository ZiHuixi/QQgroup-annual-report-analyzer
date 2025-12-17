@echo off
chcp 65001 >nul
echo ========================================
echo QQ群年度报告分析器 - 一键启动脚本
echo ========================================
echo.

:: 标记是否需要用户配置
set NEED_CONFIG=0

:: 检查Python
echo [1/9] 检查Python环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 错误：未找到Python，请先安装Python 3.8+
    echo 下载地址：https://www.python.org/downloads/
    pause
    exit /b 1
)
echo ✅ Python已安装

:: 检查Node.js
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

:: 检查并配置后端.env文件
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

:: 检查并创建 config.py（命令行模式需要）
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

:: 如果需要配置，提示用户并退出
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

:: 继续正常启动流程
echo.
echo ✅ 配置文件检查完成，继续启动...

:: 安装Python依赖
echo.
echo [5/9] 安装Python依赖...
if not exist "venv" (
    echo 创建Python虚拟环境...
    python -m venv venv
    if errorlevel 1 (
        echo ❌ 错误：虚拟环境创建失败
        pause
        exit /b 1
    )
)

:: 激活虚拟环境并验证
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ❌ 错误：虚拟环境激活失败
    pause
    exit /b 1
)

:: 设置虚拟环境中的 Python 和 pip 完整路径（确保使用虚拟环境）
set VENV_PYTHON=%CD%\venv\Scripts\python.exe
set VENV_PIP=%CD%\venv\Scripts\pip.exe

:: 验证虚拟环境中的 Python 是否存在
if not exist "%VENV_PYTHON%" (
    echo ❌ 错误：虚拟环境中的 Python 不存在：%VENV_PYTHON%
    echo    请删除 venv 文件夹后重新运行脚本
    pause
    exit /b 1
)

:: 验证虚拟环境中的 pip 是否存在
if not exist "%VENV_PIP%" (
    echo ❌ 错误：虚拟环境中的 pip 不存在：%VENV_PIP%
    echo    请删除 venv 文件夹后重新运行脚本
    pause
    exit /b 1
)

:: 使用虚拟环境中的 Python 验证环境
echo 验证虚拟环境完整性...
"%VENV_PYTHON%" --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 错误：虚拟环境中的 Python 无法运行
    pause
    exit /b 1
)

:: 检查当前使用的 Python 是否在虚拟环境中
for /f "tokens=*" %%i in ('where python 2^>nul') do set PYTHON_PATH=%%i
if defined PYTHON_PATH (
    echo %PYTHON_PATH% | findstr /i "venv" >nul
    if errorlevel 1 (
        echo ⚠️  警告：当前 python 命令可能不在虚拟环境中
        echo    当前路径：%PYTHON_PATH%
        echo    将强制使用虚拟环境中的 Python：%VENV_PYTHON%
    )
)

echo ✅ 虚拟环境已激活并验证
echo    虚拟环境 Python：%VENV_PYTHON%
echo    虚拟环境 pip：%VENV_PIP%
echo 安装后端依赖包（使用虚拟环境中的 pip）...
"%VENV_PIP%" install -r backend\requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple >nul 2>&1
if errorlevel 1 (
    echo ⚠️  使用清华源安装失败，尝试官方源...
    "%VENV_PIP%" install -r backend\requirements.txt
    if errorlevel 1 (
        echo ⚠️  依赖安装失败，尝试分步安装（可能是 jieba_fast 编译失败）...
        echo    1) 先安装核心依赖（不包含 jieba_fast）
        "%VENV_PIP%" install flask flask-cors flask-limiter gunicorn jinja2 openai httpx playwright pymysql python-dotenv requests ijson
        echo    2) 再尝试安装 jieba_fast（如果失败将自动回退 jieba）
        "%VENV_PIP%" install jieba_fast -i https://pypi.tuna.tsinghua.edu.cn/simple >nul 2>&1
        if errorlevel 1 (
            echo    ⚠️  jieba_fast 安装失败，自动回退到 jieba（标准版）
            "%VENV_PIP%" install jieba -i https://pypi.tuna.tsinghua.edu.cn/simple >nul 2>&1
            if errorlevel 1 (
                "%VENV_PIP%" install jieba
            )
        )
    )
)

:: 验证关键依赖包是否已正确安装（使用虚拟环境中的 Python）
echo 验证关键依赖包安装状态（使用虚拟环境中的 Python）...
"%VENV_PYTHON%" -c "import flask; import requests; import jieba_fast" >nul 2>&1
if errorlevel 1 (
    echo ⚠️  部分关键依赖包可能未正确安装，正在检查...
    "%VENV_PYTHON%" -c "import flask" >nul 2>&1
    if errorlevel 1 (
        echo ❌ 错误：flask 未安装，正在安装...
        "%VENV_PIP%" install flask flask-cors flask-limiter
    )
    "%VENV_PYTHON%" -c "import requests" >nul 2>&1
    if errorlevel 1 (
        echo ❌ 错误：requests 未安装，正在安装...
        "%VENV_PIP%" install requests
    )
    "%VENV_PYTHON%" -c "import jieba_fast" >nul 2>&1
    if errorlevel 1 (
        echo ⚠️  jieba_fast 安装失败（可能需要 C++ 编译器）
        echo    正在回退到 jieba（标准版本，功能相同但速度稍慢）...
        "%VENV_PIP%" install jieba -i https://pypi.tuna.tsinghua.edu.cn/simple >nul 2>&1
        if errorlevel 1 (
            "%VENV_PIP%" install jieba
        )
        echo ✅ 已安装 jieba（标准版本）
        echo.
        echo 💡 提示：如果您想使用更快的 jieba_fast，可以：
        echo    1. 安装 Visual C++ Build Tools（推荐）
        echo       下载地址：https://visualstudio.microsoft.com/visual-cpp-build-tools/
        echo       安装时选择 "C++ 生成工具" 工作负载
        echo    2. 或者直接使用 jieba（已安装，功能相同）
    ) else (
        echo ✅ jieba_fast 安装成功（高性能版本）
    )
) else (
    echo ✅ 关键依赖包验证通过（flask, requests, jieba_fast）
)
echo ✅ Python依赖安装完成

:: 安装Playwright浏览器（确保在虚拟环境中）
echo.
echo [6/9] 检查Playwright浏览器...
"%VENV_PYTHON%" -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); p.chromium.launch(headless=True); p.stop()" >nul 2>&1
if errorlevel 1 (
    echo ⚠️  Playwright浏览器未安装，正在安装...
    echo    （首次运行需要下载约100MB，请耐心等待）
    echo    使用虚拟环境中的 Python：%VENV_PYTHON%
    
    :: 确保使用虚拟环境中的 Python 来运行 playwright
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

:: 安装前端依赖
echo.
echo [7/9] 安装前端依赖...
cd frontend
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
cd ..
echo ✅ 前端依赖就绪

:: 检查存储模式并初始化（自动检测是否已初始化）
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
    echo 正在检测并初始化MySQL数据库（如需强制重置，请手动运行 "%VENV_PYTHON% backend/init_db.py --force"）...
    "%VENV_PYTHON%" backend\init_db.py
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

:: 启动后端（使用虚拟环境中的 Python 完整路径）
echo.
echo [9/9] 启动服务...
echo 正在启动后端服务...
echo    使用虚拟环境 Python：%VENV_PYTHON%
echo    后端启动命令：%VENV_PYTHON% backend\app.py

:: 验证后端启动所需的模块是否在虚拟环境中
"%VENV_PYTHON%" -c "import flask; import requests" >nul 2>&1
if errorlevel 1 (
    echo ❌ 错误：虚拟环境中缺少关键模块（flask 或 requests）
    echo    请检查依赖安装是否成功
    pause
    exit /b 1
)

start "QQ群年度报告-后端" cmd /k "cd /d %CD% && %VENV_PYTHON% backend\app.py"

:: 等待后端完全启动（健康检查）
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

:: 使用PowerShell检查后端健康状态（兼容性更好）
powershell -Command "try { $response = Invoke-WebRequest -Uri 'http://localhost:5000/api/health' -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop; exit 0 } catch { exit 1 }" >nul 2>&1
if errorlevel 1 (
    timeout /t 1 /nobreak >nul
    goto wait_backend
)

echo ✅ 后端服务已就绪（端口：5000）

:start_frontend
:: 启动前端
echo 正在启动前端服务...
start "QQ群年度报告-前端" cmd /k "cd /d %CD%\frontend && npm run dev"
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
