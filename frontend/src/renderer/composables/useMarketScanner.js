import { ref, reactive } from 'vue'
import api from '../services/api'

/**
 * 市场扫描器组合式函数
 */
export function useMarketScanner() {
  const profiles = ref([])
  const scanResults = ref([])
  const availableConditions = ref([])
  const scanning = ref(false)
  const loading = ref(false)

  const scanForm = reactive({
    symbols: [],
    conditions: [{ indicator: 'rsi', operator: 'lt', value: 30, params: { period: 14 } }],
    logic: 'and',
    timeframe: '1H',
    inst_type: 'SPOT',
  })

  async function fetchProfiles() {
    loading.value = true
    try {
      const res = await api.getScannerProfiles()
      if (res.success) profiles.value = res.data || []
    } catch (err) {
      console.error('[Scanner] 加载方案失败:', err)
    } finally {
      loading.value = false
    }
  }

  async function createProfile(data) {
    try {
      const res = await api.createScannerProfile(data)
      if (res.success) {
        await fetchProfiles()
        return res.data
      }
    } catch (err) {
      console.error('[Scanner] 创建方案失败:', err)
    }
    return null
  }

  async function deleteProfile(profileId) {
    try {
      const res = await api.deleteScannerProfile(profileId)
      if (res.success) await fetchProfiles()
      return res.success
    } catch (err) {
      console.error('[Scanner] 删除方案失败:', err)
    }
    return false
  }

  async function runScan(params = null) {
    scanning.value = true
    try {
      const data = params || {
        symbols: scanForm.symbols,
        conditions: scanForm.conditions,
        logic: scanForm.logic,
        timeframe: scanForm.timeframe,
        inst_type: scanForm.inst_type,
      }
      const res = await api.runScan(data)
      if (res.success) {
        scanResults.value = res.data || []
        return { scanned: res.scanned, matched: res.matched }
      }
    } catch (err) {
      console.error('[Scanner] 扫描失败:', err)
    } finally {
      scanning.value = false
    }
    return null
  }

  async function runProfileScan(profileId) {
    scanning.value = true
    try {
      const res = await api.runProfileScan(profileId)
      if (res.success) {
        scanResults.value = res.data || []
        return { scanned: res.scanned, matched: res.matched }
      }
    } catch (err) {
      console.error('[Scanner] 方案扫描失败:', err)
    } finally {
      scanning.value = false
    }
    return null
  }

  async function fetchConditions() {
    try {
      const res = await api.getScannerConditions()
      if (res.success) availableConditions.value = res.data || []
    } catch (err) {
      console.error('[Scanner] 加载条件类型失败:', err)
    }
  }

  function addCondition() {
    scanForm.conditions.push({ indicator: 'rsi', operator: 'lt', value: 30, params: {} })
  }

  function removeCondition(index) {
    scanForm.conditions.splice(index, 1)
  }

  return {
    profiles,
    scanResults,
    availableConditions,
    scanning,
    loading,
    scanForm,
    fetchProfiles,
    createProfile,
    deleteProfile,
    runScan,
    runProfileScan,
    fetchConditions,
    addCondition,
    removeCondition,
  }
}
