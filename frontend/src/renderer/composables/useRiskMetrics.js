import { ref, reactive } from 'vue'
import api from '../services/api'

/**
 * 风险指标组合式函数
 */
export function useRiskMetrics() {
  const metrics = ref(null)
  const drawdownData = ref(null)
  const rollingData = ref(null)
  const loading = ref(false)

  const params = reactive({
    mode: 'simulated',
    days: 90,
    window: 30,
  })

  async function fetchMetrics() {
    loading.value = true
    try {
      const res = await api.getRiskMetrics({
        mode: params.mode,
        days: params.days,
      })
      if (res.success) {
        metrics.value = res.data
      }
    } catch (err) {
      console.error('[Risk] 加载风险指标失败:', err)
    } finally {
      loading.value = false
    }
  }

  async function fetchDrawdown() {
    try {
      const res = await api.getRiskDrawdown({
        mode: params.mode,
        days: params.days,
      })
      if (res.success) {
        drawdownData.value = res.data
      }
    } catch (err) {
      console.error('[Risk] 加载回撤数据失败:', err)
    }
  }

  async function fetchRolling() {
    try {
      const res = await api.getRiskRolling({
        mode: params.mode,
        window: params.window,
        days: params.days,
      })
      if (res.success) {
        rollingData.value = res.data
      }
    } catch (err) {
      console.error('[Risk] 加载滚动指标失败:', err)
    }
  }

  async function fetchAll() {
    await Promise.all([fetchMetrics(), fetchDrawdown(), fetchRolling()])
  }

  return {
    metrics,
    drawdownData,
    rollingData,
    loading,
    params,
    fetchMetrics,
    fetchDrawdown,
    fetchRolling,
    fetchAll,
  }
}
