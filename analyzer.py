# -*- coding: utf-8 -*-
import os
import re
import random
import string
import math
import jieba
from collections import Counter, defaultdict
import config as cfg
from utils import (
    parse_timestamp,
    parse_datetime,
    clean_text,
    calculate_entropy,
    analyze_single_chars,
)
from logger import get_logger, init_logging

init_logging()

jieba.setLogLevel(jieba.logging.INFO)

logger = get_logger('analyzer')

# 全局缓存停用词，避免重复读取
_STOPWORDS_CACHE = None


def load_stopwords():
    """加载百度停用词库，文件缺失时返回空集合"""
    global _STOPWORDS_CACHE
    if _STOPWORDS_CACHE is not None:
        return _STOPWORDS_CACHE
    
    base_dir = os.path.dirname(__file__)
    # 兼容两种放置方式：项目根目录的 resources/ 和 backend/resources/
    candidate_paths = [
        os.path.join(base_dir, 'resources', 'baidu_stopwords.txt'),
        os.path.join(base_dir, 'backend', 'resources', 'baidu_stopwords.txt'),
    ]

    stopwords_path = None
    for p in candidate_paths:
        if os.path.exists(p):
            stopwords_path = p
            break

    if not stopwords_path:
        logger.warning(f"停用词文件不存在，尝试路径: {candidate_paths}")
        _STOPWORDS_CACHE = set()
        return _STOPWORDS_CACHE

    with open(stopwords_path, 'r', encoding='utf-8') as f:
        words = {line.strip() for line in f if line.strip() and not line.startswith('#')}

    _STOPWORDS_CACHE = words
    logger.info(f"📚 已加载停用词 {len(words)} 个")
    return _STOPWORDS_CACHE


