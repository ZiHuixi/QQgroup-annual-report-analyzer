<template>
  <div class="personal-report-wrapper">
    <div class="personal-report-container" v-if="report">
      <!-- 头部 -->
      <div class="report-header">
        <button @click="$emit('back')" class="back-button">← 返回</button>
        <div class="header-content">
          <div class="header-badge">Personal Annual Report</div>
          <h1>{{ report.user_name }}</h1>
          <div class="subtitle">{{ report.chat_name }} · 个人年度报告</div>
          <div class="header-stats">
            <div class="stat-box">
              <div class="stat-value">{{ formatNumber(report.total_messages) }}</div>
              <div class="stat-label">总发言数</div>
            </div>
            <div class="stat-box">
              <div class="stat-value">{{ report.active_days }}</div>
              <div class="stat-label">活跃天数</div>
            </div>
            <div class="stat-box">
              <div class="stat-value">{{ (report.active_ratio || 0).toFixed(1) }}%</div>
              <div class="stat-label">活跃率</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 人格化标签 -->
      <div class="section tags-section" v-if="report.personality_tags && report.personality_tags.length > 0">
        <div class="section-header">
          <div class="section-title">个人标签</div>
        </div>
        <div class="tags-container">
          <span v-for="tag in report.personality_tags" :key="tag" class="personality-tag">
            {{ tag }}
          </span>
        </div>
      </div>

      <!-- 基础统计 -->
      <div class="section">
        <div class="section-header">
          <div class="section-title">基础数据</div>
        </div>
        <div class="stats-grid">
          <div class="stat-card">
            <div class="stat-card-value">{{ formatNumber(report.total_messages) }}</div>
            <div class="stat-card-label">年度总发言条数</div>
          </div>
          <div class="stat-card">
            <div class="stat-card-value">{{ (report.avg_daily_messages || 0).toFixed(1) }}</div>
            <div class="stat-card-label">平均每日发言数</div>
          </div>
          <div class="stat-card">
            <div class="stat-card-value">{{ report.active_days }} / {{ report.total_days }}</div>
            <div class="stat-card-label">活跃天数 / 全年天数</div>
          </div>
          <div class="stat-card" v-if="report.most_active_date">
            <div class="stat-card-value">{{ report.most_active_date.date }}</div>
            <div class="stat-card-label">最活跃的一天（{{ report.most_active_date.count }}条）</div>
          </div>
        </div>
      </div>

      <!-- 时间分析 -->
      <div class="section">
        <div class="section-header">
          <div class="section-title">时间分析</div>
        </div>
        <div class="stats-grid">
          <div class="stat-card">
            <div class="stat-card-value">{{ report.peak_hour }}时</div>
            <div class="stat-card-label">发言最集中的小时段</div>
          </div>
          <div class="stat-card">
            <div class="stat-card-value">{{ (report.night_ratio || 0).toFixed(1) }}%</div>
            <div class="stat-card-label">夜猫子指数（22:00-06:00）</div>
          </div>
          <div class="stat-card" v-if="report.first_message_time">
            <div class="stat-card-value">{{ formatDateTime(report.first_message_time) }}</div>
            <div class="stat-card-label">最早一次发言</div>
          </div>
          <div class="stat-card" v-if="report.last_message_time">
            <div class="stat-card-value">{{ formatDateTime(report.last_message_time) }}</div>
            <div class="stat-card-label">最晚一次发言</div>
          </div>
        </div>
        
        <!-- 小时分布图 -->
        <div class="hour-chart-container" v-if="report.hour_distribution">
          <div class="hour-chart">
            <div 
              v-for="hour in 24" 
              :key="hour"
              class="hour-bar" 
              :style="{ height: getHourHeight(hour) + '%' }"
              :title="`${hour}时: ${report.hour_distribution[hour] || 0}条`"
            ></div>
          </div>
          <div class="hour-labels">
            <span>0时</span>
            <span>6时</span>
            <span>12时</span>
            <span>18时</span>
            <span>24时</span>
          </div>
        </div>
      </div>

      <!-- 消息类型 -->
      <div class="section">
        <div class="section-header">
          <div class="section-title">消息类型占比</div>
        </div>
        <div class="message-types">
          <div class="type-item">
            <span class="type-label">纯文字</span>
            <div class="type-bar">
              <div class="type-bar-fill" :style="{ width: ((report.message_type_ratios && report.message_type_ratios.text) || 0).toFixed(1) + '%' }"></div>
            </div>
            <span class="type-value">{{ ((report.message_type_ratios && report.message_type_ratios.text) || 0).toFixed(1) }}%</span>
          </div>
          <div class="type-item">
            <span class="type-label">表情</span>
            <div class="type-bar">
              <div class="type-bar-fill" :style="{ width: ((report.message_type_ratios && report.message_type_ratios.emoji) || 0).toFixed(1) + '%' }"></div>
            </div>
            <span class="type-value">{{ ((report.message_type_ratios && report.message_type_ratios.emoji) || 0).toFixed(1) }}%</span>
          </div>
          <div class="type-item">
            <span class="type-label">图片</span>
            <div class="type-bar">
              <div class="type-bar-fill" :style="{ width: ((report.message_type_ratios && report.message_type_ratios.image) || 0).toFixed(1) + '%' }"></div>
            </div>
            <span class="type-value">{{ ((report.message_type_ratios && report.message_type_ratios.image) || 0).toFixed(1) }}%</span>
          </div>
          <div class="type-item" v-if="report.message_type_ratios && report.message_type_ratios.voice > 0">
            <span class="type-label">语音</span>
            <div class="type-bar">
              <div class="type-bar-fill" :style="{ width: ((report.message_type_ratios && report.message_type_ratios.voice) || 0).toFixed(1) + '%' }"></div>
            </div>
            <span class="type-value">{{ ((report.message_type_ratios && report.message_type_ratios.voice) || 0).toFixed(1) }}%</span>
          </div>
          <div class="type-item" v-if="report.message_type_ratios && report.message_type_ratios.file > 0">
            <span class="type-label">文件</span>
            <div class="type-bar">
              <div class="type-bar-fill" :style="{ width: ((report.message_type_ratios && report.message_type_ratios.file) || 0).toFixed(1) + '%' }"></div>
            </div>
            <span class="type-value">{{ ((report.message_type_ratios && report.message_type_ratios.file) || 0).toFixed(1) }}%</span>
          </div>
        </div>
        <div class="stat-card" style="margin-top: 20px;">
          <div class="stat-card-value">{{ (report.emoji_ratio || 0).toFixed(1) }}%</div>
          <div class="stat-card-label">表情使用率（表情条数 / 总消息数）</div>
        </div>
      </div>

      <!-- 复读相关 -->
      <div class="section">
        <div class="section-header">
          <div class="section-title">复读数据</div>
        </div>
        <div class="stats-grid">
          <div class="stat-card">
            <div class="stat-card-value">{{ report.repeat_count }}</div>
            <div class="stat-card-label">与上一条消息完全相同的次数</div>
          </div>
          <div class="stat-card">
            <div class="stat-card-value">{{ report.chain_repeat_count }}</div>
            <div class="stat-card-label">连续3人以上复读的参与次数</div>
          </div>
          <div class="stat-card">
            <div class="stat-card-value">{{ (report.chain_repeat_ratio || 0).toFixed(1) }}%</div>
            <div class="stat-card-label">复读参与率</div>
          </div>
        </div>
      </div>

      <!-- 互动分析 -->
      <div class="section">
        <div class="section-header">
          <div class="section-title">互动分析</div>
        </div>
        <div class="interaction-grid">
          <div class="interaction-card" v-if="report.most_interact_user">
            <div class="interaction-title">最常互动对象</div>
            <div class="interaction-value">{{ report.most_interact_user.name }}</div>
            <div class="interaction-desc">互相回复 {{ report.most_interact_user.count }} 次</div>
          </div>
          <div class="interaction-card" v-if="report.min_reply_interval_user">
            <div class="interaction-title">聊天间隔最短</div>
            <div class="interaction-value">{{ report.min_reply_interval_user.name }}</div>
            <div class="interaction-desc">平均间隔 {{ formatSeconds(report.min_reply_interval_user.avg_interval_seconds) }}</div>
          </div>
          <div class="interaction-card">
            <div class="interaction-title">@别人次数</div>
            <div class="interaction-value">{{ report.at_count }}</div>
            <div class="interaction-desc">年度话搭子</div>
          </div>
          <div class="interaction-card">
            <div class="interaction-title">被@次数</div>
            <div class="interaction-value">{{ report.ated_count }}</div>
            <div class="interaction-desc">今年被点名 {{ report.ated_count }} 次</div>
          </div>
          <div class="interaction-card" v-if="report.most_at_target">
            <div class="interaction-title">最常@的人</div>
            <div class="interaction-value">{{ report.most_at_target.name }}</div>
            <div class="interaction-desc">{{ report.most_at_target.count }} 次</div>
          </div>
          <div class="interaction-card" v-if="report.most_at_by">
            <div class="interaction-title">最常@你的人</div>
            <div class="interaction-value">{{ report.most_at_by.name }}</div>
            <div class="interaction-desc">{{ report.most_at_by.count }} 次</div>
          </div>
        </div>
      </div>

      <!-- 词频分析 -->
      <div class="section" v-if="report.top_words && report.top_words.length > 0">
        <div class="section-header">
          <div class="section-title">高频词汇</div>
        </div>
        <div class="words-container">
          <div 
            v-for="(word, index) in report.top_words.slice(0, 20)" 
            :key="word.word"
            class="word-item"
          >
            <div class="word-rank">#{{ index + 1 }}</div>
            <div class="word-content">
              <div class="word-text">{{ word.word }}</div>
              <div class="word-freq">{{ word.freq }} 次</div>
            </div>
          </div>
        </div>
        <div class="stat-card" v-if="report.consecutive_word" style="margin-top: 20px;">
          <div class="stat-card-value">"{{ report.consecutive_word.word }}"</div>
          <div class="stat-card-label">连续出现频率最高的词（{{ report.consecutive_word.count }}次）</div>
        </div>
      </div>

      <!-- 文字分析 -->
      <div class="section">
        <div class="section-header">
          <div class="section-title">文字分析</div>
        </div>
        <div class="stats-grid">
          <div class="stat-card">
            <div class="stat-card-value">{{ (report.avg_chars_per_msg || 0).toFixed(1) }}</div>
            <div class="stat-card-label">单条消息平均字数</div>
          </div>
          <div class="stat-card">
            <div class="stat-card-value">{{ report.long_messages }}</div>
            <div class="stat-card-label">超长消息（>200字）次数</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  report: {
    type: Object,
    required: true
  }
})

