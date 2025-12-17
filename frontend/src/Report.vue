<template>
  <div class="report-page-wrapper">
    <!-- 动态加载模板组件 -->
    <component 
      v-if="report && templateComponent" 
      :is="templateComponent"
      :report="report"
      :generating-image="generatingImage"
      :image-url="imageUrl"
      :image-error="imageError"
      @generate-image="generateImage"
    />
    
    <!-- 模板加载失败提示 -->
    <div v-else-if="report && !templateComponent" class="template-error-container">
      <div class="template-error">
        <h2>⚠️ 模板加载失败</h2>
        <p>无法加载模板文件，请检查模板配置</p>
        <div class="template-info">
          <p>模板ID: <code>{{ currentTemplateId }}</code></p>
          <p>报告ID: <code>{{ currentReportId }}</code></p>
        </div>
        <button @click="loadReport">重新加载</button>
      </div>
    </div>
    
    <!-- 数据加载中 -->
    <div v-else-if="loading" class="loading-container">
      <div class="loading">
        <div class="loading-spinner"></div>
        <p>加载报告数据中...</p>
      </div>
    </div>
    
    <!-- 数据加载错误 -->
    <div v-else-if="error" class="error-container">
      <div class="error-message">
        <h2>❌ 加载失败</h2>
        <p>{{ error }}</p>
      </div>
      <button @click="loadReport">重新加载</button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, shallowRef } from 'vue'
import axios from 'axios'
import html2canvas from 'html2canvas'

const API_BASE = import.meta.env.VITE_API_BASE || '/api'

// ========== 数据状态 ==========
const report = ref(null)
const loading = ref(true)
const error = ref(null)

// ========== 模板状态 ==========
const templateComponent = shallowRef(null)
const currentTemplateId = ref('')
const currentReportId = ref('')

// ========== 图片生成状态 ==========
const generatingImage = ref(false)
const imageUrl = ref('')
const imageError = ref('')

// ========== 路由参数解析 ==========
/**
 * 获取路由参数
 * 支持两种格式：
 * - /report/{id} - 使用默认 classic 模板
 * - /report/{template}/{id} - 使用指定模板
 */
const getRouteParams = () => {
  const path = window.location.pathname
  // 尝试匹配 /personal-report/{template}/{id}
  let match = path.match(/\/personal-report\/([^/]+)\/([^/]+)/)
  if (match) {
    return { templateId: match[1], reportId: match[2], isPersonal: true }
  }
  // 尝试匹配 /report/{template}/{id}
  match = path.match(/\/report\/([^/]+)\/([^/]+)/)
  if (match) {
    return { templateId: match[1], reportId: match[2], isPersonal: false }
  }
  // 尝试匹配 /report/{id}
  match = path.match(/\/report\/([^/]+)/)
  if (match) {
    return { templateId: 'classic', reportId: match[1], isPersonal: false }
  }
  return null
}

const getReportId = () => {
  const params = getRouteParams()
  return params ? params.reportId : null
}

// ========== 模板加载 ==========
/**
 * 动态加载模板组件
 * @param {string} templateId - 模板ID
 */
const loadTemplate = async (templateId) => {
  try {
    // 尝试加载模板，支持个人报告模板
    const module = await import(`./templates/${templateId}.vue`)
    templateComponent.value = module.default
  } catch (err) {
    console.warn(`模板 ${templateId} 加载失败`, err)
    templateComponent.value = null
  }
}

// ========== 报告数据加载 ==========
/**
 * 加载报告数据
 */
const loadReport = async () => {
  loading.value = true
  error.value = null
  
  try {
    const reportId = getReportId()
    if (!reportId) {
      throw new Error('报告ID不存在')
    }
    
    const params = getRouteParams()
    const isPersonal = params?.isPersonal || false
    
    // 根据类型选择不同的API端点
    const apiEndpoint = isPersonal 
      ? `${API_BASE}/personal-reports/${reportId}`
      : `${API_BASE}/reports/${reportId}`
    
    const { data } = await axios.get(apiEndpoint)
    
    if (data.error) {
      throw new Error(data.error)
    }
    
    report.value = data
  } catch (err) {
    error.value = err.message || '加载报告失败'
    console.error('加载报告失败:', err)
  } finally {
    loading.value = false
  }
}

