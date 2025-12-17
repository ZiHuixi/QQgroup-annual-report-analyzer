# -*- coding: utf-8 -*-
"""
个人年度报告分析器
分析指定用户在群聊中的年度数据
"""

import re
import jieba
from datetime import datetime, timezone, timedelta
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Tuple
from logger import get_logger
from utils import parse_datetime, clean_text
import os

logger = get_logger(__name__)

# 停用词缓存
_STOPWORDS_CACHE = None

def load_stopwords_for_personal():
    """加载停用词（不依赖config）"""
    global _STOPWORDS_CACHE
    if _STOPWORDS_CACHE is not None:
        return _STOPWORDS_CACHE
    
    base_dir = os.path.dirname(__file__)
    candidate_paths = [
        os.path.join(base_dir, 'resources', 'baidu_stopwords.txt'),
        os.path.join(base_dir, 'backend', 'resources', 'baidu_stopwords.txt'),
    ]
    
    stopwords_path = None
    for path in candidate_paths:
        if os.path.exists(path):
            stopwords_path = path
            break
    
    if not stopwords_path:
        logger.warning(f"停用词文件不存在于任何候选路径: {candidate_paths}")
        _STOPWORDS_CACHE = set()
        return _STOPWORDS_CACHE
    
    try:
        with open(stopwords_path, 'r', encoding='utf-8') as f:
            words = {line.strip() for line in f if line.strip() and not line.startswith('#')}
        _STOPWORDS_CACHE = words
        logger.info(f"📚 已加载停用词 {len(words)} 个 from {stopwords_path}")
        return _STOPWORDS_CACHE
    except Exception as e:
        logger.error(f"❌ 加载停用词文件失败: {e}")
        _STOPWORDS_CACHE = set()
        return _STOPWORDS_CACHE


