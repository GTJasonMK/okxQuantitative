<template>
  <div class="inventory-view">
    <!-- 工具栏 + 统计 -->
    <section class="inv-toolbar">
      <div class="inv-toolbar-row">
        <div class="inv-inputs">
          <input
            v-model.trim="searchKeyword"
            type="text"
            class="inv-input"
            placeholder="搜索币种"
          />
          <select v-model="scopeFilter" class="inv-select">
            <option value="all">全部</option>
            <option value="watched">仅已关注</option>
            <option value="orphan">仅孤儿</option>
          </select>
        </div>
        <div class="inv-stats">
          <span class="inv-stat"><strong>{{ summary.symbol_count || 0 }}</strong> 币种</span>
          <span class="inv-stat-sep">/</span>
          <span class="inv-stat"><strong>{{ summary.watched_symbol_count || 0 }}</strong> 已关注</span>
          <span class="inv-stat-sep">/</span>
          <span class="inv-stat danger"><strong>{{ summary.orphan_symbol_count || 0 }}</strong> 孤儿</span>
          <span class="inv-stat-sep">/</span>
          <span class="inv-stat"><strong>{{ formatCount(summary.total_candles) }}</strong> K线</span>
          <span class="inv-stat-sep">/</span>
          <span class="inv-stat"><strong>{{ formatCount(summary.table_totals?.total) }}</strong> 总记录</span>
        </div>
        <div class="inv-actions">
          <button class="btn btn-sm" :disabled="refreshing" @click="loadInventory">
            {{ refreshing ? '刷新中' : '刷新' }}
          </button>
          <button
            class="btn btn-sm btn-danger"
            :disabled="cleaningOrphans || !summary.orphan_symbol_count"
            @click="cleanOrphans"
          >
            {{ cleaningOrphans ? '清理中' : '清理孤儿' }}
          </button>
        </div>
      </div>
      <div v-if="successMessage || errorMessage" class="inv-feedback">
        <span v-if="successMessage" class="feedback-success">{{ successMessage }}</span>
        <span v-else-if="errorMessage" class="feedback-error">{{ errorMessage }}</span>
      </div>
    </section>

    <AnalyticsDataInventoryCard mode="guardian-only" />

    <section v-if="loading && rows.length === 0" class="inv-empty">
      正在读取数据库库存...
    </section>

    <section v-else-if="filteredRows.length === 0" class="inv-empty">
      <div class="empty-title">没有匹配的数据记录</div>
      <div class="empty-text">调整搜索或筛选条件后再试。</div>
    </section>

    <section v-else class="inventory-list">
      <article v-for="row in filteredRows" :key="row.symbol" class="inventory-row">
        <div class="inventory-row-head">
          <div class="symbol-block">
            <div class="symbol-line">
              <span class="symbol-name">{{ row.symbol }}</span>
              <span class="state-badge" :class="row.watched ? 'badge-watched' : 'badge-orphan'">
                {{ row.watched ? '已关注' : '孤儿数据' }}
              </span>
              <span class="state-badge badge-plain">
                {{ formatCount(row.storage_counts?.total) }} 条记录
              </span>
            </div>
            <div class="symbol-meta">
              <span>{{ row.base_ccy }}</span>
              <span>周期 {{ row.timeframe_record_count || 0 }}</span>
              <span>K 线 {{ formatCount(row.candle_count) }}</span>
              <span v-if="row.activeJobs.length > 0">运行任务 {{ row.activeJobs.length }}</span>
            </div>
          </div>

          <div class="row-actions">
            <button class="btn btn-sm" @click="openMarket(row.symbol)">去行情</button>
            <button
              class="btn btn-sm"
              :disabled="deletingSymbol === row.symbol"
              @click="openWatchlist(row.symbol)"
            >
              去关注页
            </button>
            <button
              v-if="row.watched"
              class="btn btn-sm"
              :disabled="repairingSymbol === row.symbol"
              @click="repairRow(row)"
            >
              {{ repairingSymbol === row.symbol ? '补齐中...' : '补齐数据' }}
            </button>
            <button
              class="btn btn-sm btn-danger"
              :disabled="deletingSymbol === row.symbol"
              @click="deleteRow(row)"
            >
              {{ deletingSymbol === row.symbol ? '处理中...' : (row.watched ? '从关注与库存删除' : '仅删库存') }}
            </button>
          </div>
        </div>

        <div class="inventory-grid">
          <section class="inventory-panel">
            <div class="panel-title">现货</div>
            <DataHealthSummary
              :row="row.healthRow"
              inst-type="SPOT"
              :inst-id="row.spot_inst_id"
              compact
            />
            <div class="panel-value">{{ formatMarketCoverage(row.markets?.SPOT, row.spot_inst_id) }}</div>
            <div class="panel-targets">
              <template v-if="row.watched && getMarketMissingPlans(row, 'SPOT').length > 0">
                <button
                  v-for="timeframe in getMarketMissingPlans(row, 'SPOT')"
                  :key="`inventory-spot-${row.symbol}-${timeframe}`"
                  type="button"
                  class="sync-plan-chip"
                  :class="{ 'is-running': !!findActiveSyncJob(row, 'SPOT', timeframe) || isSyncingTarget(row, 'SPOT', timeframe) }"
                  :disabled="!!findActiveSyncJob(row, 'SPOT', timeframe) || isSyncingTarget(row, 'SPOT', timeframe)"
                  @click="runTargetedSync(row, 'SPOT', timeframe)"
                >
                  <span>{{ timeframe }}</span>
                  <span v-if="findActiveSyncJob(row, 'SPOT', timeframe)">
                    {{ formatJobStatus(findActiveSyncJob(row, 'SPOT', timeframe)) }}
                  </span>
                  <span v-else-if="isSyncingTarget(row, 'SPOT', timeframe)">创建中</span>
                </button>
              </template>
              <span v-else-if="row.watched" class="panel-note">关键周期齐</span>
              <span v-else class="panel-note">先加入关注后再定向补齐</span>
            </div>
          </section>
          <section class="inventory-panel">
            <div class="panel-title">永续</div>
            <DataHealthSummary
              :row="row.healthRow"
              inst-type="SWAP"
              :inst-id="row.swap_inst_id"
              compact
            />
            <div class="panel-value">{{ formatMarketCoverage(row.markets?.SWAP, row.swap_inst_id) }}</div>
            <div class="panel-targets">
              <template v-if="row.watched && getMarketMissingPlans(row, 'SWAP').length > 0">
                <button
                  v-for="timeframe in getMarketMissingPlans(row, 'SWAP')"
                  :key="`inventory-swap-${row.symbol}-${timeframe}`"
                  type="button"
                  class="sync-plan-chip"
                  :class="{ 'is-running': !!findActiveSyncJob(row, 'SWAP', timeframe) || isSyncingTarget(row, 'SWAP', timeframe) }"
                  :disabled="!!findActiveSyncJob(row, 'SWAP', timeframe) || isSyncingTarget(row, 'SWAP', timeframe)"
                  @click="runTargetedSync(row, 'SWAP', timeframe)"
                >
                  <span>{{ timeframe }}</span>
                  <span v-if="findActiveSyncJob(row, 'SWAP', timeframe)">
                    {{ formatJobStatus(findActiveSyncJob(row, 'SWAP', timeframe)) }}
                  </span>
                  <span v-else-if="isSyncingTarget(row, 'SWAP', timeframe)">创建中</span>
                </button>
              </template>
              <span v-else-if="row.watched" class="panel-note">关键周期齐</span>
              <span v-else class="panel-note">先加入关注后再定向补齐</span>
            </div>
          </section>
          <section class="inventory-panel">
            <div class="panel-title">非 K 线记录</div>
            <div class="storage-chip-grid">
              <span class="storage-chip">ticker {{ formatCount(row.storage_counts?.market_ticker_snapshots) }}</span>
              <span class="storage-chip">trades {{ formatCount(row.storage_counts?.market_recent_trades) }}</span>
              <span class="storage-chip">fills {{ formatCount(row.storage_counts?.local_fills) }}</span>
              <span class="storage-chip">orders {{ formatCount(row.storage_counts?.live_order_records) }}</span>
              <span class="storage-chip">backtests {{ formatCount(row.storage_counts?.backtest_results) }}</span>
              <span class="storage-chip">cost {{ formatCount(row.storage_counts?.cost_basis) }}</span>
            </div>
          </section>
        </div>

        <div v-if="row.activeJobs.length > 0" class="job-row">
          <span
            v-for="job in row.activeJobs.slice(0, 6)"
            :key="job.task_id"
            class="job-chip"
          >
            {{ job.inst_type }} · {{ job.timeframe }} · {{ formatJobStatus(job) }}
          </span>
        </div>
      </article>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { api } from '../services/api';
