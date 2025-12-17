#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JSON 文件存储服务
"""

import json
import os
import sys
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path

# 添加父目录到路径以导入 logger
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from logger import get_logger

logger = get_logger(__name__)


class JSONStorageService:
    
    def __init__(self, storage_dir: str = None):
        if storage_dir is None:
            project_root = Path(__file__).parent.parent
            storage_dir = project_root / "runtime_outputs" / "reports_db"
        
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # 索引文件路径
        self.index_file = self.storage_dir / "index.json"
        self._ensure_index()
    
    def _ensure_index(self):
        if not self.index_file.exists():
            self.index_file.write_text(json.dumps([], ensure_ascii=False, indent=2), encoding='utf-8')
    
    def _load_index(self) -> List[Dict]:
        try:
            return json.loads(self.index_file.read_text(encoding='utf-8'))
        except:
            return []
    
    def _save_index(self, index: List[Dict]):
        self.index_file.write_text(
            json.dumps(index, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )
    
    def _get_report_file(self, report_id: str) -> Path:
        return self.storage_dir / f"{report_id}.json"
    
    def _get_image_cache_file(self, cache_key: str) -> Path:
        images_dir = self.storage_dir / "images"
        images_dir.mkdir(exist_ok=True)
        return images_dir / f"{cache_key}.json"
    
    def init_database(self):
        self._ensure_index()
        logger.info(f"✅ JSON 存储初始化成功: {self.storage_dir}")
    
    def create_report(self, report_id: str, chat_name: str, message_count: int,
                     selected_words: List[Dict], statistics: Dict, 
                     ai_comments: Optional[Dict] = None, user_id: str = 'anonymous') -> bool:
        try:
            report_data = {
                "report_id": report_id,
                "chat_name": chat_name,
                "message_count": message_count,
                "user_id": user_id,
                "selected_words": selected_words,
                "statistics": statistics,
                "ai_comments": ai_comments,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            
            report_file = self._get_report_file(report_id)
            report_file.write_text(
                json.dumps(report_data, ensure_ascii=False, indent=2),
                encoding='utf-8'
            )
            
            index = self._load_index()
            index_entry = {
                "report_id": report_id,
                "chat_name": chat_name,
                "message_count": message_count,
                "user_id": user_id,
                "created_at": report_data["created_at"],
                "updated_at": report_data["updated_at"]
            }
            
            existing_idx = next((i for i, r in enumerate(index) if r["report_id"] == report_id), None)
            if existing_idx is not None:
                index[existing_idx] = index_entry
            else:
                index.append(index_entry)
            
            self._save_index(index)
            return True
            
        except Exception as e:
            logger.error(f"❌ 创建报告失败: {e}")
            return False
    
    def get_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        try:
            report_file = self._get_report_file(report_id)
            if not report_file.exists():
                return None
            
            report_data = json.loads(report_file.read_text(encoding='utf-8'))
            
            # 转换日期格式以兼容前端
            if 'created_at' in report_data:
                report_data['created_at'] = datetime.fromisoformat(report_data['created_at'])
            if 'updated_at' in report_data:
                report_data['updated_at'] = datetime.fromisoformat(report_data['updated_at'])
            
            return report_data
            
        except Exception as e:
            logger.error(f"❌ 获取报告失败: {e}")
            return None
    
    def create_personal_report(self, report_id: str, user_name: str, chat_name: str,
                              report_data: Dict, user_id: str = 'anonymous') -> bool:
        """保存个人报告"""
        try:
            personal_data = {
                "report_id": report_id,
                "user_name": user_name,
                "chat_name": chat_name,
                "user_id": user_id,
                "report_data": report_data,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            
            personal_dir = self.storage_dir / "personal_reports"
            personal_dir.mkdir(exist_ok=True)
            
            report_file = personal_dir / f"{report_id}.json"
            report_file.write_text(
                json.dumps(personal_data, ensure_ascii=False, indent=2),
                encoding='utf-8'
            )
            
            return True
        except Exception as e:
            logger.error(f"❌ 创建个人报告失败: {e}")
            return False
    
    def get_personal_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        """获取个人报告"""
        try:
            personal_dir = self.storage_dir / "personal_reports"
            report_file = personal_dir / f"{report_id}.json"
            if not report_file.exists():
                return None
            
            data = json.loads(report_file.read_text(encoding='utf-8'))
            if 'created_at' in data:
                data['created_at'] = datetime.fromisoformat(data['created_at'])
            if 'updated_at' in data:
                data['updated_at'] = datetime.fromisoformat(data['updated_at'])
            
            return data
        except Exception as e:
            logger.error(f"❌ 获取个人报告失败: {e}")
            return None
    
    def list_reports(self, page: int = 1, page_size: int = 20, 
                    chat_name: Optional[str] = None, user_id: Optional[str] = None) -> Dict[str, Any]:
        try:
            index = self._load_index()
            
            filtered = index
            
            if user_id:
                filtered = [r for r in filtered if r.get("user_id") == user_id]
            
            if chat_name:
                filtered = [r for r in filtered if chat_name.lower() in r["chat_name"].lower()]
            
            filtered.sort(key=lambda x: x["created_at"], reverse=True)
            
            total = len(filtered)
            start = (page - 1) * page_size
            end = start + page_size
            data = filtered[start:end]
            
            for item in data:
                if 'created_at' in item:
                    item['created_at'] = datetime.fromisoformat(item['created_at'])
                if 'updated_at' in item:
                    item['updated_at'] = datetime.fromisoformat(item['updated_at'])
            
            return {
                'data': data,
                'total': total,
                'page': page,
                'page_size': page_size
            }
            
        except Exception as e:
            logger.error(f"❌ 查询报告列表失败: {e}")
            return {'data': [], 'total': 0, 'page': page, 'page_size': page_size}
    
    def delete_report(self, report_id: str) -> bool:
        try:
            report_file = self._get_report_file(report_id)
            if report_file.exists():
                report_file.unlink()
            
            index = self._load_index()
            index = [r for r in index if r["report_id"] != report_id]
            self._save_index(index)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 删除报告失败: {e}")
            return False
    
    def get_cached_image(self, cache_key: str) -> Optional[Dict[str, Any]]:
        try:
            cache_file = self._get_image_cache_file(cache_key)
            if not cache_file.exists():
                return None
            
            cache_data = json.loads(cache_file.read_text(encoding='utf-8'))
            
            if 'created_at' in cache_data:
                cache_data['created_at'] = datetime.fromisoformat(cache_data['created_at'])
            
            return cache_data
            
        except Exception as e:
            logger.error(f"❌ 获取缓存图片失败: {e}")
            return None
    
    def save_image_cache(self, cache_key: str, image_data: str) -> str:
        try:
            cache_data = {
                "cache_key": cache_key,
                "image_url": image_data,
                "created_at": datetime.now().isoformat()
            }
            
            cache_file = self._get_image_cache_file(cache_key)
            cache_file.write_text(
                json.dumps(cache_data, ensure_ascii=False),
                encoding='utf-8'
            )
            
            return image_data
            
        except Exception as e:
            logger.error(f"❌ 保存缓存图片失败: {e}")
            return image_data
