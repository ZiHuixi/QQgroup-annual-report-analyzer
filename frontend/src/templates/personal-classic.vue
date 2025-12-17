<template>
  <div class="report-page-wrapper classic-template">
    <div class="report-container" v-if="report">
      <div class="stripe"></div>
      
      <!-- 头部 -->
      <div class="header">
        <div class="header-badge">Personal Annual Report</div>
        <div class="header-star-group">★ ★ ★</div>
        <h1 :class="getTitleClass(report.user_name)">{{ report.user_name }}</h1>
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
      
      <div class="stripe-diagonal"></div>

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
        <div class="stats-grid-personal">
          <div class="stat-card-personal">
            <div class="stat-card-value">{{ formatNumber(report.total_messages) }}</div>
            <div class="stat-card-label">年度总发言条数</div>
          </div>
          <div class="stat-card-personal">
            <div class="stat-card-value">{{ (report.avg_daily_messages || 0).toFixed(1) }}</div>
            <div class="stat-card-label">平均每日发言数</div>
          </div>
          <div class="stat-card-personal">
            <div class="stat-card-value">{{ report.active_days }} / {{ report.total_days }}</div>
            <div class="stat-card-label">活跃天数 / 全年天数</div>
          </div>
          <div class="stat-card-personal" v-if="report.most_active_date">
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
        <div class="stats-grid-personal">
          <div class="stat-card-personal">
            <div class="stat-card-value">{{ report.peak_hour }}时</div>
            <div class="stat-card-label">发言最集中的小时段</div>
          </div>
          <div class="stat-card-personal">
            <div class="stat-card-value">{{ (report.night_ratio || 0).toFixed(1) }}%</div>
            <div class="stat-card-label">夜猫子指数（22:00-06:00）</div>
          </div>
          <div class="stat-card-personal" v-if="report.first_message_time">
            <div class="stat-card-value">{{ formatDateTime(report.first_message_time) }}</div>
            <div class="stat-card-label">最早一次发言</div>
          </div>
          <div class="stat-card-personal" v-if="report.last_message_time">
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
        </div>
        <div class="stat-card-personal" style="margin-top: 20px;">
          <div class="stat-card-value">{{ (report.emoji_ratio || 0).toFixed(1) }}%</div>
          <div class="stat-card-label">表情使用率</div>
        </div>
      </div>

      <!-- 互动分析 -->
      <div class="section" v-if="report.most_interact_user || report.most_at_target || report.most_at_by">
        <div class="section-header">
          <div class="section-title">互动分析</div>
        </div>
        <div class="interaction-grid-personal">
          <div class="interaction-card-personal" v-if="report.most_interact_user">
            <div class="interaction-title">最常互动对象</div>
            <div class="interaction-value">{{ report.most_interact_user.name }}</div>
            <div class="interaction-desc">互相回复 {{ report.most_interact_user.count }} 次</div>
          </div>
          <div class="interaction-card-personal" v-if="report.most_at_target">
            <div class="interaction-title">最常@的人</div>
            <div class="interaction-value">{{ report.most_at_target.name }}</div>
            <div class="interaction-desc">{{ report.most_at_target.count }} 次</div>
          </div>
          <div class="interaction-card-personal" v-if="report.most_at_by">
            <div class="interaction-title">最常@你的人</div>
            <div class="interaction-value">{{ report.most_at_by.name }}</div>
            <div class="interaction-desc">{{ report.most_at_by.count }} 次</div>
          </div>
        </div>
      </div>

      <!-- 高频词汇 -->
      <div class="section" v-if="report.top_words && report.top_words.length > 0">
        <div class="section-header">
          <div class="section-title">高频词汇</div>
        </div>
        <div class="words-container-personal">
          <div 
            v-for="(word, index) in report.top_words.slice(0, 10)" 
            :key="word.word"
            class="word-item-personal"
          >
            <div class="word-rank">#{{ index + 1 }}</div>
            <div class="word-content">
              <div class="word-text">{{ word.word }}</div>
              <div class="word-freq">{{ word.freq }} 次</div>
            </div>
          </div>
        </div>
      </div>
      
      <div class="stripe-diagonal"></div>
      
      <!-- 分享按钮区域 -->
      <div class="share-section">
        <div class="share-container">
          <!-- 如果没有生成图片或有错误，显示生成按钮 -->
          <button 
            v-if="!imageUrl || imageError"
            class="share-button" 
            @click="$emit('generate-image')"
            :disabled="generatingImage">
            <span v-if="!generatingImage">
              {{ imageError ? '🔄 重新生成' : '📸 生成图片分享' }}
            </span>
            <span v-else>
              <span class="loading-dots">生成中</span>
            </span>
          </button>
          
          <!-- 如果图片已生成，显示下载和重新生成选项 -->
          <div v-if="imageUrl && !imageError" class="share-result">
            <div class="share-success">✅ 图片已生成并下载</div>
            <div class="share-actions">
              <a :href="imageUrl" :download="imageFileName" class="download-button">
                💾 再次下载
              </a>
              <button class="regenerate-button" @click="$emit('generate-image')">
                🔄 重新生成
              </button>
            </div>
          </div>
          
          <!-- 显示错误信息 -->
          <div v-if="imageError" class="share-error">
            ❌ {{ imageError }}
          </div>
        </div>
      </div>
      
      <!-- 页脚 -->
      <div class="footer">
        <div class="footer-text">
          Github.com/ZiHuixi/QQgroup-annual-report-analyzer
        </div>
      </div>
      
      <div class="stripe-thin"></div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useReportUtils } from '../composables/useReportUtils'