import AnalyticsDataInventoryCard from '../components/analytics/AnalyticsDataInventoryCard.vue';
import DataHealthSummary from '../components/data/DataHealthSummary.vue';
import { useGuardianSyncPlans, sortGuardianTimeframes } from '../composables/useGuardianSyncPlans';
import { useMarketDataHealthCatalog } from '../composables/useMarketDataHealthCatalog';
import { resolveDataHealthStatus } from '../utils/dataHealth';

defineOptions({
  name: 'InventoryView',
});

const router = useRouter();

const loading = ref(false);
const refreshing = ref(false);
const cleaningOrphans = ref(false);
const deletingSymbol = ref('');
const repairingSymbol = ref('');
const rows = ref([]);
const activeJobs = ref([]);
const summary = ref({
  symbol_count: 0,
  watched_symbol_count: 0,
  orphan_symbol_count: 0,
  total_candles: 0,
  total_timeframe_records: 0,
  table_totals: {},
});
const searchKeyword = ref('');
const scopeFilter = ref('all');
const successMessage = ref('');
const errorMessage = ref('');
const syncingTargetKey = ref('');

let pollTimer = null;
let loadInventoryPromise = null;
const {
  rowMap: dataHealthRowMap,
  error: dataHealthError,
  loadCatalog: loadDataHealthCatalog,
} = useMarketDataHealthCatalog();
const {
  planMap,
  enabledTimeframes,
  error: guardianPlansError,
  loadPlans,
} = useGuardianSyncPlans();