class PersonalAnalyzer:
    """个人年度报告分析器"""
    
    def __init__(self, data: Dict, target_name: str, use_stopwords: bool = False):
        """
        初始化个人分析器
        
        Args:
            data: 群聊数据（包含messages和chatInfo）
            target_name: 要分析的用户名称
            use_stopwords: 是否使用停用词库
        """
        self.data = data
        self.messages = data.get('messages', [])
        self.chat_name = data.get('chatName', data.get('chatInfo', {}).get('name', '未知群聊'))
        self.target_name = target_name
        self.use_stopwords = use_stopwords
        self.stopwords = load_stopwords_for_personal() if use_stopwords else set()
        
        # 构建用户映射
        self._build_user_mapping()
        
        # 查找目标用户
        self.target_uin = self._find_target_user()
        if not self.target_uin:
            raise ValueError(f"未找到用户: {target_name}")
        
        # 过滤出目标用户的消息
        self.user_messages = [msg for msg in self.messages 
                             if msg.get('sender', {}).get('uin') == self.target_uin]
        
        if not self.user_messages:
            raise ValueError(f"用户 {target_name} 在指定时间范围内没有发言")
        
        logger.info(f"📊 开始分析用户: {target_name} (UIN: {self.target_uin})")
        logger.info(f"📝 找到 {len(self.user_messages)} 条消息")
        
        # 初始化统计变量
        self._init_stats()
    
    def _build_user_mapping(self):
        """构建用户UIN到名称的映射"""
        self.uin_to_name = {}
        uin_names = defaultdict(list)
        uin_member_names = {}
        
        for msg in self.messages:
            sender = msg.get('sender', {})
            uin = sender.get('uin')
            name = (sender.get('name') or '').strip()
            
            if uin and name:
                if not uin_names[uin] or uin_names[uin][-1] != name:
                    uin_names[uin].append(name)
            
            if uin:
                raw_msg = msg.get('rawMessage', {})
                send_member_name = raw_msg.get('sendMemberName', '').strip()
                if send_member_name:
                    uin_member_names[uin] = send_member_name
        
        for uin, names in uin_names.items():
            chosen_name = None
            for name in reversed(names):
                if name != str(uin):
                    chosen_name = name
                    break
            if chosen_name is None and names:
                chosen_name = names[-1]
            
            if chosen_name is None and uin in uin_member_names:
                chosen_name = uin_member_names[uin]
            
            if chosen_name is None or chosen_name == str(uin):
                chosen_name = f"用户{uin}"
            
            self.uin_to_name[uin] = chosen_name
    
    def _find_target_user(self) -> Optional[str]:
        """查找目标用户的UIN"""
        # 精确匹配
        for uin, name in self.uin_to_name.items():
            if name == self.target_name:
                return uin
        
        # 模糊匹配（包含）
        for uin, name in self.uin_to_name.items():
            if self.target_name in name or name in self.target_name:
                logger.info(f"🔍 模糊匹配到用户: {name} (UIN: {uin})")
                return uin
        
        return None
    
    def _init_stats(self):
        """初始化统计变量"""
        self.total_messages = 0
        self.total_chars = 0
        self.message_types = Counter()  # text, emoji, image, voice, file
        self.emoji_count = 0
        self.image_count = 0
        self.voice_count = 0
        self.file_count = 0
        
        # 时间相关
        self.active_days = set()
        self.daily_message_count = Counter()
        self.hour_distribution = Counter()
        self.night_messages = 0  # 22:00-06:00
        self.first_message_time = None
        self.last_message_time = None
        
        # 互动相关
        self.reply_count = 0
        self.replied_count = 0
        self.at_count = 0
        self.ated_count = 0
        self.at_targets = Counter()  # 被@的人
        self.at_by = Counter()  # @我的人
        
        # 回复关系
        self.reply_to = Counter()  # 我回复了谁
        self.replied_by = Counter()  # 谁回复了我
        self.reply_intervals = defaultdict(list)  # 与不同人的回复间隔
        
        # 复读相关
        self.repeat_count = 0  # 与上一条消息完全相同
        self.chain_repeat_count = 0  # 连续3人以上复读的参与次数
        
        # 词频
        self.word_freq = Counter()
        self.word_samples = defaultdict(list)
        
        # 消息内容
        self.all_messages = []  # 存储所有消息文本
        self.long_messages = 0  # >200字的消息
        
        # 特殊消息
        self.most_replied_message = None  # 最多人回复的消息
        self.most_emoji_message = None  # 表情反应最多的消息
        self.chain_repeat_message = None  # 引发复读的消息
        
        # 构建msgid到发送者的映射（用于回复分析）
        self.msgid_to_sender = {}
        for msg in self.messages:
            msg_id = msg.get('messageId')
            sender_uin = msg.get('sender', {}).get('uin')
            if msg_id and sender_uin:
                self.msgid_to_sender[msg_id] = sender_uin
    
    def analyze(self):
        """执行分析"""
        logger.info("🔍 开始分析个人数据...")
        
        # 先遍历所有消息，统计@和回复关系（避免重复计算）
        msg_id_to_user_msg = {msg.get('messageId'): msg for msg in self.user_messages}
        
        for msg in self.messages:
            sender_uin = msg.get('sender', {}).get('uin')
            if not sender_uin or str(sender_uin) == str(self.target_uin):
                continue  # 跳过目标用户自己的消息
            
            elements = msg.get('rawMessage', {}).get('elements', [])
            for element in elements:
                elem_type = element.get('elementType')
                
                # 检查是否@了目标用户
                if elem_type == 1:  # 文本元素
                    text_elem = element.get('textElement', {})
                    at_uid = text_elem.get('atUid', '')
                    if str(at_uid) == str(self.target_uin):
                        self.ated_count += 1
                        self.at_by[str(sender_uin)] += 1
                
                # 检查是否回复了目标用户
                elif elem_type == 7:  # 回复元素
                    reply_elem = element.get('replyElement', {})
                    ref_msg_id = reply_elem.get('sourceMsgIdInRecords') or reply_elem.get('replayMsgId')
                    if ref_msg_id and ref_msg_id in msg_id_to_user_msg:
                        self.replied_count += 1
                        self.replied_by[str(sender_uin)] += 1
        
        # 再遍历用户消息，统计用户自己的数据
        prev_message_text = None
        prev_sender_uin = None
        repeat_chain = []  # 当前复读链
        
        for i, msg in enumerate(self.user_messages):
            # 基本统计
            self.total_messages += 1
            
            # 时间分析
            timestamp = msg.get('timestamp', '')
            msg_dt = parse_datetime(timestamp)
            
            # 重置当前消息的类型标记
            current_msg_has_emoji = False
            current_msg_has_image = False
            
            if msg_dt:
                if self.first_message_time is None or msg_dt < self.first_message_time:
                    self.first_message_time = msg_dt
                if self.last_message_time is None or msg_dt > self.last_message_time:
                    self.last_message_time = msg_dt
                
                # 活跃天数
                date_str = msg_dt.strftime('%Y-%m-%d')
                self.active_days.add(date_str)
                self.daily_message_count[date_str] += 1
                
                # 小时分布
                hour = msg_dt.hour
                self.hour_distribution[hour] += 1
                
                # 夜猫子指数（22:00-06:00）
                if hour >= 22 or hour < 6:
                    self.night_messages += 1
            
            # 内容分析
            content = msg.get('content', {})
            text = content.get('text', '') if isinstance(content, dict) else ''
            
            # 提取@信息
            at_contents = []
            elements = msg.get('rawMessage', {}).get('elements', [])
            for element in elements:
                elem_type = element.get('elementType')
                
                if elem_type == 1:  # 文本元素
                    text_elem = element.get('textElement', {})
                    at_type = text_elem.get('atType', 0)
                    at_uid = text_elem.get('atUid', '')
                    at_content = text_elem.get('content', '')
                    
                    if at_type > 0 and at_uid and str(at_uid) != '0':
                        self.at_count += 1
                        at_target_uin = str(at_uid)
                        self.at_targets[at_target_uin] += 1
                        if at_content:
                            at_contents.append(at_content)
                
                elif elem_type == 2:  # 图片元素
                    pic_elem = element.get('picElement', {})
                    summary = pic_elem.get('summary', '')
                    if summary and summary.startswith('[') and summary.endswith(']'):
                        current_msg_has_emoji = True
                        self.message_types['emoji'] += 1
                        self.emoji_count += 1
                    else:
                        current_msg_has_image = True
                        self.message_types['image'] += 1
                        self.image_count += 1
                
                elif elem_type == 7:  # 回复元素
                    self.reply_count += 1
                    reply_elem = element.get('replyElement', {})
                    target_uin = reply_elem.get('senderUid')
                    
                    if not target_uin or target_uin == '0':
                        ref_msg_id = reply_elem.get('sourceMsgIdInRecords') or reply_elem.get('replayMsgId')
                        if ref_msg_id:
                            target_uin = self.msgid_to_sender.get(ref_msg_id)
                    
                    if target_uin and str(target_uin) != '0' and str(target_uin) != self.target_uin:
                        target_uin_str = str(target_uin)
                        self.reply_to[target_uin_str] += 1
                        
                        # 计算回复间隔（需要找到被回复的消息时间）
                        ref_msg_id = reply_elem.get('sourceMsgIdInRecords') or reply_elem.get('replayMsgId')
                        if ref_msg_id:
                            for prev_msg in self.messages:
                                if prev_msg.get('messageId') == ref_msg_id:
                                    prev_msg_dt = parse_datetime(prev_msg.get('timestamp', ''))
                                    if prev_msg_dt and msg_dt:
                                        interval = (msg_dt - prev_msg_dt).total_seconds()
                                        self.reply_intervals[target_uin_str].append(interval)
                                    break
            
            # 文本处理
            cleaned = clean_text(text, at_contents)
            
            # 消息类型统计（如果没有任何特殊类型，则视为纯文字）
            if not current_msg_has_emoji and not current_msg_has_image:
                if cleaned:
                    self.message_types['text'] += 1
            
            if cleaned:
                self.all_messages.append(cleaned)
                self.total_chars += len(cleaned)
                
                # 超长消息
                if len(cleaned) > 200:
                    self.long_messages += 1
                
                # 词频分析
                words = list(jieba.cut(cleaned))
                for word in words:
                    word = word.strip()
                    if not word:
                        continue
                    if self.use_stopwords and word in self.stopwords:
                        continue
                    self.word_freq[word] += 1
                    if len(self.word_samples[word]) < 3:
                        self.word_samples[word].append(cleaned)
            
            # 消息类型统计（如果没有任何特殊类型，则视为纯文字）
            if not current_msg_has_emoji and not current_msg_has_image:
                if cleaned:
                    self.message_types['text'] += 1
            
            # 复读检测
            if prev_message_text and cleaned and cleaned == prev_message_text:
                self.repeat_count += 1
            
            # 复读链检测（需要检查前后消息）
            if i > 0 and i < len(self.user_messages) - 1:
                prev_msg = self.user_messages[i-1]
                next_msg = self.user_messages[i+1] if i+1 < len(self.user_messages) else None
                
                prev_text = clean_text(prev_msg.get('content', {}).get('text', ''), [])
                next_text = clean_text(next_msg.get('content', {}).get('text', ''), []) if next_msg else None
                
                if cleaned and prev_text and cleaned == prev_text:
                    # 检查是否形成复读链
                    repeat_chain.append(i)
                    if next_text and next_text == cleaned:
                        # 连续复读
                        if len(repeat_chain) >= 2:
                            self.chain_repeat_count += 1
            
            # 更新前一条消息文本（用于复读检测）
            prev_message_text = cleaned if cleaned else None
            prev_sender_uin = self.target_uin
        
        logger.info("✅ 个人数据分析完成")
    
    def export_json(self) -> Dict:
        """导出分析结果为JSON格式"""
        # 计算日期范围
        if self.first_message_time and self.last_message_time:
            date_range = (self.last_message_time - self.first_message_time).days + 1
        else:
            date_range = 365  # 默认一年
        
        # 平均每日发言数
        avg_daily = self.total_messages / date_range if date_range > 0 else 0
        
        # 最活跃的一天
        if self.daily_message_count:
            most_active_date, most_active_count = self.daily_message_count.most_common(1)[0]
        else:
            most_active_date = None
            most_active_count = 0
        
        # 最活跃的小时段
        if self.hour_distribution:
            peak_hour = self.hour_distribution.most_common(1)[0][0]
        else:
            peak_hour = 12
        
        # 夜猫子指数
        night_ratio = (self.night_messages / self.total_messages * 100) if self.total_messages > 0 else 0
        
        # 消息类型占比
        total_typed = sum(self.message_types.values())
        type_ratios = {
            'text': (self.message_types['text'] / total_typed * 100) if total_typed > 0 else 0,
            'emoji': (self.message_types['emoji'] / total_typed * 100) if total_typed > 0 else 0,
            'image': (self.message_types['image'] / total_typed * 100) if total_typed > 0 else 0,
            'voice': (self.message_types.get('voice', 0) / total_typed * 100) if total_typed > 0 else 0,
            'file': (self.message_types.get('file', 0) / total_typed * 100) if total_typed > 0 else 0,
        }
        
        # 表情使用率
        emoji_ratio = (self.emoji_count / self.total_messages * 100) if self.total_messages > 0 else 0
        
        # 单条消息平均字数
        avg_chars_per_msg = (self.total_chars / self.total_messages) if self.total_messages > 0 else 0
        
        # 最常互动对象
        most_interact_uin = None
        most_interact_count = 0
        if self.reply_to:
            most_interact_uin, most_interact_count = self.reply_to.most_common(1)[0]
        
        # 最短回复间隔
        min_interval = None
        min_interval_target = None
        for target_uin, intervals in self.reply_intervals.items():
            if intervals:
                avg_interval = sum(intervals) / len(intervals)
                if min_interval is None or avg_interval < min_interval:
                    min_interval = avg_interval
                    min_interval_target = target_uin
        
        # 最常@的人
        most_at_target_uin = None
        most_at_target_count = 0
        if self.at_targets:
            most_at_target_uin, most_at_target_count = self.at_targets.most_common(1)[0]
        
        # 最常@我的人
        most_at_by_uin = None
        most_at_by_count = 0
        if self.at_by:
            most_at_by_uin, most_at_by_count = self.at_by.most_common(1)[0]
        
        # Top N 高频词
        top_words = []
        for word, freq in self.word_freq.most_common(20):
            top_words.append({
                'word': word,
                'freq': freq,
                'samples': self.word_samples[word][:3]
            })
        
        # 连续出现频率最高的词（需要分析连续出现）
        consecutive_words = self._find_consecutive_words()
        
        # 生成人格化标签
        tags = self._generate_personality_tags(night_ratio, emoji_ratio, self.repeat_count, 
                                               self.chain_repeat_count, avg_chars_per_msg)
        
        result = {
            'user_name': self.target_name,
            'chat_name': self.chat_name,
            'analysis_date': datetime.now().strftime('%Y-%m-%d'),
            
            # 基础统计
            'total_messages': self.total_messages,
            'avg_daily_messages': round(avg_daily, 2),
            'active_days': len(self.active_days),
            'total_days': date_range,
            'active_ratio': round(len(self.active_days) / date_range * 100, 2) if date_range > 0 else 0,
            
            # 时间分析
            'most_active_date': {
                'date': most_active_date,
                'count': most_active_count
            } if most_active_date else None,
            'peak_hour': peak_hour,
            'night_ratio': round(night_ratio, 2),
            'first_message_time': self.first_message_time.strftime('%Y-%m-%d %H:%M:%S') if self.first_message_time else None,
            'last_message_time': self.last_message_time.strftime('%Y-%m-%d %H:%M:%S') if self.last_message_time else None,
            
            # 消息类型
            'message_type_ratios': type_ratios,
            'emoji_ratio': round(emoji_ratio, 2),
            
            # 复读相关
            'repeat_count': self.repeat_count,
            'chain_repeat_count': self.chain_repeat_count,
            'chain_repeat_ratio': round(self.chain_repeat_count / self.total_messages * 100, 2) if self.total_messages > 0 else 0,
            
            # 互动分析
            'at_count': self.at_count,
            'ated_count': self.ated_count,
            'reply_count': self.reply_count,
            'replied_count': self.replied_count,
            'most_interact_user': {
                'name': self.uin_to_name.get(most_interact_uin, '未知用户'),
                'count': most_interact_count
            } if most_interact_uin else None,
            'min_reply_interval_user': {
                'name': self.uin_to_name.get(min_interval_target, '未知用户'),
                'avg_interval_seconds': round(min_interval, 2) if min_interval else None
            } if min_interval_target else None,
            'most_at_target': {
                'name': self.uin_to_name.get(most_at_target_uin, '未知用户'),
                'count': most_at_target_count
            } if most_at_target_uin else None,
            'most_at_by': {
                'name': self.uin_to_name.get(most_at_by_uin, '未知用户'),
                'count': most_at_by_count
            } if most_at_by_uin else None,
            
            # 词频分析
            'top_words': top_words,
            'consecutive_word': consecutive_words,
            'avg_chars_per_msg': round(avg_chars_per_msg, 2),
            'long_messages': self.long_messages,
            
            # 人格化标签
            'personality_tags': tags,
            
            # 小时分布（用于图表）
            'hour_distribution': dict(self.hour_distribution),
        }
        
        return result
    
    def _find_consecutive_words(self) -> Optional[Dict]:
        """查找连续出现频率最高的词"""
        if not self.all_messages:
            return None
        
        word_consecutive_count = Counter()
        for msg_text in self.all_messages:
            words = list(jieba.cut(msg_text))
            prev_word = None
            for word in words:
                word = word.strip()
                if not word or (self.use_stopwords and word in self.stopwords):
                    continue
                if word == prev_word:
                    word_consecutive_count[word] += 1
                prev_word = word
        
        if word_consecutive_count:
            most_consecutive_word, count = word_consecutive_count.most_common(1)[0]
            return {
                'word': most_consecutive_word,
                'count': count
            }
        return None
    
    def _generate_personality_tags(self, night_ratio: float, emoji_ratio: float, 
                                   repeat_count: int, chain_repeat_count: int, 
                                   avg_chars: float) -> List[str]:
        """生成人格化标签"""
        tags = []
        
        # 夜猫子
        if night_ratio > 30:
            tags.append('夜猫子')
        
        # 表情包供应商
        if emoji_ratio > 20:
            tags.append('表情包供应商')
        
        # 潜水大师
        if self.total_messages < 100:
            tags.append('潜水大师')
        
        # 复读机
        if repeat_count > self.total_messages * 0.1:
            tags.append('复读机')
        
        # 秒回王（检查最短回复间隔）
        min_interval = None
        for intervals in self.reply_intervals.values():
            if intervals:
                avg_interval = sum(intervals) / len(intervals)
                if min_interval is None or avg_interval < min_interval:
                    min_interval = avg_interval
        if min_interval and min_interval < 60:
            tags.append('秒回王')
        
        # 话题终结者/话题制造机
        if self.replied_count > self.reply_count * 1.5:
            tags.append('话题制造机')
        elif self.reply_count > self.replied_count * 1.5:
            tags.append('话题终结者')
        
        # 群聊气氛组
        if chain_repeat_count > 10:
            tags.append('群聊气氛组')
        
        if not tags:
            tags.append('群聊活跃成员')
        
        return tags

