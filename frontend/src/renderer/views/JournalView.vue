<template>
  <div class="journal-view">
    <!-- 命令栏 -->
    <header class="jv-command-bar">
      <div class="jv-left">
        <h1 class="jv-title">交易日志</h1>
        <nav class="jv-tabs">
          <button
            v-for="tab in tabs"
            :key="tab.key"
            class="jv-tab"
            :class="{ active: activeTab === tab.key }"
            @click="activeTab = tab.key"
          >
            {{ tab.label }}
          </button>
        </nav>
      </div>
      <div class="jv-right">
        <button v-if="activeTab === 'list'" class="btn btn-primary btn-sm" @click="openNewForm">新建日志</button>
        <select v-if="activeTab === 'stats'" v-model="statsGroupBy" class="select select-sm" @change="fetchStats(filters.mode, statsGroupBy)">
          <option value="tag">按标签</option>
          <option value="strategy">按策略</option>
        </select>
      </div>
    </header>

    <!-- 日志列表 -->
    <section v-if="activeTab === 'list'" class="card">
      <div class="section-header">
        <h3 class="card-title">日志记录</h3>
        <div class="header-actions">
          <button class="btn btn-primary" @click="openNewForm">新建日志</button>
        </div>
      </div>

      <!-- 筛选条件 -->
      <div class="filter-bar">
        <select v-model="filters.mode" class="select select-sm" @change="fetchEntries">
          <option value="">全部模式</option>
          <option value="simulated">模拟盘</option>
          <option value="live">实盘</option>
        </select>
        <input
          v-model="filters.inst_id"
          class="input input-sm"
          placeholder="交易对筛选"
          @keyup.enter="fetchEntries"
        />
        <input
          v-model="filters.tags"
          class="input input-sm"
          placeholder="标签筛选(逗号分隔)"
          @keyup.enter="fetchEntries"
        />
        <button class="btn btn-ghost btn-sm" @click="fetchEntries">搜索</button>
      </div>

      <!-- 日志表格 -->
      <div v-if="loading" class="loading-state">加载中...</div>
      <div v-else-if="entries.length === 0" class="empty-state">暂无日志记录</div>
      <table v-else class="data-table">
        <thead>
          <tr>
            <th>时间</th>
            <th>标题</th>
            <th>交易对</th>
            <th>标签</th>
            <th>评分</th>
            <th>盈亏</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="entry in entries" :key="entry.entry_id">
            <td class="cell-time">{{ formatTime(entry.created_at) }}</td>
            <td>{{ entry.title || '(无标题)' }}</td>
            <td>{{ entry.inst_id || '-' }}</td>
            <td>
              <span v-for="tag in entry.tags" :key="tag" class="tag-badge">{{ tag }}</span>
            </td>
            <td>
              <span v-if="entry.rating">{{ '★'.repeat(entry.rating) }}</span>
              <span v-else class="text-muted">-</span>
            </td>
            <td :class="pnlClass(entry.pnl_snapshot)">
              {{ entry.pnl_snapshot ? entry.pnl_snapshot.toFixed(2) : '-' }}
            </td>
            <td class="cell-actions">
              <button class="btn btn-ghost btn-xs" @click="openEditForm(entry)">编辑</button>
              <button class="btn btn-ghost btn-xs text-danger" @click="confirmDelete(entry)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>

      <!-- 分页 -->
      <div v-if="totalPages > 1" class="pagination">
        <button class="btn btn-ghost btn-sm" :disabled="currentPage <= 1" @click="goToPage(currentPage - 1)">上一页</button>
        <span class="page-info">{{ currentPage }} / {{ totalPages }}</span>
        <button class="btn btn-ghost btn-sm" :disabled="currentPage >= totalPages" @click="goToPage(currentPage + 1)">下一页</button>
      </div>
    </section>

    <!-- 新建/编辑表单 -->
    <section v-if="activeTab === 'form'" class="card">
      <div class="section-header">
        <h3 class="card-title">{{ editingId ? '编辑日志' : '新建日志' }}</h3>
        <button class="btn btn-ghost btn-sm" @click="activeTab = 'list'">返回列表</button>
      </div>

      <div class="form-grid">
        <div class="form-group">
          <label>标题</label>
          <input v-model="form.title" class="input" placeholder="简短描述本次交易" />
        </div>
        <div class="form-group">
          <label>交易对</label>
          <input v-model="form.inst_id" class="input" placeholder="如 BTC-USDT" />
        </div>
        <div class="form-group">
          <label>模式</label>
          <select v-model="form.mode" class="select">
            <option value="simulated">模拟盘</option>
            <option value="live">实盘</option>
          </select>
        </div>
        <div class="form-group">
          <label>评分 (1-5)</label>
          <select v-model.number="form.rating" class="select">
            <option :value="0">未评分</option>
            <option v-for="n in 5" :key="n" :value="n">{{ '★'.repeat(n) }}</option>
          </select>
        </div>
        <div class="form-group">
          <label>标签 (逗号分隔)</label>
          <input v-model="formTagsStr" class="input" placeholder="突破,趋势跟踪" />
        </div>
        <div class="form-group">
          <label>策略</label>
          <input v-model="form.strategy_name" class="input" placeholder="策略名称" />
        </div>
        <div class="form-group">
          <label>盈亏快照 (USDT)</label>
          <input v-model.number="form.pnl_snapshot" class="input" type="number" step="0.01" />
        </div>
        <div class="form-group">
          <label>情绪标记</label>
          <select v-model="form.emotion" class="select">
            <option value="">未标记</option>
            <option value="confident">自信</option>
            <option value="uncertain">犹豫</option>
            <option value="fearful">恐惧</option>
            <option value="greedy">贪婪</option>
            <option value="calm">冷静</option>
          </select>
        </div>
        <div class="form-group form-group-full">
          <label>笔记内容</label>
          <textarea v-model="form.content" class="textarea" rows="6" placeholder="记录交易逻辑、入场理由、复盘总结..." />
        </div>
      </div>

      <div class="form-actions">
        <button class="btn btn-ghost" @click="activeTab = 'list'">取消</button>
        <button class="btn btn-primary" :disabled="saving" @click="submitForm">
          {{ saving ? '保存中...' : (editingId ? '保存修改' : '创建日志') }}
        </button>
      </div>
    </section>

    <!-- 统计面板 -->
    <section v-if="activeTab === 'stats'" class="card">
      <div class="section-header">
        <h3 class="card-title">统计分析</h3>
        <div class="header-actions">
          <select v-model="statsGroupBy" class="select select-sm" @change="fetchStats(filters.mode, statsGroupBy)">
            <option value="tag">按标签</option>
            <option value="strategy">按策略</option>
          </select>
        </div>
      </div>

      <div v-if="!stats" class="empty-state">暂无数据</div>
      <table v-else class="data-table">
        <thead>
          <tr>
            <th>{{ statsGroupBy === 'tag' ? '标签' : '策略' }}</th>
            <th>条目数</th>
            <th>总盈亏</th>
            <th>胜率</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="group in stats.groups" :key="group.key">
            <td>{{ group.key }}</td>
            <td>{{ group.count }}</td>
            <td :class="pnlClass(group.total_pnl)">{{ group.total_pnl.toFixed(2) }}</td>
            <td>{{ group.win_rate.toFixed(1) }}%</td>
          </tr>
        </tbody>
      </table>
      <p v-if="stats" class="stats-total">共 {{ stats.total_entries }} 条日志</p>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useJournal } from '../composables/useJournal'