const formatCount = (value) => {
  const numeric = Number(value || 0);
  if (!Number.isFinite(numeric)) return '0';
  return new Intl.NumberFormat('zh-CN').format(Math.max(Math.round(numeric), 0));
};

const formatJobStatus = (job) => {
  const status = String(job?.status || '').toLowerCase();
  if (status === 'running') {
    return `${job?.progress || 0}%`;
  }
  if (status === 'completed') return '已完成';
  if (status === 'failed') return '失败';
  if (status === 'cancelled') return '已取消';
  return '排队中';
};

const normalizeSymbol = (symbol) => {
  const normalized = String(symbol || '').trim().toUpperCase();
  if (!normalized) return '';
  if (normalized.endsWith('-SWAP')) return normalized.slice(0, -5);
  if (!normalized.includes('-')) return `${normalized}-USDT`;
  return normalized;
};

const formatMarketCoverage = (market, fallbackInstId) => {
  if (!market || !Array.isArray(market.timeframes) || market.timeframes.length === 0) {
    return `${fallbackInstId} 尚未入库`;
  }
  const timeframes = sortGuardianTimeframes(market.timeframes.map(item => item.timeframe)).join(' / ');
  const candleCount = formatCount(market.candle_count);
  const completeCount = Number(market.history_complete_count || 0);
  const completionText = completeCount > 0 ? ` · 已补齐 ${completeCount} 个周期` : '';
  return `${timeframes} · ${candleCount} 根${completionText}`;
};

const buildTargetSyncKey = (symbol, instType, timeframe) => `${symbol}:${instType}:${timeframe}`;

const getMarketPresentTimeframes = (row, instType) => (
  sortGuardianTimeframes(
    (row?.healthRow?.markets?.[instType]?.timeframes || [])
      .map(item => String(item?.timeframe || '').trim())
      .filter(Boolean),
  )
);

