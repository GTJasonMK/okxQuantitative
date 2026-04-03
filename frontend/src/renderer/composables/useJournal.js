import { ref, reactive, computed } from 'vue'
import api from '../services/api'

/**
 * 交易日志组合式函数
 * 管理日志条目的 CRUD、标签、统计
 */
export function useJournal() {
  const entries = ref([])
  const currentEntry = ref(null)
  const tags = ref([])
  const stats = ref(null)
  const total = ref(0)
  const loading = ref(false)
  const saving = ref(false)

  const filters = reactive({
    mode: '',
    inst_id: '',
    tags: '',
    strategy_id: '',
    date_from: '',
    date_to: '',
    limit: 20,
    offset: 0,
  })

  const totalPages = computed(() => Math.ceil(total.value / filters.limit))
  const currentPage = computed(() => Math.floor(filters.offset / filters.limit) + 1)

  async function fetchEntries() {
    loading.value = true
    try {
      const params = {}
      if (filters.mode) params.mode = filters.mode
      if (filters.inst_id) params.inst_id = filters.inst_id
      if (filters.tags) params.tags = filters.tags
      if (filters.strategy_id) params.strategy_id = filters.strategy_id
      if (filters.date_from) params.date_from = filters.date_from
      if (filters.date_to) params.date_to = filters.date_to
      params.limit = filters.limit
      params.offset = filters.offset

      const res = await api.getJournalEntries(params)
      if (res.success) {
        entries.value = res.data || []
        total.value = res.total || 0
      }
    } catch (err) {
      console.error('[Journal] 加载日志失败:', err)
    } finally {
      loading.value = false
    }
  }

  async function fetchEntry(entryId) {
    try {
      const res = await api.getJournalEntry(entryId)
      if (res.success) {
        currentEntry.value = res.data
      }
    } catch (err) {
      console.error('[Journal] 加载日志详情失败:', err)
    }
  }

  async function createEntry(data) {
    saving.value = true
    try {
      const res = await api.createJournalEntry(data)
      if (res.success) {
        await fetchEntries()
        return res.data
      }
    } catch (err) {
      console.error('[Journal] 创建日志失败:', err)
    } finally {
      saving.value = false
    }
    return null
  }

  async function updateEntry(entryId, data) {
    saving.value = true
    try {
      const res = await api.updateJournalEntry(entryId, data)
      if (res.success) {
        await fetchEntries()
        return res.data
      }
    } catch (err) {
      console.error('[Journal] 更新日志失败:', err)
    } finally {
      saving.value = false
    }
    return null
  }

  async function deleteEntry(entryId) {
    try {
      const res = await api.deleteJournalEntry(entryId)
      if (res.success) {
        await fetchEntries()
        return true
      }
    } catch (err) {
      console.error('[Journal] 删除日志失败:', err)
    }
    return false
  }

  async function fetchTags() {
    try {
      const res = await api.getJournalTags()
      if (res.success) {
        tags.value = res.data || []
      }
    } catch (err) {
      console.error('[Journal] 加载标签失败:', err)
    }
  }

  async function fetchStats(mode = '', groupBy = 'tag') {
    try {
      const res = await api.getJournalStats({ mode, group_by: groupBy })
      if (res.success) {
        stats.value = res.data
      }
    } catch (err) {
      console.error('[Journal] 加载统计失败:', err)
    }
  }

  function goToPage(page) {
    filters.offset = (page - 1) * filters.limit
    fetchEntries()
  }

  return {
    entries,
    currentEntry,
    tags,
    stats,
    total,
    totalPages,
    currentPage,
    loading,
    saving,
    filters,
    fetchEntries,
    fetchEntry,
    createEntry,
    updateEntry,
    deleteEntry,
    fetchTags,
    fetchStats,
    goToPage,
  }
}
