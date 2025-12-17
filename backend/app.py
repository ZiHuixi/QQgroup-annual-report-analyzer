#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flask 后端：QQ群年度报告分析器线上版

Licensed under AGPL-3.0: https://www.gnu.org/licenses/agpl-3.0.html

"""

import os
import json
import uuid
import base64
import requests
import asyncio
from typing import List, Dict
from io import BytesIO

from flask import Flask, request, jsonify, send_from_directory, session
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
import secrets
import hmac
import hashlib

load_dotenv()

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import sys
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import config
import analyzer as analyzer_mod
from image_generator import ImageGenerator, AIWordSelector
from utils import load_json
from personal_analyzer import PersonalAnalyzer

from backend.db_service import DatabaseService
from backend.json_storage import JSONStorageService

# 导入日志系统
import sys
sys.path.insert(0, PROJECT_ROOT)
from logger import get_logger, init_logging

init_logging()
logger = get_logger('backend')

app = Flask(__name__)

# ============================================
# 安全配置（从环境变量读取）
# ============================================

SECURITY_ENABLED = os.getenv('SECURITY_ENABLED', 'true').lower() == 'true'
DEPLOYMENT_ENV = os.getenv('DEPLOYMENT_ENV', 'local').lower()
SECURITY_HEADERS_ENABLED = os.getenv('SECURITY_HEADERS_ENABLED', 'true').lower() == 'true'
FILE_SECURITY_CHECK = os.getenv('FILE_SECURITY_CHECK_ENABLED', 'true').lower() == 'true'

# 速率限制配置
RATE_LIMIT_DEFAULT = os.getenv('RATE_LIMIT_DEFAULT', '200 per day, 50 per hour')
RATE_LIMIT_UPLOAD = os.getenv('RATE_LIMIT_UPLOAD', '10 per hour')
RATE_LIMIT_FINALIZE = os.getenv('RATE_LIMIT_FINALIZE', '20 per hour')
RATE_LIMIT_GET_REPORT = os.getenv('RATE_LIMIT_GET_REPORT', '100 per hour')
RATE_LIMIT_LIST_REPORTS = os.getenv('RATE_LIMIT_LIST_REPORTS', '200 per hour')
RATE_LIMIT_GENERATE_IMAGE = os.getenv('RATE_LIMIT_GENERATE_IMAGE', '30 per hour')
RATE_LIMIT_DELETE_REPORT = os.getenv('RATE_LIMIT_DELETE_REPORT', '50 per hour')

# AI功能开关
AI_COMMENT_ENABLED = os.getenv('AI_COMMENT_ENABLED', 'false').lower() == 'true'
AI_WORD_SELECTION_ENABLED = os.getenv('AI_WORD_SELECTION_ENABLED', 'false').lower() == 'true'

# Redis URL（用于分布式限流）
REDIS_URL = os.getenv('REDIS_URL', '')
STORAGE_URI = REDIS_URL if REDIS_URL else 'memory://'

# 安全头配置
SECURITY_HEADER_X_FRAME_OPTIONS = os.getenv('SECURITY_HEADER_X_FRAME_OPTIONS', 'DENY')
SECURITY_HEADER_X_CONTENT_TYPE_OPTIONS = os.getenv('SECURITY_HEADER_X_CONTENT_TYPE_OPTIONS', 'nosniff')
SECURITY_HEADER_X_XSS_PROTECTION = os.getenv('SECURITY_HEADER_X_XSS_PROTECTION', '1; mode=block')
SECURITY_HEADER_REFERRER_POLICY = os.getenv('SECURITY_HEADER_REFERRER_POLICY', 'strict-origin-when-cross-origin')
SECURITY_HEADER_HSTS = os.getenv('SECURITY_HEADER_HSTS', '')

# 文件验证配置
ALLOWED_FILE_EXTENSIONS = os.getenv('ALLOWED_FILE_EXTENSIONS', 'json').split(',')

logger.info(f"{'='*60}")
logger.info(f"🔒 安全配置状态")
logger.info(f"{'='*60}")
logger.info(f"安全功能: {'✅ 已启用' if SECURITY_ENABLED else '❌ 已禁用'}")
logger.info(f"部署环境: {DEPLOYMENT_ENV.upper()}")
logger.info(f"安全响应头: {'✅ 已启用' if SECURITY_HEADERS_ENABLED else '❌ 已禁用'}")
logger.info(f"文件安全检查: {'✅ 已启用' if FILE_SECURITY_CHECK else '❌ 已禁用'}")
logger.info(f"速率限制存储: {'Redis' if REDIS_URL else '内存'}")
logger.info(f"{'='*60}\n")

# 速率限制器配置（根据 SECURITY_ENABLED 决定是否启用）
if SECURITY_ENABLED and RATE_LIMIT_DEFAULT:
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=[RATE_LIMIT_DEFAULT] if RATE_LIMIT_DEFAULT else [],
        storage_uri=STORAGE_URI,
        strategy="fixed-window"
    )
    logger.info("✅ 速率限制已启用")
else:
    # 创建一个禁用的限流器（不实际限制）
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=[],
        storage_uri="memory://",
        enabled=False
    )
    logger.warning("⚠️  速率限制已禁用（仅限本地开发使用）")

# 添加安全响应头
@app.after_request
def add_security_headers(response):
    if SECURITY_ENABLED and SECURITY_HEADERS_ENABLED:
        if SECURITY_HEADER_X_CONTENT_TYPE_OPTIONS:
            response.headers['X-Content-Type-Options'] = SECURITY_HEADER_X_CONTENT_TYPE_OPTIONS
        if SECURITY_HEADER_X_FRAME_OPTIONS:
            response.headers['X-Frame-Options'] = SECURITY_HEADER_X_FRAME_OPTIONS
        if SECURITY_HEADER_X_XSS_PROTECTION:
            response.headers['X-XSS-Protection'] = SECURITY_HEADER_X_XSS_PROTECTION
        if SECURITY_HEADER_REFERRER_POLICY:
            response.headers['Referrer-Policy'] = SECURITY_HEADER_REFERRER_POLICY
        if SECURITY_HEADER_HSTS:
            response.headers['Strict-Transport-Security'] = SECURITY_HEADER_HSTS
    return response

@app.errorhandler(429)
def ratelimit_handler(e):
    logger.warning(f"速率限制触发 | IP: {request.remote_addr} | 路径: {request.path}")
    return jsonify({
        "error": "请求过于频繁，请稍后再试",
        "message": str(e.description)
    }), 429

# CORS配置 - 从环境变量读取
allowed_origins = os.getenv('ALLOWED_ORIGINS', 'http://localhost:5173,http://localhost:5000').split(',')
CORS(app, resources={
    r"/*": {
        "origins": allowed_origins,
        "supports_credentials": True
    }
})

# Flask配置
max_size_mb = int(os.getenv('MAX_UPLOAD_SIZE_MB', '1024'))
app.config['MAX_CONTENT_LENGTH'] = max_size_mb * 1024 * 1024
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', secrets.token_hex(32))
app.config['SESSION_COOKIE_SECURE'] = os.getenv('SESSION_COOKIE_SECURE', 'false').lower() == 'true'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = 86400 * 30  # 30天

# 会话管理
def get_or_create_user_id():
    if 'user_id' not in session:
        session['user_id'] = secrets.token_hex(16)
        session.permanent = True
        logger.debug(f"创建新会话: {session['user_id']}")
    return session['user_id']

# CSRF保护
def generate_csrf_token():
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return session['csrf_token']

def validate_csrf_token():
    if not SECURITY_ENABLED:
        return True
    
    token = request.headers.get('X-CSRF-Token') or request.form.get('csrf_token')
    session_token = session.get('csrf_token')
    
    if not token or not session_token:
        return False
    
    # 使用恒定时间比较防止时序攻击
    return hmac.compare_digest(token, session_token)

@app.before_request
def csrf_protect():
    if request.method in ['GET', 'HEAD', 'OPTIONS']:
        return
    
    if request.path == '/api/health':
        return
    
    if not validate_csrf_token():
        logger.warning(f"CSRF验证失败 | IP: {request.remote_addr} | 路径: {request.path}")
        return jsonify({"error": "CSRF令牌验证失败"}), 403

storage_mode = os.getenv('STORAGE_MODE', 'json').lower()

if storage_mode == 'mysql':
    try:
        logger.info("📦 使用 MySQL 数据库存储")
        db_service = DatabaseService()
        db_service.init_database()
    except Exception as e:
        logger.warning(f"MySQL 初始化失败: {e}")
        logger.info("🔄 回退到 JSON 文件存储")
        db_service = JSONStorageService()
        db_service.init_database()
else:
    try:
        logger.info("📦 使用 JSON 文件存储（本地模式）")
        db_service = JSONStorageService()
        db_service.init_database()
    except Exception as e:
        logger.error(f"存储服务初始化失败: {e}")
        db_service = None


def generate_ai_comments(selected_word_objects: List[Dict]) -> Dict[str, str]:
    # 使用OpenAI API为每个热词生成犀利的AI锐评
    # 返回: {word: comment} 的字典
    if not AI_COMMENT_ENABLED:
        logger.info("⚠️ AI锐评功能被禁用，跳过生成")
        return {}  # 如果关掉，返回空字典
    try:
        from image_generator import AICommentGenerator
        ai_gen = AICommentGenerator()
        
        if ai_gen.client:
            comments = ai_gen.generate_batch(selected_word_objects)
            logger.info("✅ AI锐评生成完成")
            return comments
        else:
            logger.warning("OpenAI未配置，使用默认锐评")
            return {w['word']: ai_gen._fallback_comment(w['word']) 
                   for w in selected_word_objects}
    except Exception as e:
        logger.error(f"AI锐评生成失败: {e}")
        from image_generator import AICommentGenerator
        ai_gen = AICommentGenerator()
        return {w['word']: ai_gen._fallback_comment(w['word']) 
               for w in selected_word_objects}


@app.route("/api/health", methods=["GET"])
def health():
    """健康检查"""
    return jsonify({
        "ok": True,
        "services": {
            "database": db_service is not None
        },
        "rate_limit": {
            "enabled": SECURITY_ENABLED,
            "scope": "per_ip",
            "note": "每个IP地址独立计数"
        },
        "csrf": {
            "enabled": SECURITY_ENABLED
        },
        "features": {
            "ai_comment_enabled": AI_COMMENT_ENABLED,
            "ai_word_selection_enabled": AI_WORD_SELECTION_ENABLED
        }
    })

@app.route("/api/csrf-token", methods=["GET"])
def get_csrf_token():
    get_or_create_user_id()
    token = generate_csrf_token()
    return jsonify({"csrf_token": token})


def allowed_file(filename):
    """检查文件类型是否允许（根据配置）"""
    if not filename or '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in ALLOWED_FILE_EXTENSIONS


@app.route("/api/upload", methods=["POST"])
@limiter.limit(RATE_LIMIT_UPLOAD if SECURITY_ENABLED and RATE_LIMIT_UPLOAD else "1000000 per hour")
def upload_and_analyze():
    if not db_service:
        return jsonify({"error": "数据库服务未初始化"}), 500

    user_id = get_or_create_user_id()

    file = request.files.get("file")
    if not file:
        return jsonify({"error": "缺少文件"}), 400

    if not file.filename:
        return jsonify({"error": "文件名为空"}), 400

    if not allowed_file(file.filename):
        allowed_exts = ', '.join(ALLOWED_FILE_EXTENSIONS)
        return jsonify({"error": f"只允许上传以下类型文件: {allowed_exts}"}), 400

    # 使用 secure_filename 防止路径遍历攻击（根据配置）
    if FILE_SECURITY_CHECK:
        safe_filename = secure_filename(file.filename)
    else:
        safe_filename = file.filename

    auto_select = request.form.get("auto_select", "false").lower() == "true"
    use_stopwords = request.form.get("use_stopwords", "false").lower() == "true"
    logger.info(f"🔍 收到上传请求 - auto_select参数: {request.form.get('auto_select')}, 解析后: {auto_select}")
    logger.info(f"🔍 使用停用词库: {use_stopwords}")
    logger.info(f"🔍 收到上传请求 - auto_select参数: {request.form.get('auto_select')}, 解析后: {auto_select}")

    start_date = request.form.get('start_date')
    end_date = request.form.get('end_date')

    if start_date:
        config.MESSAGE_START_DATE = start_date
        logger.info(f"设置消息开始时间过滤：{start_date}")
    else:
        config.MESSAGE_START_DATE = None

    if end_date:
        config.MESSAGE_END_DATE = end_date
        logger.info(f"设置消息结束时间过滤：{end_date}")
    else:
        config.MESSAGE_END_DATE = None

    report_id = str(uuid.uuid4())

    # 添加请求日志（增强安全审计）
    logger.info(f"{'='*60}")
    logger.info(f"📤 收到上传请求 | Report ID: {report_id}")
    logger.debug(f"原文件名: {file.filename}")
    logger.debug(f"安全文件名: {safe_filename}")
    logger.debug(f"文件大小: {file.content_length or '未知'} 字节")
    logger.debug(f"AI自动选词: {auto_select}")
    logger.debug(f"请求来源: {request.remote_addr}")
    logger.debug(f"User-Agent: {request.headers.get('User-Agent', '未知')}")
    logger.info(f"{'='*60}\n")

    # 临时保存文件
    base_dir = os.path.join(PROJECT_ROOT, "runtime_outputs")
    temp_dir = os.path.join(base_dir, "temp")
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, f"{report_id}.json")
    file.save(temp_path)

    try:
        # 使用流式解析加载JSON（避免内存溢出）
        data = load_json(temp_path)
        analyzer = analyzer_mod.ChatAnalyzer(data, use_stopwords=use_stopwords)
        analyzer.analyze()
        report = analyzer.export_json()

        all_words = report.get('topWords', [])[:100]
        
        # 确保有足够的词汇
        if len(all_words) == 0:
            logger.error("❌ 分析结果中没有找到任何热词")
            cleanup_temp_files(temp_path)
            return jsonify({"error": "分析结果中没有找到热词，请检查聊天记录文件"}), 500

        if auto_select:
            logger.info("✅ 进入自动选词模式")
            # 自动选词模式：根据AI功能是否开启选择不同的选词方式
            if AI_WORD_SELECTION_ENABLED:
                logger.info("🤖 启动AI智能选词...")
                ai_selector = AIWordSelector()

                if ai_selector.client:
                    selected_word_objects = ai_selector.select_words(all_words, top_n=200)

                    if selected_word_objects:
                        # 按词频从高到低排序
                        selected_word_objects_sorted = sorted(
                            selected_word_objects,
                            key=lambda w: w['freq'],
                            reverse=True
                        )
                        selected_words = [w['word'] for w in selected_word_objects_sorted[:10]]
                        # 如果AI选词少于10个，用前10个热词补齐
                        if len(selected_words) < 10:
                            logger.warning(f"AI选词只有{len(selected_words)}个，用前10个热词补齐")
                            selected_words = [w['word'] for w in all_words[:10]]
                        logger.info(f"✅ AI选词成功（已按词频排序）: {', '.join(selected_words)}")
                    else:
                        logger.warning("AI选词失败，使用前10个热词")
                        selected_words = [w['word'] for w in all_words[:10]]
                else:
                    logger.warning("OpenAI未配置，使用前10个热词")
                    selected_words = [w['word'] for w in all_words[:10]]
            else:
                # AI功能未开启，直接使用前10个热词
                logger.info("📋 使用默认前10个热词（AI功能未开启）")
                if len(all_words) < 10:
                    logger.warning(f"可用词汇只有{len(all_words)}个，少于10个")
                selected_words = [w['word'] for w in all_words[:10]]
                if len(selected_words) < 10:
                    logger.error(f"无法选择10个词，只有{len(selected_words)}个可用词汇")
                    raise ValueError(f"可用词汇不足10个，无法生成报告")

            user_id = get_or_create_user_id()
            logger.info(f"📝 准备生成报告，已选择{len(selected_words)}个词: {', '.join(selected_words[:5])}...")
            result = finalize_report(
                report_id=report_id,
                analyzer=None,  
                selected_words=selected_words,
                auto_mode=True,
                report_data=report,
                user_id=user_id
            )
            logger.info(f"✅ 自动选词模式报告生成完成，返回结果: {result.get_json() if hasattr(result, 'get_json') else result}")
            cleanup_temp_files(temp_path)
            return result
        else:
            result_temp_path = os.path.join(temp_dir, f"{report_id}_result.json")
            with open(result_temp_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)

            return jsonify({
                "report_id": report_id,
                "chat_name": report.get('chatName', '未知群聊'),
                "message_count": report.get('messageCount', 0),
                "available_words": all_words,
                "stopwords_enabled": use_stopwords
            })
    except Exception as exc:
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"❌ upload_and_analyze失败: {exc}")
        logger.error(f"错误堆栈:\n{error_trace}")
        traceback.print_exc()
        cleanup_temp_files(temp_path)
        return jsonify({"error": f"分析失败: {exc}"}), 500


@app.route("/api/personal-report", methods=["POST"])
@limiter.limit(RATE_LIMIT_UPLOAD if SECURITY_ENABLED and RATE_LIMIT_UPLOAD else "1000000 per hour")
def generate_personal_report():
    """生成个人年度报告"""
    try:
        if 'file' not in request.files:
            return jsonify({"error": "未上传文件"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "未选择文件"}), 400
        
        target_name = request.form.get('target_name', '').strip()
        if not target_name:
            return jsonify({"error": "未指定要分析的用户名称"}), 400
        
        use_stopwords = request.form.get("use_stopwords", "false").lower() == "true"
        
        # 保存临时文件
        base_dir = os.path.join(PROJECT_ROOT, "runtime_outputs")
        temp_dir = os.path.join(base_dir, "temp")
        os.makedirs(temp_dir, exist_ok=True)
        
        report_id = str(uuid.uuid4())
        temp_path = os.path.join(temp_dir, f"{report_id}.json")
        file.save(temp_path)
        
        try:
            # 加载JSON数据
            data = load_json(temp_path)
            
            # 创建个人分析器
            analyzer = PersonalAnalyzer(data, target_name, use_stopwords=use_stopwords)
            analyzer.analyze()
            report = analyzer.export_json()
            
            # 保存到数据库
            if db_service:
                # 将个人报告数据转换为数据库格式
                success = db_service.create_personal_report(
                    report_id=report_id,
                    user_name=report.get('user_name', target_name),
                    chat_name=report.get('chat_name', '未知群聊'),
                    report_data=report,
                    user_id=get_or_create_user_id()
                )
                if not success:
                    logger.warning(f"⚠️ 个人报告保存到数据库失败，但继续返回数据")
            
            # 清理临时文件
            cleanup_temp_files(temp_path)
            
            return jsonify({
                "success": True,
                "report_id": report_id,
                "report": report,
                "report_url": f"/personal-report/{report_id}"
            })
            
        except ValueError as e:
            cleanup_temp_files(temp_path)
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            cleanup_temp_files(temp_path)
            logger.error(f"❌ 个人报告生成失败: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({"error": f"分析失败: {str(e)}"}), 500
            
    except Exception as e:
        logger.error(f"❌ 个人报告API错误: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"服务器错误: {str(e)}"}), 500


@app.route("/api/finalize", methods=["POST"])
@limiter.limit(RATE_LIMIT_FINALIZE if SECURITY_ENABLED and RATE_LIMIT_FINALIZE else "1000000 per hour")
def finalize_report_endpoint():
    if not db_service:
        return jsonify({"error": "数据库服务未初始化"}), 500
    
    data = request.json
    if not data:
        return jsonify({"error": "请求体为空"}), 400
    
    report_id = data.get('report_id')
    selected_words = data.get('selected_words', [])
    
    if not report_id or not selected_words:
        return jsonify({"error": "缺少必要参数"}), 400
    
    if not isinstance(selected_words, list) or len(selected_words) == 0:
        return jsonify({"error": "selected_words 必须是非空数组"}), 400
    
    if len(selected_words) != 10:
        return jsonify({"error": "必须选择10个词"}), 400
    
    logger.info(f"\n{'='*60}")
    logger.info(f"📝 收到选词确认请求 | Report ID: {report_id}")
    logger.info(f"   选中词汇: {', '.join(selected_words[:5])}{'...' if len(selected_words) > 5 else ''}")
    logger.info(f"   词汇数量: {len(selected_words)}")
    logger.info(f"{'='*60}\n")
    
    try:
        base_dir = os.path.join(PROJECT_ROOT, "runtime_outputs")
        temp_dir = os.path.join(base_dir, "temp")
        result_temp_path = os.path.join(temp_dir, f"{report_id}_result.json")
        
        if not os.path.exists(result_temp_path):
            return jsonify({"error": "分析结果已过期，请重新上传"}), 404
        
        logger.info("📂 加载已缓存的分析结果...")
        with open(result_temp_path, 'r', encoding='utf-8') as f:
            report = json.load(f)
        

        user_id = get_or_create_user_id()
        
        result = finalize_report(
            report_id=report_id,
            analyzer=None,  
            selected_words=selected_words,
            auto_mode=False,
            report_data=report,
            user_id=user_id
        )
        
        # 清理临时文件
        original_json_path = os.path.join(temp_dir, f"{report_id}.json")
        cleanup_temp_files(result_temp_path)
        if os.path.exists(original_json_path):
            cleanup_temp_files(original_json_path)
        
        return result
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"生成失败: {exc}"}), 500


def finalize_report(report_id: str, analyzer, selected_words: List[str], 
                   auto_mode: bool = False, report_data: Dict = None, user_id: str = None):
    """
    完成报告生成
    
    Args:
        report_id: 报告ID
        analyzer: 分析器实例（可选）
        selected_words: 选中的词汇列表
        auto_mode: 是否自动模式
        report_data: 报告数据（可选，如果提供则不使用analyzer）
        user_id: 用户ID（可选）
    """
    try:
        if report_data is None:
            report = analyzer.export_json()
        else:
            report = report_data
        
        # 转换selected_words为详细对象
        top_words = report.get('topWords', [])
        logger.info(f"📊 报告中的topWords数量: {len(top_words)}")
        if not isinstance(top_words, list):
            logger.error(f"❌ topWords格式错误，期望list，实际: {type(top_words)}")
            raise ValueError(f"topWords格式错误: {type(top_words)}")
        
        all_words = {}
        for w in top_words:
            if isinstance(w, dict) and 'word' in w:
                all_words[w['word']] = w
            else:
                logger.warning(f"⚠️ 跳过无效的词汇项: {w}")
        
        logger.info(f"📝 构建的all_words字典包含{len(all_words)}个词")
        logger.info(f"📝 需要处理的selected_words: {selected_words}")
        
        selected_word_objects = []
        for word in selected_words:
            if word in all_words:
                selected_word_objects.append(all_words[word])
            else:
                logger.warning(f"⚠️ 词汇 '{word}' 不在topWords中，使用默认值")
                selected_word_objects.append({"word": word, "freq": 0, "samples": []})
        
        ai_comments = generate_ai_comments(selected_word_objects)
        
        statistics = {
            "chatName": report.get('chatName'),
            "messageCount": report.get('messageCount'),
            "rankings": report.get('rankings', {}),
            "timeDistribution": report.get('timeDistribution', {}),
            "hourDistribution": report.get('hourDistribution', {})
        }
        
        success = db_service.create_report(
            report_id=report_id,
            chat_name=statistics['chatName'],
            message_count=statistics['messageCount'],
            selected_words=selected_word_objects,
            statistics=statistics,
            ai_comments=ai_comments,
            user_id=user_id  
        )
        
        if not success:
            return jsonify({"error": "保存数据库失败"}), 500
        
        return jsonify({
            "success": True,
            "report_id": report_id,
            "report_url": f"/report/{report_id}",
            "message": "报告已生成" if not auto_mode else "AI已自动完成选词并生成报告"
        })
    except Exception as exc:
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"❌ finalize_report失败: {exc}")
        logger.error(f"错误堆栈:\n{error_trace}")
        traceback.print_exc()
        return jsonify({"error": f"最终化失败: {exc}"}), 500


def cleanup_temp_files(file_path: str):
    try:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"🗑️ 已删除临时文件: {file_path}")
    except Exception as e:
        logger.warning(f"⚠️ 清理临时文件失败: {e}")


@app.route("/api/reports", methods=["GET"])
@limiter.limit(RATE_LIMIT_LIST_REPORTS if SECURITY_ENABLED and RATE_LIMIT_LIST_REPORTS else "1000000 per hour")
def list_reports():

    if not db_service:
        return jsonify({"error": "数据库服务未初始化"}), 500
    
    user_id = get_or_create_user_id()
    
    page = int(request.args.get('page', 1))
    page_size = int(request.args.get('page_size', 20))
    chat_name = request.args.get('chat_name')
    
    try:
        result = db_service.list_reports(page, page_size, chat_name, user_id=user_id)
        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": f"查询失败: {exc}"}), 500


@app.route("/api/templates", methods=["GET"])
def get_templates():
    import json
    templates_file = os.path.join(PROJECT_ROOT, "frontend/src/templates/templates.json")
    
    try:
        with open(templates_file, 'r', encoding='utf-8') as f:
            templates_data = json.load(f)
            return jsonify(templates_data)
    except Exception as e:
        return jsonify({
            "templates": [
                {
                    "id": "classic",
                    "name": "模板1",
                    "description": "最初的模板",
                    "component": "classic.vue"
                }
            ]
        })


@app.route("/api/personal-reports/<report_id>", methods=["GET"])
@limiter.limit(RATE_LIMIT_GET_REPORT if SECURITY_ENABLED and RATE_LIMIT_GET_REPORT else "1000000 per hour")
def get_personal_report_api(report_id):
    """获取个人报告"""
    if not db_service:
        return jsonify({"error": "数据库服务未初始化"}), 500
    
    try:
        personal_report = db_service.get_personal_report(report_id)
        if not personal_report:
            return jsonify({"error": "个人报告不存在"}), 404
        
        report_data = personal_report.get('report_data', {})
        return jsonify(report_data)
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"获取失败: {exc}"}), 500


@app.route("/api/personal-reports/<report_id>/generate-image", methods=["POST"])
@limiter.limit(RATE_LIMIT_GENERATE_IMAGE if SECURITY_ENABLED and RATE_LIMIT_GENERATE_IMAGE else "1000000 per hour")
def generate_personal_report_image(report_id):
    """生成个人报告图片"""
    if not db_service:
        return jsonify({"error": "数据库服务未初始化"}), 500
    
    try:
        data = request.get_json() or {}
        template_id = data.get('template', 'personal-classic')
        force_regenerate = data.get('force', False)
        image_format = data.get('format', 'for_share')
        
        personal_report = db_service.get_personal_report(report_id)
        if not personal_report:
            return jsonify({"error": "个人报告不存在"}), 404
        
        cache_key = f"personal_{report_id}_{template_id}_{image_format}"
        if not force_regenerate:
            cached_image = db_service.get_cached_image(cache_key)
            if cached_image:
                logger.info(f"📦 返回缓存图片: {cache_key}")
                return jsonify({
                    "success": True,
                    "image_url": cached_image['image_url'],
                    "cached": True,
                    "generated_at": str(cached_image['created_at'])
                })
        
        logger.info(f"🖼️ 开始生成个人报告图片: {report_id} (模板: {template_id}, 格式: {image_format})")
        
        frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:5173')
        report_url = f"{frontend_url}/personal-report/{template_id}/{report_id}"
        
        if image_format == 'for_share':
            report_url += '?mode=share'
        
        image_data = asyncio.run(generate_image_with_playwright(report_url))
        
        if not image_data:
            return jsonify({"error": "图片生成失败"}), 500
        
        image_url = db_service.save_image_cache(cache_key, image_data)
        
        logger.info(f"✅ 个人报告图片生成成功: {cache_key}")
        
        return jsonify({
            "success": True,
            "image_url": image_url,
            "cached": False,
            "generated_at": "now"
        })
        
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"生成失败: {exc}"}), 500


@app.route("/api/reports/<report_id>", methods=["GET"])
@limiter.limit(RATE_LIMIT_GET_REPORT if SECURITY_ENABLED and RATE_LIMIT_GET_REPORT else "1000000 per hour")
def get_report_api(report_id):
    if not db_service:
        return jsonify({"error": "数据库服务未初始化"}), 500
    
    try:
        report = db_service.get_report(report_id)
        if not report:
            return jsonify({"error": "报告不存在"}), 404
        
        processed_data = process_report_data_for_frontend(report)
        
        return jsonify(processed_data)
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"获取失败: {exc}"}), 500


@app.route("/api/reports/<report_id>", methods=["DELETE"])
@limiter.limit(RATE_LIMIT_DELETE_REPORT if SECURITY_ENABLED and RATE_LIMIT_DELETE_REPORT else "1000000 per hour")
def delete_report(report_id):
    if not db_service:
        return jsonify({"error": "数据库服务未初始化"}), 500
    
    user_id = get_or_create_user_id()
    
    try:
        report = db_service.get_report(report_id)
        if not report:
            return jsonify({"error": "报告不存在"}), 404
        
        if report.get('user_id') != user_id:
            logger.warning(f"⚠️ 权限拒绝: 用户 {user_id} 尝试删除报告 {report_id} (所有者: {report.get('user_id')})")
            return jsonify({"error": "无权限删除此报告"}), 403
        
        success = db_service.delete_report(report_id)
        if not success:
            return jsonify({"error": "删除失败"}), 500
        
        logger.info(f"✅ 报告已删除: {report_id} (用户: {user_id})")
        return jsonify({"success": True, "message": "报告已删除"})
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"删除失败: {exc}"}), 500


@app.route("/api/reports/<report_id>/generate-image", methods=["POST"])
@limiter.limit(RATE_LIMIT_GENERATE_IMAGE if SECURITY_ENABLED and RATE_LIMIT_GENERATE_IMAGE else "1000000 per hour")
def generate_report_image(report_id):
    """
    生成报告图片（后端渲染，支持缓存）
    
    Query参数：
    - template: 模板ID（默认classic）
    - force: 是否强制重新生成（默认false）
    - format: 图片格式，可选 for_display（网页显示版）或 for_share（分享版，默认）

    """
    if not db_service:
        return jsonify({"error": "数据库服务未初始化"}), 500
    
    try:
        data = request.get_json() or {}
        template_id = data.get('template', 'classic')
        force_regenerate = data.get('force', False)
        image_format = data.get('format', 'for_share')  # for_share 或 for_display
        
        report = db_service.get_report(report_id)
        if not report:
            return jsonify({"error": "报告不存在"}), 404
        
        cache_key = f"{report_id}_{template_id}_{image_format}"
        if not force_regenerate:
            cached_image = db_service.get_cached_image(cache_key)
            if cached_image:
                logger.info(f"📦 返回缓存图片: {cache_key}")
                return jsonify({
                    "success": True,
                    "image_url": cached_image['image_url'],
                    "cached": True,
                    "generated_at": str(cached_image['created_at'])
                })
        
        logger.info(f"🖼️ 开始生成图片: {report_id} (模板: {template_id}, 格式: {image_format})")
        
        frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:5173')
        report_url = f"{frontend_url}/report/{template_id}/{report_id}"
        
        if image_format == 'for_share':
            report_url += '?mode=share'
        
        image_data = asyncio.run(generate_image_with_playwright(report_url))
        
        if not image_data:
            return jsonify({"error": "图片生成失败"}), 500
        
        image_url = db_service.save_image_cache(cache_key, image_data)
        
        logger.info(f"✅ 图片生成成功: {cache_key}")
        
        return jsonify({
            "success": True,
            "image_url": image_url,
            "cached": False,
            "generated_at": "now"
        })
        
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"生成失败: {exc}"}), 500


async def generate_image_with_playwright(url):
    """
    使用 Playwright 无头浏览器生成图片
    返回 base64 编码的图片数据
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error("❌ 需要安装 Playwright: pip install playwright && playwright install chromium")
        return None
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )
            
            page = await browser.new_page(
                viewport={'width': 450, 'height': 800},
                device_scale_factor=2  # 2倍分辨率
            )
            
            logger.info(f"   🌐 访问: {url}")
            await page.goto(url, wait_until='networkidle', timeout=30000)
            
            await page.wait_for_timeout(3000)
            
            height = await page.evaluate('document.body.scrollHeight')
            await page.set_viewport_size({'width': 450, 'height': height + 50})
            await page.wait_for_timeout(1000)
            
            screenshot_bytes = await page.screenshot(
                full_page=True,
                type='png'
            )
            
            await browser.close()
            
            image_b64 = base64.b64encode(screenshot_bytes).decode('utf-8')
            return f"data:image/png;base64,{image_b64}"
            
    except Exception as e:
        logger.error(f"❌ Playwright 生成失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def process_report_data_for_frontend(report):
    """
    使用ImageGenerator的逻辑处理报告数据为前端需要的格式
    复用image_generator.py中的_prepare_template_data方法
    """

    json_data = {
        'chatName': report['chat_name'],
        'messageCount': report['message_count'],
        'topWords': report['selected_words'],  # 这里已经包含完整的词信息
        'rankings': report['statistics'].get('rankings', {}),
        'hourDistribution': report['statistics'].get('hourDistribution', {})
    }
    

    gen = ImageGenerator()
    gen.json_data = json_data
    gen.selected_words = report['selected_words']  
    gen.ai_comments = report.get('ai_comments', {}) or {}  
    
    template_data = gen._prepare_template_data()
    
    return {
        "report_id": report['report_id'],
        "chat_name": template_data['chat_name'],
        "message_count": template_data['message_count'],
        "selected_words": template_data['selected_words'],  # 这里已经包含ai_comment
        "rankings": template_data['rankings'],  # 这里已经是处理好的榜单
        "statistics": {
            "hourDistribution": {str(h['hour']): h['count'] for h in template_data['hour_data']}
        },
        "peak_hour": template_data['peak_hour'],
        "created_at": str(report['created_at'])
    }


# 静态文件服务 - 用于 Docker 部署时提供前端页面
frontend_dist = os.path.join(PROJECT_ROOT, "frontend", "dist")

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_frontend(path):
    """提供前端静态文件服务"""
    if path and os.path.exists(os.path.join(frontend_dist, path)):
        return send_from_directory(frontend_dist, path)
    # 默认返回 index.html（用于 Vue Router）
    return send_from_directory(frontend_dist, "index.html")


if __name__ == "__main__":
    debug_mode = os.environ.get("DEBUG", "").lower() in ("1", "true", "yes")
    base_port = int(os.environ.get("FLASK_PORT", os.environ.get("PORT", 5000)))

    def try_run(p):
        app.run(host="0.0.0.0", port=p, debug=debug_mode, use_reloader=False)

    try:
        try_run(base_port)
    except OSError as exc:
        if "Address already in use" in str(exc):
            fallback = base_port + 1
            logger.warning(f"⚠️ 端口 {base_port} 已被占用，尝试 {fallback}")
            try_run(fallback)
        else:
            raise