const getMarketMissingPlans = (row, instType) => {
  const present = new Set(getMarketPresentTimeframes(row, instType));
  return enabledTimeframes.value.filter(timeframe => !present.has(timeframe));
};

const findActiveSyncJob = (row, instType, timeframe) => {
  const instId = instType === 'SPOT' ? row?.spot_inst_id : row?.swap_inst_id;
  return row?.activeJobs?.find((job) => (
    job.inst_id === instId &&
    String(job.inst_type || '').toUpperCase() === instType &&
    String(job.timeframe || '').trim() === timeframe
  )) || null;
};

const isSyncingTarget = (row, instType, timeframe) => (
  syncingTargetKey.value === buildTargetSyncKey(row?.symbol, instType, timeframe)
);

const runTargetedSync = async (row, instType, timeframe) => {
  if (!row?.watched) {
    errorMessage.value = `${row?.symbol || '--'} 还未加入关注列表，不能定向补齐`;
    successMessage.value = '';
    return;
  }

  const instId = instType === 'SPOT' ? row?.spot_inst_id : row?.swap_inst_id;
  if (!instId) {
    errorMessage.value = `${row?.symbol || '--'} 缺少 ${instType} 产品标识，无法发起补齐`;
    successMessage.value = '';
    return;
  }

  const activeJob = findActiveSyncJob(row, instType, timeframe);
  if (activeJob) {
    successMessage.value = `${row.symbol} ${instType} ${timeframe} 已有运行中的补齐任务`;
    errorMessage.value = '';
    return;
  }

  clearMessages();
  const syncKey = buildTargetSyncKey(row.symbol, instType, timeframe);
  syncingTargetKey.value = syncKey;
  try {
    const plan = planMap.value.get(timeframe);
    await api.startSyncJob(instId, {
      instType,
      timeframe,
      days: Number(plan?.bootstrap_days) || (timeframe === '1m' ? 7 : 30),
      mode: plan?.archive_mode === 'full' ? 'full' : 'window',
    });
    successMessage.value = `${row.symbol} ${instType} ${timeframe} 已加入后台同步队列`;
    await loadInventory();
  } catch (error) {
    errorMessage.value = error?.response?.data?.detail || error?.message || '发起定向补齐失败';
  } finally {
    if (syncingTargetKey.value === syncKey) {
      syncingTargetKey.value = '';
    }
  }
};

const filteredRows = computed(() => {
  const keyword = normalizeSymbol(searchKeyword.value);
  return rows.value.filter((row) => {
    if (scopeFilter.value === 'watched' && !row.watched) return false;
    if (scopeFilter.value === 'orphan' && !row.orphan) return false;
    if (!keyword) return true;
    return row.symbol.includes(keyword) || row.base_ccy.includes(keyword.replace('-USDT', ''));
  });
});

const clearMessages = () => {
  successMessage.value = '';
  errorMessage.value = '';
};

const mergeInventoryRowsWithJobs = (inventoryRows, jobs) => (
  (inventoryRows || []).map(row => {
    const relatedInstIds = new Set([row.spot_inst_id, row.swap_inst_id]);
    return {
      ...row,
      healthRow: dataHealthRowMap.value.get(normalizeSymbol(row.symbol)) || null,
      spotHealthStatus: resolveDataHealthStatus(dataHealthRowMap.value.get(normalizeSymbol(row.symbol)), 'SPOT'),
      swapHealthStatus: resolveDataHealthStatus(dataHealthRowMap.value.get(normalizeSymbol(row.symbol)), 'SWAP'),
      activeJobs: (jobs || []).filter(job => relatedInstIds.has(job.inst_id)),
    };
  })
);