const {
  entries, tags, stats, total, totalPages, currentPage,
  loading, saving, filters,
  fetchEntries, createEntry, updateEntry, deleteEntry,
  fetchTags, fetchStats, goToPage,
} = useJournal()

const tabs = [
  { key: 'list', label: '日志列表' },
  { key: 'form', label: '新建日志' },
  { key: 'stats', label: '统计分析' },
]
const activeTab = ref('list')
const editingId = ref(null)
const statsGroupBy = ref('tag')

// 表单数据
const form = ref(getEmptyForm())
const formTagsStr = ref('')

function getEmptyForm() {
  return {
    title: '', content: '', mode: 'simulated', inst_id: '',
    inst_type: 'SPOT', tags: [], strategy_id: '', strategy_name: '',
    rating: 0, emotion: '', pnl_snapshot: 0, screenshots: [], metadata: {},
  }
}

function openNewForm() {
  editingId.value = null
  form.value = getEmptyForm()
  formTagsStr.value = ''
  activeTab.value = 'form'
}

function openEditForm(entry) {
  editingId.value = entry.entry_id
  form.value = { ...entry }
  formTagsStr.value = (entry.tags || []).join(', ')
  activeTab.value = 'form'
}

async function submitForm() {
  const data = {
    ...form.value,
    tags: formTagsStr.value.split(',').map(t => t.trim()).filter(Boolean),
  }
  if (editingId.value) {
    await updateEntry(editingId.value, data)
  } else {
    await createEntry(data)
  }
  activeTab.value = 'list'
}

async function confirmDelete(entry) {
  if (confirm(`确定删除日志「${entry.title || entry.entry_id}」？`)) {
    await deleteEntry(entry.entry_id)
  }
}

function formatTime(ts) {
  if (!ts) return '-'
  try {
    const d = new Date(ts)
    return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
  } catch {
    return ts
  }
}

function pnlClass(val) {
  if (!val) return ''
  return val > 0 ? 'text-profit' : val < 0 ? 'text-loss' : ''
}

onMounted(() => {
  fetchEntries()
  fetchTags()
  fetchStats('', 'tag')
})
</script>

<style scoped src="../assets/styles/views/journal-view.css"></style>