// ========== Props ==========
const props = defineProps({
  report: {
    type: Object,
    required: true
  },
  generatingImage: {
    type: Boolean,
    default: false
  },
  imageUrl: {
    type: String,
    default: ''
  },
  imageError: {
    type: String,
    default: ''
  }
})

// ========== Emits ==========
defineEmits(['generate-image'])

// ========== 使用工具函数 ==========
const {
  formatNumber,
  getTitleClass,
} = useReportUtils()

// ========== 辅助函数 ==========
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

const getHourHeight = (hour) => {
  if (!props.report.hour_distribution) return 0
  const maxCount = Math.max(...Object.values(props.report.hour_distribution))
  if (maxCount === 0) return 0
  const count = props.report.hour_distribution[hour] || 0
  return (count / maxCount) * 100
}

// 获取图片文件名
const imageFileName = computed(() => {
  const userName = props.report?.user_name || '用户'
  return `${userName}_个人年度报告_${new Date().getTime()}.png`
})
</script>

<style>
@import '../report-styles.css';
</style>

<style scoped>
.classic-template {
  
}

.tags-section {
  background: rgba(255, 255, 255, 0.05);
  padding: 24px;
  border-radius: 12px;
  margin-bottom: 32px;
}

.tags-container {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 16px;
}

.personality-tag {
  display: inline-block;
  padding: 8px 16px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-radius: 20px;
  font-size: 14px;
  font-weight: 500;
}

.stats-grid-personal {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 20px;
  margin-top: 24px;
}

.stat-card-personal {
  background: rgba(255, 255, 255, 0.05);
  padding: 24px;
  border-radius: 12px;
  text-align: center;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.stat-card-personal .stat-card-value {
  font-size: 32px;
  font-weight: 700;
  color: #fff;
  margin-bottom: 8px;
}

.stat-card-personal .stat-card-label {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.7);
}

.hour-chart-container {
  margin-top: 32px;
  padding: 24px;
  background: rgba(255, 255, 255, 0.05);
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
  background: linear-gradient(180deg, #667eea 0%, #764ba2 100%);
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
  color: rgba(255, 255, 255, 0.7);
}

.message-types {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-top: 24px;
}

.type-item {
  display: flex;
  align-items: center;
  gap: 16px;
}

.type-label {
  width: 80px;
  font-size: 14px;
  color: #fff;
  font-weight: 500;
}

.type-bar {
  flex: 1;
  height: 24px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  overflow: hidden;
}

.type-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
  transition: width 0.3s ease;
}

.type-value {
  width: 60px;
  text-align: right;
  font-size: 14px;
  color: rgba(255, 255, 255, 0.7);
  font-weight: 500;
}

.interaction-grid-personal {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 20px;
  margin-top: 24px;
}

.interaction-card-personal {
  background: rgba(255, 255, 255, 0.05);
  padding: 20px;
  border-radius: 12px;
  text-align: center;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.interaction-title {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.7);
  margin-bottom: 8px;
}

.interaction-value {
  font-size: 24px;
  font-weight: 700;
  color: #fff;
  margin-bottom: 4px;
}

.interaction-desc {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
}

.words-container-personal {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 16px;
  margin-top: 24px;
}

.word-item-personal {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.word-rank {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.7);
  font-weight: 600;
}

.word-content {
  flex: 1;
}

.word-text {
  font-size: 16px;
  font-weight: 600;
  color: #fff;
  margin-bottom: 4px;
}

.word-freq {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
}
</style>