const loadInventory = async () => {
  if (loadInventoryPromise) {
    return loadInventoryPromise;
  }

  const firstLoad = rows.value.length === 0 && !loading.value;
  loading.value = firstLoad;
  refreshing.value = !firstLoad;

  loadInventoryPromise = (async () => {
    try {
      const [inventoryRes, jobsRes] = await Promise.all([
        api.getDataInventory(),
        api.getSyncJobs({ activeOnly: true, limit: 200 }),
        loadPlans(),
        loadDataHealthCatalog({ includeOrphans: true, force: true }),
      ]);

      const inventoryData = inventoryRes?.code === 0 ? inventoryRes.data || {} : {};
      const jobs = jobsRes?.code === 0 && Array.isArray(jobsRes.data) ? jobsRes.data : [];
      const inventoryRows = Array.isArray(inventoryData.rows) ? inventoryData.rows : [];

      activeJobs.value = jobs;
      summary.value = inventoryData.summary || summary.value;
      rows.value = mergeInventoryRowsWithJobs(inventoryRows, jobs);
      if (dataHealthError.value && !errorMessage.value) {
        errorMessage.value = dataHealthError.value;
      }
      if (guardianPlansError.value && !errorMessage.value) {
        errorMessage.value = guardianPlansError.value;
      }
    } catch (error) {
      errorMessage.value = error?.response?.data?.detail || error?.message || '读取数据库库存失败';
    } finally {
      loading.value = false;
      refreshing.value = false;
      loadInventoryPromise = null;
    }
  })();

  return loadInventoryPromise;
};

const deleteRow = async (row) => {
  const actionText = row.watched ? '从关注列表和数据库库存中删除' : '删除数据库库存';
  const confirmed = window.confirm(`确认${actionText} ${row.symbol} 吗？`);
  if (!confirmed) return;

  clearMessages();
  deletingSymbol.value = row.symbol;
  try {
    const res = await api.deleteInventorySymbol(row.symbol, {
      removeWatch: row.watched,
    });
    const deletedTotal = Number(res?.data?.deleted_counts?.total || 0);
    const cancelledJobCount = Array.isArray(res?.data?.active_sync_jobs) ? res.data.active_sync_jobs.length : 0;
    successMessage.value = row.watched
      ? `${row.symbol} 已从关注与库存删除，共清理 ${formatCount(deletedTotal)} 条记录${cancelledJobCount > 0 ? `；已取消 ${cancelledJobCount} 个后台任务` : ''}`
      : `${row.symbol} 的库存已删除，共清理 ${formatCount(deletedTotal)} 条记录${cancelledJobCount > 0 ? `；已取消 ${cancelledJobCount} 个后台任务` : ''}`;
    await loadInventory();
  } catch (error) {
    errorMessage.value = error?.response?.data?.detail || error?.message || '删除库存失败';
  } finally {
    deletingSymbol.value = '';
  }
};

const cleanOrphans = async () => {
  const orphanCount = Number(summary.value.orphan_symbol_count || 0);
  if (orphanCount <= 0) return;

  const confirmed = window.confirm(`确认清理全部 ${orphanCount} 个未关注孤儿币种的库存数据吗？`);
  if (!confirmed) return;

  clearMessages();
  cleaningOrphans.value = true;
  try {
    const res = await api.deleteOrphanInventory();
    const deletedSymbolCount = Number(res?.data?.deleted_symbol_count || 0);
    const deletedTotal = Number(res?.data?.deleted_counts?.total || 0);
    successMessage.value = `已清理 ${deletedSymbolCount} 个孤儿币种，共删除 ${formatCount(deletedTotal)} 条记录`;
    await loadInventory();
  } catch (error) {
    errorMessage.value = error?.response?.data?.detail || error?.message || '清理孤儿数据失败';
  } finally {
    cleaningOrphans.value = false;
  }
};

