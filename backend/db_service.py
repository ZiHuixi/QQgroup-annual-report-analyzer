#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库服务：管理报告数据的存储和查询
"""

import pymysql
import json
import os
import sys
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

# 添加父目录到路径以导入logger
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from logger import get_logger

load_dotenv()

logger = get_logger(__name__)


class DatabaseService:
    def __init__(self):
        self.config = {
            'host': os.getenv('MYSQL_HOST', 'localhost'),
            'port': int(os.getenv('MYSQL_PORT', '3306')),
            'user': os.getenv('MYSQL_USER', 'root'),
            'password': os.getenv('MYSQL_PASSWORD', ''),
            'database': os.getenv('MYSQL_DATABASE', 'qq_reports'),
            'charset': os.getenv('MYSQL_CHARSET', 'utf8mb4')
        }
    
    def get_connection(self):
        return pymysql.connect(**self.config)
    
    def init_database(self):
        conn = None
        try:
            config_without_db = self.config.copy()
            database_name = config_without_db.pop('database')
            conn = pymysql.connect(**config_without_db)
            cursor = conn.cursor()
            
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {database_name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            cursor.execute(f"USE {database_name}")
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reports (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    report_id VARCHAR(64) UNIQUE NOT NULL COMMENT '报告唯一ID',
                    chat_name VARCHAR(255) NOT NULL COMMENT '群聊名称',
                    message_count INT NOT NULL COMMENT '消息总数',
                    user_id VARCHAR(64) NOT NULL COMMENT '创建者会话ID',
                    
                    selected_words JSON NOT NULL COMMENT '选中的热词列表（包含word, freq, samples, contributors等）',
                    statistics JSON NOT NULL COMMENT '关键统计数据（rankings, timeDistribution等）',
                    ai_comments JSON COMMENT 'AI锐评内容 {word: comment}',
                    
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    
                    INDEX idx_chat_name (chat_name),
                    INDEX idx_created_at (created_at),
                    INDEX idx_user_id (user_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            
            conn.commit()
            logger.info("✅ 数据库初始化成功")
        except Exception as e:
            logger.error(f"❌ 数据库初始化失败: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    def create_report(self, report_id: str, chat_name: str, message_count: int,
                     selected_words: List[Dict], statistics: Dict, 
                     ai_comments: Optional[Dict] = None, user_id: str = 'anonymous') -> bool:
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            sql = """
                INSERT INTO reports 
                (report_id, chat_name, message_count, user_id, selected_words, statistics, ai_comments)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(sql, (
                report_id,
                chat_name,
                message_count,
                user_id,
                json.dumps(selected_words, ensure_ascii=False),
                json.dumps(statistics, ensure_ascii=False),
                json.dumps(ai_comments, ensure_ascii=False) if ai_comments else None
            ))
            
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"创建报告失败: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()
    
    def create_personal_report(self, report_id: str, user_name: str, chat_name: str,
                              report_data: Dict, user_id: str = 'anonymous') -> bool:
        """保存个人报告到数据库"""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # 检查personal_reports表是否存在，如果不存在则创建
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS personal_reports (
                    report_id VARCHAR(255) PRIMARY KEY,
                    user_name VARCHAR(255) NOT NULL,
                    chat_name VARCHAR(255) NOT NULL,
                    user_id VARCHAR(255) DEFAULT 'anonymous',
                    report_data TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            
            sql = """
                INSERT INTO personal_reports 
                (report_id, user_name, chat_name, user_id, report_data)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                user_name = VALUES(user_name),
                chat_name = VALUES(chat_name),
                report_data = VALUES(report_data),
                updated_at = CURRENT_TIMESTAMP
            """
            cursor.execute(sql, (
                report_id,
                user_name,
                chat_name,
                user_id,
                json.dumps(report_data, ensure_ascii=False)
            ))
            
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"创建个人报告失败: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()
    
    def get_personal_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        """获取个人报告"""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            
            sql = "SELECT * FROM personal_reports WHERE report_id = %s"
            cursor.execute(sql, (report_id,))
            result = cursor.fetchone()
            
            if result and result.get('report_data'):
                result['report_data'] = json.loads(result['report_data'])
            
            return result
        except Exception as e:
            logger.error(f"获取个人报告失败: {e}")
            return None
        finally:
            if conn:
                conn.close()
    
    def get_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            
            sql = "SELECT * FROM reports WHERE report_id = %s"
            cursor.execute(sql, (report_id,))
            result = cursor.fetchone()
            
            if result:
                # 解析JSON字段
                if result.get('selected_words'):
                    result['selected_words'] = json.loads(result['selected_words'])
                if result.get('statistics'):
                    result['statistics'] = json.loads(result['statistics'])
                if result.get('ai_comments'):
                    result['ai_comments'] = json.loads(result['ai_comments'])
            
            return result
        except Exception as e:
            logger.error(f"获取报告失败: {e}")
            return None
        finally:
            if conn:
                conn.close()
    
    def list_reports(self, page: int = 1, page_size: int = 20, 
                    chat_name: Optional[str] = None, user_id: Optional[str] = None) -> Dict[str, Any]:
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            
            # 构建查询条件
            where_conditions = []
            params = []
            
            if user_id:
                where_conditions.append("user_id = %s")
                params.append(user_id)
            
            if chat_name:
                where_conditions.append("chat_name LIKE %s")
                params.append(f"%{chat_name}%")
            
            where_clause = ""
            if where_conditions:
                where_clause = "WHERE " + " AND ".join(where_conditions)
            
            count_sql = f"SELECT COUNT(*) as total FROM reports {where_clause}"
            cursor.execute(count_sql, params)
            total = cursor.fetchone()['total']
            
            offset = (page - 1) * page_size
            data_sql = f"""
                SELECT id, report_id, chat_name, message_count, 
                       created_at, updated_at
                FROM reports 
                {where_clause}
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """
            cursor.execute(data_sql, params + [page_size, offset])
            data = cursor.fetchall()
            
            return {
                'data': data,
                'total': total,
                'page': page,
                'page_size': page_size
            }
        except Exception as e:
            logger.error(f"查询报告列表失败: {e}")
            return {'data': [], 'total': 0, 'page': page, 'page_size': page_size}
        finally:
            if conn:
                conn.close()
    
    def delete_report(self, report_id: str) -> bool:
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            sql = "DELETE FROM reports WHERE report_id = %s"
            cursor.execute(sql, (report_id,))
            
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"删除报告失败: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()
    
    def get_cached_image(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """获取缓存的图片数据"""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            
            # 确保缓存表存在
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS image_cache (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    cache_key VARCHAR(255) UNIQUE NOT NULL,
                    image_url LONGTEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_cache_key (cache_key)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            
            sql = "SELECT cache_key, image_url, created_at FROM image_cache WHERE cache_key = %s"
            cursor.execute(sql, (cache_key,))
            result = cursor.fetchone()
            
            return result
        except Exception as e:
            logger.error(f"获取缓存图片失败: {e}")
            return None
        finally:
            if conn:
                conn.close()
    
    def save_image_cache(self, cache_key: str, image_data: str) -> str:
        """保存图片缓存"""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # 确保缓存表存在
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS image_cache (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    cache_key VARCHAR(255) UNIQUE NOT NULL,
                    image_url LONGTEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_cache_key (cache_key)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            
            sql = """
                INSERT INTO image_cache (cache_key, image_url)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE 
                    image_url = VALUES(image_url),
                    created_at = CURRENT_TIMESTAMP
            """
            cursor.execute(sql, (cache_key, image_data))
            
            conn.commit()
            return image_data
        except Exception as e:
            logger.error(f"保存缓存图片失败: {e}")
            if conn:
                conn.rollback()
            return image_data
        finally:
            if conn:
                conn.close()