defineEmits(['back'])

const formatNumber = (num) => {
  if (num >= 10000) {
    return (num / 10000).toFixed(1) + '万'
  }
  return num.toLocaleString()
}

const formatDateTime = (str) => {
  if (!str) return ''
  const date = new Date(str)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const formatSeconds = (seconds) => {
  if (!seconds) return ''
  if (seconds < 60) {
    return seconds.toFixed(0) + '秒'
  } else if (seconds < 3600) {
    return (seconds / 60).toFixed(1) + '分钟'
  } else {
    return (seconds / 3600).toFixed(1) + '小时'
  }
}

const getHourHeight = (hour) => {
  if (!props.report.hour_distribution) return 0
  const maxCount = Math.max(...Object.values(props.report.hour_distribution))
  if (maxCount === 0) return 0
  const count = props.report.hour_distribution[hour] || 0
  return (count / maxCount) * 100
}
</script>

<style scoped>
.personal-report-wrapper {
  min-height: 100vh;
  background: #f5f5f7;
  padding: 20px;
}

.personal-report-container {
  max-width: 1200px;
  margin: 0 auto;
  background: white;
  border-radius: 16px;
  padding: 40px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.back-button {
  background: #f5f5f7;
  border: 1px solid #e5e5e7;
  padding: 8px 16px;
  border-radius: 8px;
  cursor: pointer;
  margin-bottom: 20px;
  font-size: 14px;
  color: #1d1d1f;
}

.back-button:hover {
  background: #e5e5e7;
}

.report-header {
  text-align: center;
  padding-bottom: 40px;
  border-bottom: 2px solid #e5e5e7;
  margin-bottom: 40px;
}

.header-badge {
  display: inline-block;
  padding: 4px 12px;
  background: #007aff;
  color: white;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.5px;
  margin-bottom: 16px;
}

.report-header h1 {
  font-size: 48px;
  font-weight: 700;
  margin: 16px 0;
  color: #1d1d1f;
}

.subtitle {
  font-size: 18px;
  color: #6e6e73;
  margin-bottom: 24px;
}

.header-stats {
  display: flex;
  justify-content: center;
  gap: 40px;
  margin-top: 32px;
}

.stat-box {
  text-align: center;
}

.stat-value {
  font-size: 36px;
  font-weight: 700;
  color: #007aff;
  margin-bottom: 8px;
}

.stat-label {
  font-size: 14px;
  color: #6e6e73;
}

.section {
  margin-bottom: 48px;
}

.section-header {
  margin-bottom: 24px;
}

.section-title {
  font-size: 28px;
  font-weight: 700;
  color: #1d1d1f;
}

.tags-section {
  background: #f5f5f7;
  padding: 24px;
  border-radius: 12px;
}

.tags-container {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.personality-tag {
  display: inline-block;
  padding: 8px 16px;
  background: #007aff;
  color: white;
  border-radius: 20px;
  font-size: 14px;
  font-weight: 500;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 20px;
}

.stat-card {
  background: #f5f5f7;
  padding: 24px;
  border-radius: 12px;
  text-align: center;
}

.stat-card-value {
  font-size: 32px;
  font-weight: 700;
  color: #007aff;
  margin-bottom: 8px;
}

.stat-card-label {
  font-size: 14px;
  color: #6e6e73;
}

.hour-chart-container {
  margin-top: 32px;
  padding: 24px;
  background: #f5f5f7;
  border-radius: 12px;
}

.hour-chart {
  display: flex;
  align-items: flex-end;
  height: 200px;
  gap: 4px;
  margin-bottom: 16px;
}

.hour-bar {
  flex: 1;
  background: #007aff;
  border-radius: 4px 4px 0 0;
  min-height: 4px;
  transition: all 0.3s ease;
}

.hour-bar:hover {
  opacity: 0.8;
}

.hour-labels {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #6e6e73;
}

.message-types {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.type-item {
  display: flex;
  align-items: center;
  gap: 16px;
}

.type-label {
  width: 80px;
  font-size: 14px;
  color: #1d1d1f;
  font-weight: 500;
}

.type-bar {
  flex: 1;
  height: 24px;
  background: #e5e5e7;
  border-radius: 12px;
  overflow: hidden;
}

.type-bar-fill {
  height: 100%;
  background: #007aff;
  transition: width 0.3s ease;
}

.type-value {
  width: 60px;
  text-align: right;
  font-size: 14px;
  color: #6e6e73;
  font-weight: 500;
}

.interaction-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 20px;
}

.interaction-card {
  background: #f5f5f7;
  padding: 20px;
  border-radius: 12px;
  text-align: center;
}

.interaction-title {
  font-size: 14px;
  color: #6e6e73;
  margin-bottom: 8px;
}

.interaction-value {
  font-size: 24px;
  font-weight: 700;
  color: #007aff;
  margin-bottom: 4px;
}

.interaction-desc {
  font-size: 12px;
  color: #6e6e73;
}

.words-container {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 16px;
}

.word-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: #f5f5f7;
  border-radius: 8px;
}

.word-rank {
  font-size: 14px;
  color: #6e6e73;
  font-weight: 600;
}

.word-content {
  flex: 1;
}

.word-text {
  font-size: 16px;
  font-weight: 600;
  color: #1d1d1f;
  margin-bottom: 4px;
}

.word-freq {
  font-size: 12px;
  color: #6e6e73;
}
</style>