const repairRow = async (row) => {
  const syncSpot = row.spotHealthStatus !== 'healthy';
  const syncSwap = row.swapHealthStatus !== 'healthy';
  if (!syncSpot && !syncSwap) {
    successMessage.value = `${row.symbol} 当前数据已健康，无需补齐`;
    errorMessage.value = '';
    return;
  }

  clearMessages();
  repairingSymbol.value = row.symbol;
  try {
    const res = await api.repairWatchedSymbol(row.symbol, {
      syncSpot,
      syncSwap,
    });
    const startedCount = Number(res?.data?.started_count || 0);
    const reusedCount = Number(res?.data?.reused_count || 0);
    successMessage.value = startedCount > 0
      ? `${row.symbol} 已重新发起回补，新增 ${formatCount(startedCount)} 个任务${reusedCount > 0 ? `，复用 ${formatCount(reusedCount)} 个运行中任务` : ''}`
      : `${row.symbol} 的回补请求已提交${reusedCount > 0 ? `，复用 ${formatCount(reusedCount)} 个运行中任务` : ''}`;
    await loadInventory();
  } catch (error) {
    errorMessage.value = error?.response?.data?.detail || error?.message || '重新发起回补失败';
  } finally {
    repairingSymbol.value = '';
  }
};

const openMarket = async (symbol) => {
  await router.push({ path: '/', query: { symbol } });
};

const openWatchlist = async (symbol) => {
  await router.push({
    path: '/data',
    query: {
      tab: 'watchlist',
      symbol,
    },
  });
};

onMounted(async () => {
  await loadInventory();
  pollTimer = window.setInterval(() => {
    void loadInventory();
  }, 4000);
});

onUnmounted(() => {
  if (pollTimer) {
    window.clearInterval(pollTimer);
    pollTimer = null;
  }
});
</script>

<style scoped>
.inventory-view {
  display: flex;
  flex-direction: column;
  gap: 14px;
  height: 100%;
  padding: 14px 6px;
  color: var(--text-primary);
}

/* 工具栏 — 紧凑一体 */
.inv-toolbar {
  flex-shrink: 0;
  padding: 12px 16px;
  border-radius: var(--radius-lg);
  border: 1px solid rgba(255, 255, 255, 0.06);
  background: var(--bg-secondary);
}

.inv-toolbar-row {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.inv-inputs {
  display: flex;
  align-items: center;
  gap: 8px;
}

.inv-input {
  width: 180px;
  padding: 8px 12px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
  background: rgba(0, 0, 0, 0.3);
  color: var(--text-primary);
  font-size: 12px;
}

.inv-input:focus {
  border-color: var(--accent-color);
  outline: none;
  box-shadow: 0 0 0 3px rgba(247, 147, 26, 0.12);
}

.inv-select {
  min-width: 100px;
  padding: 8px 12px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
  background: rgba(0, 0, 0, 0.3);
  color: var(--text-primary);
  font-size: 12px;
}

.inv-stats {
  display: flex;
  align-items: center;
  gap: 6px;
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-secondary);
  margin-left: auto;
}

.inv-stat strong {
  color: var(--text-primary);
  font-size: 13px;
  margin-right: 2px;
}

.inv-stat.danger strong {
  color: var(--color-danger);
}

.inv-stat-sep {
  color: rgba(255, 255, 255, 0.1);
}

.inv-actions {
  display: flex;
  gap: 6px;
}

.inv-feedback {
  margin-top: 8px;
  font-size: 12px;
}

.feedback-success {
  color: var(--color-success);
}

.feedback-error {
  color: var(--color-danger);
}

/* 空状态 */
.inv-empty {
  display: grid;
  place-items: center;
  min-height: 200px;
  border-radius: var(--radius-lg);
  border: 1px dashed var(--border-color);
  background: rgba(15, 17, 21, 0.5);
  color: var(--text-secondary);
}

.inventory-title {
  margin: 10px 0 8px;
  font-size: 32px;
  line-height: 1.1;
}

.inventory-subtitle {
  max-width: 760px;
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.6;
}

.inventory-summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(140px, 1fr));
  gap: 12px;
  min-width: 460px;
}

.summary-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 16px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.summary-label {
  color: var(--text-muted);
  font-size: 12px;
}

.summary-value {
  font-size: 24px;
}

.summary-value.danger {
  color: var(--color-danger);
}

.inventory-toolbar,
.inventory-feedback {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  padding: 16px 18px;
  border-radius: 18px;
  border: 1px solid var(--border-color);
  background: var(--bg-card);
}

.toolbar-left,
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.inventory-input {
  width: 320px;
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid var(--border-color);
  background: rgba(255, 255, 255, 0.02);
  color: var(--text-primary);
}