// ========== 图片生成功能 ==========
/**
 * 生成报告图片分享（调用后端API）
 */
const generateImage = async () => {
  if (generatingImage.value) return
  
  generatingImage.value = true
  imageError.value = ''
  
  try {
    const reportId = getReportId()
    if (!reportId) {
      throw new Error('报告ID不存在')
    }
    
    const params = getRouteParams()
    const templateId = params?.templateId || 'classic'
    const isPersonal = params?.isPersonal || false
    
    console.log('🖼️ 请求后端生成图片...')
    
    // 根据类型选择不同的API端点
    const apiEndpoint = isPersonal
      ? `${API_BASE}/personal-reports/${reportId}/generate-image`
      : `${API_BASE}/reports/${reportId}/generate-image`
    
    const { data } = await axios.post(
      apiEndpoint,
      {
        template: templateId,
        format: 'for_share',  // 分享版本
        force: false  // 使用缓存
      }
    )
    
    if (data.success) {
      imageUrl.value = data.image_url
      
      // 自动触发下载
      const params = getRouteParams()
      const isPersonal = params?.isPersonal || false
      const name = isPersonal 
        ? (report.value?.user_name || '用户')
        : (report.value?.chat_name || '报告')
      const reportType = isPersonal ? '个人年度报告' : '年度报告'
      const fileName = `${name}_${reportType}_${new Date().getTime()}.png`
      const link = document.createElement('a')
      link.href = data.image_url
      link.download = fileName
      link.click()
      
      console.log('✅ 图片生成成功', data.cached ? '(来自缓存)' : '')
    } else {
      throw new Error(data.error || '图片生成失败')
    }
    
  } catch (err) {
    console.error('生成图片失败:', err)
    imageError.value = err.response?.data?.error || err.message || '生成图片失败，请重试'
  } finally {
    generatingImage.value = false
  }
}

// ========== 生命周期 ==========
onMounted(async () => {
  const params = getRouteParams()
  if (params) {
    currentTemplateId.value = params.templateId
    currentReportId.value = params.reportId
    await loadTemplate(params.templateId)
  }
  loadReport()
})
</script>

<style>
/* 报告页面包装器 - 居中并设置背景 */
.report-page-wrapper {
  background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%);
  min-height: 100vh;
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding: 0;
  margin: 0;
}

/* ========== 加载状态 ========== */
.loading-container, .error-container, .template-error-container {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  color: #f5f5dc;
  text-align: center;
  padding: 20px;
}

.loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
}

.loading-spinner {
  width: 50px;
  height: 50px;
  border: 4px solid rgba(212, 175, 55, 0.2);
  border-top-color: #d4af37;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.loading p {
  font-size: 18px;
  color: #d4af37;
  margin: 0;
}

/* ========== 错误状态 ========== */
.error-container, .template-error-container {
  gap: 20px;
}

.error-message, .template-error {
  background: rgba(0, 0, 0, 0.5);
  padding: 30px;
  border-radius: 10px;
  border: 2px solid #d4af37;
  max-width: 600px;
}

.error-message h2, .template-error h2 {
  color: #ff6b6b;
  margin: 0 0 15px 0;
  font-size: 24px;
}

.error-message p, .template-error p {
  color: #f5f5dc;
  margin: 10px 0;
  font-size: 16px;
}

.template-info {
  margin: 20px 0;
  padding: 15px;
  background: rgba(212, 175, 55, 0.1);
  border-radius: 5px;
  text-align: left;
}

.template-info p {
  margin: 5px 0;
  font-size: 14px;
}

.template-info code {
  background: rgba(0, 0, 0, 0.5);
  padding: 2px 8px;
  border-radius: 3px;
  color: #d4af37;
  font-family: 'Courier New', monospace;
}

.error-container button, .template-error-container button {
  padding: 12px 30px;
  background: #d4af37;
  color: #000;
  border: none;
  border-radius: 5px;
  font-size: 16px;
  font-weight: bold;
  cursor: pointer;
  transition: all 0.3s ease;
}

.error-container button:hover, .template-error-container button:hover {
  background: #f0c14b;
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(212, 175, 55, 0.3);
}

.error-container button:active, .template-error-container button:active {
  transform: translateY(0);
}
</style>