class ChatAnalyzer:
    def __init__(self, data, use_stopwords=False, stopwords=None):
        self.data = data
        self.messages = data.get('messages', [])
        self.chat_name = data.get('chatName', data.get('chatInfo', {}).get('name', '未知群聊'))
        self.use_stopwords = use_stopwords
        self.stopwords = stopwords if stopwords is not None else (load_stopwords() if use_stopwords else set())
        
        # 应用时间范围过滤
        self._filter_messages_by_time()
        self.uin_to_name = {}
        self.msgid_to_sender = {}
        self.word_freq = Counter()
        self.word_samples = defaultdict(list)
        self.word_contributors = defaultdict(Counter)
        self.user_msg_count = Counter()
        self.user_char_count = Counter()
        self.user_char_per_msg = {}
        self.user_image_count = Counter()
        self.user_forward_count = Counter()
        self.user_reply_count = Counter()
        self.user_replied_count = Counter()
        self.user_at_count = Counter()
        self.user_ated_count = Counter()
        self.user_emoji_count = Counter()
        self.user_link_count = Counter()
        self.user_night_count = Counter()
        self.user_morning_count = Counter()
        self.user_repeat_count = Counter()
        self.hour_distribution = Counter()
        self.discovered_words = set()
        self.merged_words = {}
        self.single_char_stats = {}  # 单字统计
        self.cleaned_texts = []  # 缓存清洗后的文本
        self._build_mappings()
    
    def _filter_messages_by_time(self):
        """根据配置的时间范围过滤消息"""
        if cfg.MESSAGE_START_DATE is None and cfg.MESSAGE_END_DATE is None:
            return
        
        from datetime import datetime
        
        # 解析配置的日期
        start_dt = None
        end_dt = None
        
        if cfg.MESSAGE_START_DATE:
            try:
                start_dt = datetime.strptime(cfg.MESSAGE_START_DATE, '%Y-%m-%d')
                start_dt = start_dt.replace(hour=0, minute=0, second=0, microsecond=0)
                # 转换为东八区
                from datetime import timezone, timedelta
                start_dt = start_dt.replace(tzinfo=timezone(timedelta(hours=8)))
            except Exception as e:
                logger.warning(f"起始日期格式错误: {cfg.MESSAGE_START_DATE}, 错误: {e}")
        
        if cfg.MESSAGE_END_DATE:
            try:
                end_dt = datetime.strptime(cfg.MESSAGE_END_DATE, '%Y-%m-%d')
                end_dt = end_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
                # 转换为东八区
                from datetime import timezone, timedelta
                end_dt = end_dt.replace(tzinfo=timezone(timedelta(hours=8)))
            except Exception as e:
                logger.warning(f"结束日期格式错误: {cfg.MESSAGE_END_DATE}, 错误: {e}")
        
        if start_dt is None and end_dt is None:
            return  # 日期解析失败，不过滤
        
        # 过滤消息
        original_count = len(self.messages)
        filtered_messages = []
        
        for msg in self.messages:
            timestamp = msg.get('timestamp', '')
            msg_dt = parse_datetime(timestamp)
            
            if msg_dt is None:
                continue 
            
            # 检查是否在时间范围内
            if start_dt and msg_dt < start_dt:
                continue
            if end_dt and msg_dt > end_dt:
                continue
            
            filtered_messages.append(msg)
        
        self.messages = filtered_messages
        filtered_count = len(self.messages)
        
        if start_dt or end_dt:
            time_range = []
            if start_dt:
                time_range.append(f"从 {cfg.MESSAGE_START_DATE}")
            if end_dt:
                time_range.append(f"到 {cfg.MESSAGE_END_DATE}")
            logger.info(f"⏰ 时间范围过滤: {' '.join(time_range)}")
            logger.info(f"   原始消息: {original_count} 条, 过滤后: {filtered_count} 条")

    def _is_bot_message(self, msg):
        """判断是否为机器人消息（基于 subMsgType）"""
        if not cfg.FILTER_BOT_MESSAGES:
            return False
        
        raw_msg = msg.get('rawMessage', {})
        sub_msg_type = raw_msg.get('subMsgType', 0)
        return sub_msg_type in [577, 65]

    def _build_mappings(self):
        # 构建 uin 到 name 的映射，优先保留有效的 name
        # 先收集每个 uin 的所有 name（按顺序）和 sendMemberName
        uin_names = defaultdict(list)
        uin_member_names = {}  # 存储最后的 sendMemberName
        
        for msg in self.messages:
            if self._is_bot_message(msg):
                continue
            
            sender = msg.get('sender', {})
            uin = sender.get('uin')
            name = sender.get('name', '').strip()
            msg_id = msg.get('messageId')
            
            if uin and name:
                # 只在 name 与上一个不同时添加
                if not uin_names[uin] or uin_names[uin][-1] != name:
                    uin_names[uin].append(name)
            
            # 收集 sendMemberName（保留最后一个）
            if uin:
                raw_msg = msg.get('rawMessage', {})
                send_member_name = raw_msg.get('sendMemberName', '').strip()
                if send_member_name:
                    uin_member_names[uin] = send_member_name
            
            if msg_id and uin:
                self.msgid_to_sender[msg_id] = uin
        
        # 为每个 uin 选择最合适的 name
        for uin, names in uin_names.items():
            # 从后往前找第一个不等于uin的 name
            chosen_name = None
            for name in reversed(names):
                if name != str(uin):
                    chosen_name = name
                    break
            
            # 如果所有 name 都等于 uin，使用 sendMemberName
            if chosen_name is None:
                if uin in uin_member_names:
                    chosen_name = uin_member_names[uin]
                elif names:
                    chosen_name = names[-1]  # 兜底：使用最后一个
            
            if chosen_name:
                self.uin_to_name[uin] = chosen_name

    def get_name(self, uin):
        return self.uin_to_name.get(uin, f"未知用户({uin})")

    def analyze(self):
        logger.info(f"📊 开始分析: {self.chat_name}")
        logger.info(f"📝 消息总数: {len(self.messages)}")
        
        logger.info("🧹 预处理文本...")
        self._preprocess_texts()
        
        logger.info("🔤 分析单字独立性...")
        self.single_char_stats = analyze_single_chars(self.cleaned_texts)
        
        logger.info("🔍 新词发现...")
        self._discover_new_words()
        
        logger.info("🔗 词组合并...")
        self._merge_word_pairs()
        
        logger.info("📈 分词统计...")
        self._tokenize_and_count()
        
        logger.info("🎮 趣味统计...")
        self._fun_statistics()
        
        logger.info("🧹 过滤整理...")
        self._filter_results()
        
        logger.info("✅ 分析完成!")

    def _preprocess_texts(self):
        """预处理所有文本"""
        skipped = 0
        bot_filtered = 0
        for msg in self.messages:
            # 跳过机器人消息
            if self._is_bot_message(msg):
                bot_filtered += 1
                continue
            
            content = msg.get('content', {})
            text = content.get('text', '') if isinstance(content, dict) else ''
            cleaned = clean_text(text)
            if cleaned and len(cleaned) >= 1:
                self.cleaned_texts.append(cleaned)
            elif text:
                skipped += 1
        
        if cfg.FILTER_BOT_MESSAGES and bot_filtered > 0:
            logger.debug(f"有效文本: {len(self.cleaned_texts)} 条, 跳过: {skipped} 条, 过滤机器人: {bot_filtered} 条")
        else:
            logger.debug(f"有效文本: {len(self.cleaned_texts)} 条, 跳过: {skipped} 条")

    def _discover_new_words(self):
        """新词发现"""
        ngram_freq = Counter()
        left_neighbors = defaultdict(Counter)
        right_neighbors = defaultdict(Counter)
        total_chars = 0
        
        for text in self.cleaned_texts:
            sentences = re.split(r'[，。！？、；：""''（）\s\n\r,\.!?\(\)]', text)
            for sentence in sentences:
                sentence = sentence.strip()
                if len(sentence) < 2:
                    continue
                total_chars += len(sentence)
                
                for n in range(2, min(6, len(sentence) + 1)):
                    for i in range(len(sentence) - n + 1):
                        ngram = sentence[i:i+n]
                        # 只跳过纯空格
                        if not ngram.strip():
                            continue
                        ngram_freq[ngram] += 1
                        if i > 0:
                            left_neighbors[ngram][sentence[i-1]] += 1
                        else:
                            left_neighbors[ngram]['<BOS>'] += 1
                        if i + n < len(sentence):
                            right_neighbors[ngram][sentence[i+n]] += 1
                        else:
                            right_neighbors[ngram]['<EOS>'] += 1
        
        for word, freq in ngram_freq.items():
            if freq < cfg.NEW_WORD_MIN_FREQ:
                continue
            
            # 邻接熵
            left_ent = calculate_entropy(left_neighbors[word])
            right_ent = calculate_entropy(right_neighbors[word])
            min_ent = min(left_ent, right_ent)
            if min_ent < cfg.ENTROPY_THRESHOLD:
                continue
            
            # PMI
            min_pmi = float('inf')
            for i in range(1, len(word)):
                left_freq = ngram_freq.get(word[:i], 0)
                right_freq = ngram_freq.get(word[i:], 0)
                if left_freq > 0 and right_freq > 0:
                    pmi = math.log2((freq * total_chars) / (left_freq * right_freq + 1e-10))
                    min_pmi = min(min_pmi, pmi)
            
            if min_pmi == float('inf'):
                min_pmi = 0
            
            if min_pmi < cfg.PMI_THRESHOLD:
                continue
            
            self.discovered_words.add(word)
        
        for word in self.discovered_words:
            jieba.add_word(word, freq=1000)
        
        logger.debug(f"发现 {len(self.discovered_words)} 个新词")

    def _merge_word_pairs(self):
        bigram_counter = Counter()
        word_right_counter = Counter()
        
        for text in self.cleaned_texts:
            words = [w for w in jieba.cut(text) if w.strip()]
            for i in range(len(words) - 1):
                w1, w2 = words[i].strip(), words[i+1].strip()
                if not w1 or not w2:
                    continue
                if re.match(r'^[\d\W]+$', w1) or re.match(r'^[\d\W]+$', w2):
                    continue
                bigram_counter[(w1, w2)] += 1
                word_right_counter[w1] += 1
        
        for (w1, w2), count in bigram_counter.items():
            merged = w1 + w2
            if len(merged) > cfg.MERGE_MAX_LEN:
                continue
            if count < cfg.MERGE_MIN_FREQ:
                continue
            
            # 条件概率 P(w2|w1)
            if word_right_counter[w1] > 0:
                prob = count / word_right_counter[w1]
                if prob >= cfg.MERGE_MIN_PROB:
                    self.merged_words[merged] = (w1, w2, count, prob)
                    jieba.add_word(merged, freq=count * 1000)
        
        logger.debug(f"合并 {len(self.merged_words)} 个词组")
        
        if self.merged_words:
            sorted_merges = sorted(self.merged_words.items(), key=lambda x: -x[1][2])[:10]
            for merged, (w1, w2, cnt, prob) in sorted_merges:
                logger.debug(f"  {merged}: {w1}+{w2} ({cnt}次, {prob:.0%})")

    def _tokenize_and_count(self):
        for idx, msg in enumerate(self.messages):
            if self._is_bot_message(msg):
                continue
            
            sender_uin = msg.get('sender', {}).get('uin')
            content = msg.get('content', {})
            text = content.get('text', '') if isinstance(content, dict) else ''
            original_text = text
            cleaned = clean_text(text)
            
            if not cleaned:
                continue
            
            words = list(jieba.cut(cleaned))
            
            for word in words:
                word = word.strip()
                if not word:
                    continue
                
                if self.use_stopwords and word in self.stopwords:
                    continue

                # 提前过滤黑名单（性能优化：避免统计后再过滤）
                if word in cfg.BLACKLIST:
                    continue
                
                self.word_freq[word] += 1
                if sender_uin:
                    self.word_contributors[word][sender_uin] += 1
                if len(self.word_samples[word]) < cfg.SAMPLE_COUNT * 3:
                    self.word_samples[word].append(cleaned)

    def _fun_statistics(self):
        """趣味统计"""
        prev_clean = None  
        prev_sender = None
        
        for msg in self.messages:
            if self._is_bot_message(msg):
                continue
            
            sender_uin = msg.get('sender', {}).get('uin')
            if not sender_uin:
                continue
            
            content = msg.get('content', {})
            text = content.get('text', '') if isinstance(content, dict) else ''
            timestamp = msg.get('timestamp', '')
            raw = msg.get('rawMessage', {})
            elements = raw.get('elements', [])
            
            self.user_msg_count[sender_uin] += 1
            clean = clean_text(text)
            self.user_char_count[sender_uin] += len(clean)
            
            has_image = False
            is_emoji_image = False
            has_forward = False
            has_link = False
            emoji_count_from_elements = 0
            
            for elem in elements:
                elem_type = elem.get('elementType')
                
                # 跳过回复元素
                if elem_type == 7:
                    continue
                
                # 图片元素 
                if elem_type == 2:
                    has_image = True
                    pic_elem = elem.get('picElement', {})
                    summary = pic_elem.get('summary', '')
                    # 检查是否为表情图片
                    if summary and summary.startswith('[') and summary.endswith(']'):
                        is_emoji_image = True
                        emoji_count_from_elements += 1
                
                # 文本元素
                elif elem_type == 1:
                    text_elem = elem.get('textElement', {})
                    
                    # @统计
                    at_type = text_elem.get('atType', 0)
                    at_uid = text_elem.get('atUid', '')
                    if at_type > 0 and at_uid and at_uid != '0':
                        self.user_at_count[sender_uin] += 1
                        self.user_ated_count[at_uid] += 1
                    
                    # 链接统计（文本中的链接）
                    if not has_link:
                        text_content = text_elem.get('content', '')
                        if re.search(r'https?://', text_content):
                            has_link = True
                
                # 链接元素
                elif elem_type == 10:
                    has_link = True
                
                # 转发元素
                elif elem_type == 16 and 'multiForwardMsgElement' in elem:
                    has_forward = True
            
            # ========== 图片统计（content.resources 中有图片 且 非表情） ==========
            resources = content.get('resources', []) if isinstance(content, dict) else []
            has_image_resource = any(res.get('type') == 'image' for res in resources)
            if has_image_resource and not is_emoji_image:
                self.user_image_count[sender_uin] += 1
            
            # ========== 转发统计 ==========
            if has_forward:
                self.user_forward_count[sender_uin] += 1
            
            # ========== 回复统计 ==========
            reply_info = content.get('reply') if isinstance(content, dict) else None
            if reply_info:
                self.user_reply_count[sender_uin] += 1
                ref_msg_id = reply_info.get('referencedMessageId')
                if ref_msg_id and ref_msg_id in self.msgid_to_sender:
                    target_uin = self.msgid_to_sender[ref_msg_id]
                    self.user_replied_count[target_uin] += 1
            
            # ========== 表情统计 ==========
            # content.emojis 中的QQ表情
            emojis = content.get('emojis', []) if isinstance(content, dict) else []
            emoji_count = len(emojis) + emoji_count_from_elements
            if emoji_count > 0:
                self.user_emoji_count[sender_uin] += emoji_count
            
            # ========== 链接统计 ==========
            if has_link:
                self.user_link_count[sender_uin] += 1
            
            # ========== 时段统计 ==========
            hour = parse_timestamp(timestamp)
            if hour is not None:
                self.hour_distribution[hour] += 1
                if hour in cfg.NIGHT_OWL_HOURS:
                    self.user_night_count[sender_uin] += 1
                if hour in cfg.EARLY_BIRD_HOURS:
                    self.user_morning_count[sender_uin] += 1
            
            # ========== 复读统计 ==========
            if clean and len(clean) >= 2:
                if clean == prev_clean and sender_uin != prev_sender:
                    self.user_repeat_count[sender_uin] += 1
            
            prev_clean = clean if clean else prev_clean
            prev_sender = sender_uin
        
        # ========== 计算人均字数（保留1位小数） ==========
        for uin in self.user_msg_count:
            msg_count = self.user_msg_count[uin]
            char_count = self.user_char_count[uin]
            if msg_count >= 10:
                self.user_char_per_msg[uin] = round(char_count / msg_count, 1)


    def _filter_results(self):
        """过滤结果"""
        filtered_freq = Counter()
        
        for word, freq in self.word_freq.items():
            if len(word) < cfg.MIN_WORD_LEN or len(word) > cfg.MAX_WORD_LEN:
                continue
            if freq < cfg.MIN_FREQ:
                continue
            
            if word in cfg.WHITELIST:
                filtered_freq[word] = freq
                continue
            
            if word in cfg.BLACKLIST:
                continue
            
            # 单字特殊处理
            if len(word) == 1:
                # 单个符号跳过（但数字/字母走单字统计）
                if word in string.punctuation or word in '，。！？；：、""''（）【】':
                    continue
                # 其他单字（数字/字母/汉字）走独立性检查
                stats = self.single_char_stats.get(word)
                if stats:
                    total, indep, ratio = stats
                    if ratio < cfg.SINGLE_MIN_SOLO_RATIO or indep < cfg.SINGLE_MIN_SOLO_COUNT:
                        continue
                else:
                    continue
                        
            filtered_freq[word] = freq
        
        self.word_freq = filtered_freq
        
        # 采样
        for word in self.word_samples:
            samples = self.word_samples[word]
            if len(samples) > cfg.SAMPLE_COUNT:
                self.word_samples[word] = random.sample(samples, cfg.SAMPLE_COUNT)
        
        logger.debug(f"过滤后 {len(self.word_freq)} 个词")

    def get_top_words(self, n=None):
        n = n or cfg.TOP_N
        return self.word_freq.most_common(n)

    def get_word_detail(self, word):
        return {
            'word': word,
            'freq': self.word_freq.get(word, 0),
            'samples': self.word_samples.get(word, []),
            'contributors': [(self.get_name(uin), count) 
                           for uin, count in self.word_contributors[word].most_common(cfg.CONTRIBUTOR_TOP_N)]
        }

    def get_fun_rankings(self):
        rankings = {}
        
        def fmt(counter, top_n=cfg.RANK_TOP_N):
            return [(self.get_name(uin), count) for uin, count in counter.most_common(top_n)]
        
        rankings['话痨榜'] = fmt(self.user_msg_count)
        rankings['字数榜'] = fmt(self.user_char_count)
        
        sorted_avg = sorted(self.user_char_per_msg.items(), key=lambda x: x[1], reverse=True)[:cfg.RANK_TOP_N]
        rankings['长文王'] = [(self.get_name(uin), f"{avg:.1f}字/条") for uin, avg in sorted_avg]
        
        rankings['图片狂魔'] = fmt(self.user_image_count)
        rankings['合并转发王'] = fmt(self.user_forward_count)
        rankings['回复狂'] = fmt(self.user_reply_count)
        rankings['被回复最多'] = fmt(self.user_replied_count)
        rankings['艾特狂'] = fmt(self.user_at_count)
        rankings['被艾特最多'] = fmt(self.user_ated_count)
        rankings['表情帝'] = fmt(self.user_emoji_count)
        rankings['链接分享王'] = fmt(self.user_link_count)
        rankings['深夜党'] = fmt(self.user_night_count)
        rankings['早起鸟'] = fmt(self.user_morning_count)
        rankings['复读机'] = fmt(self.user_repeat_count)
        
        return rankings
    
    def export_json(self):
        """导出JSON格式结果（包含uin信息）"""
        top_words = []
        for word, freq in self.get_top_words():
            # 再次在导出阶段过滤停用词，保证报告中不包含停用词
            if self.use_stopwords and word in self.stopwords:
                continue
            top_words.append({
                'word': word,
                'freq': freq,
                'contributors': [
                    {
                        'name': self.get_name(uin),
                        'uin': uin,
                        'count': count
                    }
                    for uin, count in self.word_contributors[word].most_common(cfg.CONTRIBUTOR_TOP_N)
                ],
                'samples': self.word_samples.get(word, [])[:cfg.SAMPLE_COUNT]
            })

        result = {
            'chatName': self.chat_name,
            'messageCount': len(self.messages),
            'topWords': top_words,
            'rankings': {},
            'hourDistribution': {str(h): self.hour_distribution.get(h, 0) for h in range(24)}
        }
        
        # 趣味榜单（包含uin）
        def fmt_with_uin(counter, top_n=cfg.RANK_TOP_N):
            return [
                {'name': self.get_name(uin), 'uin': uin, 'value': count}
                for uin, count in counter.most_common(top_n)
            ]
        
        result['rankings']['话痨榜'] = fmt_with_uin(self.user_msg_count)
        result['rankings']['字数榜'] = fmt_with_uin(self.user_char_count)
        
        # 长文王特殊处理
        sorted_avg = sorted(self.user_char_per_msg.items(), key=lambda x: x[1], reverse=True)[:cfg.RANK_TOP_N]
        result['rankings']['长文王'] = [
            {'name': self.get_name(uin), 'uin': uin, 'value': f"{avg:.1f}字/条"}
            for uin, avg in sorted_avg
        ]
        
        result['rankings']['图片狂魔'] = fmt_with_uin(self.user_image_count)
        result['rankings']['合并转发王'] = fmt_with_uin(self.user_forward_count)
        result['rankings']['回复狂'] = fmt_with_uin(self.user_reply_count)
        result['rankings']['被回复最多'] = fmt_with_uin(self.user_replied_count)
        result['rankings']['艾特狂'] = fmt_with_uin(self.user_at_count)
        result['rankings']['被艾特最多'] = fmt_with_uin(self.user_ated_count)
        result['rankings']['表情帝'] = fmt_with_uin(self.user_emoji_count)
        result['rankings']['链接分享王'] = fmt_with_uin(self.user_link_count)
        result['rankings']['深夜党'] = fmt_with_uin(self.user_night_count)
        result['rankings']['早起鸟'] = fmt_with_uin(self.user_morning_count)
        result['rankings']['复读机'] = fmt_with_uin(self.user_repeat_count)
        
        return result