.inventory-select {
  min-width: 140px;
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid var(--border-color);
  background: rgba(255, 255, 255, 0.02);
  color: var(--text-primary);
}

.feedback-success {
  color: var(--color-success);
}

.feedback-error {
  color: var(--color-danger);
}

.feedback-muted {
  color: var(--text-muted);
}

.inventory-empty {
  display: grid;
  place-items: center;
  min-height: 280px;
  border-radius: 24px;
  border: 1px dashed var(--border-color);
  background: rgba(15, 17, 21, 0.7);
  color: var(--text-secondary);
  text-align: center;
}

.empty-title {
  font-size: 22px;
  color: var(--text-primary);
}

.empty-text {
  margin-top: 8px;
}

.inventory-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-height: 0;
  overflow: auto;
}

.inventory-row {
  padding: 18px 20px;
  border-radius: 20px;
  border: 1px solid var(--border-color);
  background: rgba(15, 17, 21, 0.94);
}

.inventory-row-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.symbol-line,
.symbol-meta,
.job-row,
.storage-chip-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.symbol-name {
  font-size: 22px;
  font-weight: 700;
}

.symbol-meta {
  margin-top: 10px;
  color: var(--text-muted);
  font-size: 12px;
}

.state-badge,
.job-chip,
.storage-chip {
  padding: 6px 10px;
  border-radius: 999px;
  font-size: 12px;
}

.badge-watched {
  background: rgba(34, 197, 94, 0.14);
  color: var(--color-success);
}

.badge-orphan {
  background: rgba(239, 68, 68, 0.14);
  color: var(--color-danger);
}

.badge-plain {
  background: rgba(255, 255, 255, 0.05);
  color: var(--text-secondary);
}

.inventory-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-top: 16px;
}

.inventory-panel {
  padding: 14px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.panel-title {
  font-size: 12px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.panel-value {
  margin-top: 10px;
  line-height: 1.6;
}

.panel-note {
  margin-top: 8px;
  color: var(--text-muted);
  font-size: 12px;
}

.panel-targets {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.sync-plan-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 30px;
  padding: 0 10px;
  border: 1px solid rgba(247, 147, 26, 0.18);
  border-radius: 999px;
  background: var(--accent-bg);
  color: var(--gold-color);
  font-size: 12px;
  cursor: pointer;
  transition: transform 0.16s ease, border-color 0.16s ease, background 0.16s ease;
}

.sync-plan-chip:hover:not(:disabled) {
  transform: translateY(-1px);
  border-color: rgba(247, 147, 26, 0.34);
  background: rgba(247, 147, 26, 0.16);
}

.sync-plan-chip:disabled,
.sync-plan-chip.is-running {
  cursor: default;
  border-color: rgba(59, 130, 246, 0.28);
  background: rgba(59, 130, 246, 0.12);
  color: var(--color-info);
}

.storage-chip-grid {
  margin-top: 10px;
}

.storage-chip,
.job-chip {
  background: rgba(255, 255, 255, 0.04);
  color: var(--text-secondary);
}

.job-row {
  margin-top: 14px;
}

.row-actions {
  display: flex;
  gap: 10px;
}

.btn-sm {
  padding: 8px 12px;
}

.btn-danger {
  border-color: rgba(239, 68, 68, 0.24);
  color: var(--color-danger);
}

@media (max-width: 1280px) {
  .inventory-hero {
    flex-direction: column;
  }

  .inventory-summary-grid {
    min-width: 0;
  }
}

@media (max-width: 900px) {
  .inventory-view {
    padding: 16px;
  }

  .inventory-toolbar,
  .inventory-feedback,
  .inventory-row-head {
    flex-direction: column;
    align-items: stretch;
  }

  .toolbar-left,
  .toolbar-right {
    flex-wrap: wrap;
  }

  .inventory-input {
    width: 100%;
  }

  .inventory-grid {
    grid-template-columns: 1fr;
  }

  .row-actions {
    flex-wrap: wrap;
  }
}
</style>
