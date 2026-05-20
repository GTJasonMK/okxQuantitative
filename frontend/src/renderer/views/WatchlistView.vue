<template>
  <div class="watchlist-view">
    <!-- 统计条 + 工具栏 合并为一个紧凑区域 -->
    <section class="wl-toolbar">
      <div class="wl-toolbar-row">
        <div class="wl-inputs">
          <input
            v-model.trim="newSymbol"
            type="text"
            class="wl-input"
            placeholder="输入 BTC / BTC-USDT"
            @keyup.enter="addSymbol"
          />
          <label class="archive-toggle" title="开启后会拉取该币从发行至今的所有历史K线">
            <input type="checkbox" v-model="newArchiveAll" />
            <span>全量归档</span>
          </label>
          <button class="btn btn-primary btn-sm" :disabled="adding || !newSymbol" @click="addSymbol">
            {{ adding ? '添加中...' : '添加' }}
          </button>
        </div>
        <div class="wl-stats">
          <span class="wl-stat"><strong>{{ watchedSymbols.length }}</strong> 关注</span>
          <span class="wl-stat-sep">/</span>
          <span class="wl-stat"><strong>{{ readySpotCount }}</strong> 现货</span>
          <span class="wl-stat-sep">/</span>
          <span class="wl-stat"><strong>{{ readySwapCount }}</strong> 永续</span>
          <span class="wl-stat-sep">/</span>
          <span class="wl-stat warning"><strong>{{ gapMarketCount }}</strong> 待补</span>
          <span class="wl-stat-sep">/</span>
          <span class="wl-stat"><strong>{{ activeJobs.length }}</strong> 任务</span>
        </div>
        <div class="wl-actions">
          <button class="btn btn-sm" :disabled="refreshing" @click="loadPageData">
            {{ refreshing ? '刷新中' : '刷新' }}
          </button>
          <button class="btn btn-sm" :disabled="repairingAll" @click="repairAllData">
            {{ repairingAll ? '请求中' : '后台补齐' }}
          </button>
        </div>
      </div>
      <div v-if="successMessage || errorMessage" class="wl-feedback">
        <span v-if="successMessage" class="note-success">{{ successMessage }}</span>
        <span v-else-if="errorMessage" class="note-error">{{ errorMessage }}</span>
      </div>
    </section>

    <!-- 空状态 -->
    <section v-if="loading && rows.length === 0" class="wl-empty">
      正在加载关注币种...
    </section>
    <section v-else-if="rows.length === 0" class="wl-empty">
      <div class="empty-title">还没有关注币种</div>
      <div class="empty-text">在上方输入交易对，系统会自动拉起全量历史同步。</div>
    </section>

    <!-- 表格 -->
    <section v-else class="wl-table-shell">
      <div class="watchlist-table">
        <div class="watchlist-table-head">
          <span>币种</span>
          <span>现货数据</span>
          <span>永续数据</span>
          <span>后台任务</span>
          <span>操作</span>
        </div>

        <article v-for="row in rows" :key="row.symbol" class="watchlist-row">
          <div class="watchlist-symbol">
            <div class="symbol-main">
              {{ row.symbol }}
              <span v-if="row.archive_all_history" class="archive-badge" title="全量归档：拉取从发行至今所有历史">归档</span>
            </div>
            <div class="symbol-meta">
              <span>{{ row.base_ccy }}</span>
              <span>添加于 {{ formatTime(row.created_at) }}</span>
            </div>
          </div>

          <div class="watchlist-coverage">
            <div class="coverage-title">SPOT</div>
            <div class="coverage-line">{{ formatCoverage(row.spotCoverage) }}</div>
            <DataHealthSummary class="coverage-health" :row="row.healthRow" inst-type="SPOT" :inst-id="row.spot_inst_id" compact />
            <div class="coverage-targets">
              <template v-if="row.sync_spot === false">
                <span class="sync-plan-note">未启用</span>
              </template>
              <template v-else-if="getMarketMissingPlans(row, 'SPOT').length > 0">
                <button
                  v-for="timeframe in getMarketMissingPlans(row, 'SPOT')"
                  :key="`spot-${row.symbol}-${timeframe}`"
                  type="button"
                  class="sync-plan-chip"
                  :class="{ 'is-running': !!findActiveSyncJob(row, 'SPOT', timeframe) || isSyncingTarget(row, 'SPOT', timeframe) }"
                  :disabled="!!findActiveSyncJob(row, 'SPOT', timeframe) || isSyncingTarget(row, 'SPOT', timeframe)"
                  @click="runTargetedSync(row, 'SPOT', timeframe)"
                >
                  <span>{{ timeframe }}</span>
                  <span v-if="findActiveSyncJob(row, 'SPOT', timeframe)">{{ formatJobStatus(findActiveSyncJob(row, 'SPOT', timeframe)) }}</span>
                  <span v-else-if="isSyncingTarget(row, 'SPOT', timeframe)">创建中</span>
                </button>
              </template>
              <span v-else class="sync-plan-note">周期齐全</span>
            </div>
          </div>

          <div class="watchlist-coverage">
            <div class="coverage-title">SWAP</div>
            <div class="coverage-line">{{ formatCoverage(row.swapCoverage) }}</div>
            <DataHealthSummary class="coverage-health" :row="row.healthRow" inst-type="SWAP" :inst-id="row.swap_inst_id" compact />
            <div class="coverage-targets">
              <template v-if="row.sync_swap === false">
                <span class="sync-plan-note">未启用</span>
              </template>
              <template v-else-if="getMarketMissingPlans(row, 'SWAP').length > 0">
                <button
                  v-for="timeframe in getMarketMissingPlans(row, 'SWAP')"
                  :key="`swap-${row.symbol}-${timeframe}`"
                  type="button"
                  class="sync-plan-chip"
                  :class="{ 'is-running': !!findActiveSyncJob(row, 'SWAP', timeframe) || isSyncingTarget(row, 'SWAP', timeframe) }"
                  :disabled="!!findActiveSyncJob(row, 'SWAP', timeframe) || isSyncingTarget(row, 'SWAP', timeframe)"
                  @click="runTargetedSync(row, 'SWAP', timeframe)"
                >
                  <span>{{ timeframe }}</span>
                  <span v-if="findActiveSyncJob(row, 'SWAP', timeframe)">{{ formatJobStatus(findActiveSyncJob(row, 'SWAP', timeframe)) }}</span>
                  <span v-else-if="isSyncingTarget(row, 'SWAP', timeframe)">创建中</span>
                </button>
              </template>
              <span v-else class="sync-plan-note">周期齐全</span>
            </div>
          </div>

          <div class="watchlist-jobs">
            <template v-if="row.activeJobs.length > 0">
              <div v-for="job in row.activeJobs.slice(0, 4)" :key="job.task_id" class="job-chip">
                {{ job.inst_type }} · {{ job.timeframe }} · {{ formatJobStatus(job) }}
              </div>
            </template>
            <span v-else class="job-chip job-chip-idle">空闲</span>
          </div>

          <div class="watchlist-actions">
            <button class="btn btn-sm" @click="openMarket(row.symbol)">行情</button>
            <button class="btn btn-sm" :disabled="repairingSymbol === row.symbol" @click="repairSymbolData(row)">
              {{ repairingSymbol === row.symbol ? '补齐中' : '补齐' }}
            </button>
            <button class="btn btn-sm btn-danger" :disabled="deletingSymbol === row.symbol" @click="deleteSymbol(row.symbol)">
              {{ deletingSymbol === row.symbol ? '删除中' : '删除' }}
            </button>
          </div>
        </article>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { api } from '../services/api';
import DataHealthSummary from '../components/data/DataHealthSummary.vue';
import { useGuardianSyncPlans, sortGuardianTimeframes } from '../composables/useGuardianSyncPlans';
import { useMarketDataHealthCatalog } from '../composables/useMarketDataHealthCatalog';
import { resolveDataHealthStatus } from '../utils/dataHealth';

defineOptions({
  name: 'WatchlistView',
});

const router = useRouter();
const route = useRoute();

const watchedSymbols = ref([]);
const syncStatus = ref([]);
const activeJobs = ref([]);
const loading = ref(false);
const refreshing = ref(false);
const adding = ref(false);
const deletingSymbol = ref('');
const repairingSymbol = ref('');
const repairingAll = ref(false);
const newSymbol = ref('');
const newArchiveAll = ref(false);
const errorMessage = ref('');
const successMessage = ref('');
const syncingTargetKey = ref('');
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

let pollTimer = null;
let loadPageDataPromise = null;
const normalizeSymbol = (symbol) => {
  const normalized = String(symbol || '').trim().toUpperCase();
  if (!normalized) return '';
  if (normalized.endsWith('-SWAP')) return normalized.slice(0, -5);
  if (!normalized.includes('-')) return `${normalized}-USDT`;
  return normalized;
};

const formatTime = (value) => {
  if (!value) return '--';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return '--';
  return parsed.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
};

const formatCount = (value) => {
  const numeric = Number(value || 0);
  if (!Number.isFinite(numeric) || numeric <= 0) return '0';
  return new Intl.NumberFormat('zh-CN').format(Math.round(numeric));
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

const buildCoverage = (instId, instType) => {
  const records = syncStatus.value.filter(item => item.inst_id === instId && item.inst_type === instType);
  const sortedTimeframes = sortGuardianTimeframes(records.map(item => item.timeframe));

  const totalCandles = records.reduce((sum, item) => sum + Number(item.candle_count || 0), 0);
  const historyCompleted = records.filter(item => item.history_complete).length;
  const latestSyncTime = [...records]
    .map(item => item.last_sync_time)
    .filter(Boolean)
    .sort()
    .at(-1) || '';

  return {
    timeframes: sortedTimeframes,
    totalCandles,
    historyCompleted,
    latestSyncTime,
  };
};

const rows = computed(() => (
  watchedSymbols.value.map(item => {
    const spotCoverage = buildCoverage(item.spot_inst_id, 'SPOT');
    const swapCoverage = buildCoverage(item.swap_inst_id, 'SWAP');
    const relatedInstIds = new Set([item.spot_inst_id, item.swap_inst_id]);

    return {
      ...item,
      healthRow: dataHealthRowMap.value.get(item.symbol) || null,
      spotHealthStatus: resolveDataHealthStatus(dataHealthRowMap.value.get(item.symbol), 'SPOT'),
      swapHealthStatus: resolveDataHealthStatus(dataHealthRowMap.value.get(item.symbol), 'SWAP'),
      spotCoverage,
      swapCoverage,
      activeJobs: activeJobs.value.filter(job => relatedInstIds.has(job.inst_id)),
    };
  })
));

const readySpotCount = computed(() => (
  rows.value.filter(item => item.spotCoverage.timeframes.length > 0).length
));

const readySwapCount = computed(() => (
  rows.value.filter(item => item.swapCoverage.timeframes.length > 0).length
));

const gapMarketCount = computed(() => (
  rows.value.reduce((count, row) => {
    let next = count;
    if (row.sync_spot !== false && row.spotHealthStatus !== 'healthy') {
      next += 1;
    }
    if (row.sync_swap !== false && row.swapHealthStatus !== 'healthy') {
      next += 1;
    }
    return next;
  }, 0)
));

const formatCoverage = (coverage) => {
  if (!coverage.timeframes.length) {
    return '尚未落库';
  }
  const completedSuffix = coverage.historyCompleted > 0 ? ` · 已补齐 ${coverage.historyCompleted} 个周期` : '';
  const latestSuffix = coverage.latestSyncTime ? ` · 更新 ${formatTime(coverage.latestSyncTime)}` : '';
  return `${coverage.timeframes.join(' / ')} · ${formatCount(coverage.totalCandles)} 根${completedSuffix}${latestSuffix}`;
};

const buildTargetSyncKey = (symbol, instType, timeframe) => `${symbol}:${instType}:${timeframe}`;

const getMarketPresentTimeframes = (row, instType) => {
  const market = row?.healthRow?.markets?.[instType];
  return sortGuardianTimeframes((market?.timeframes || []).map(item => item?.timeframe));
};

const getMarketMissingPlans = (row, instType) => {
  if (!row) return [];
  if (instType === 'SPOT' && row.sync_spot === false) return [];
  if (instType === 'SWAP' && row.sync_swap === false) return [];
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
    await loadPageData();
  } catch (error) {
    errorMessage.value = error?.response?.data?.detail || error?.message || '发起定向补齐失败';
  } finally {
    if (syncingTargetKey.value === syncKey) {
      syncingTargetKey.value = '';
    }
  }
};

const clearMessages = () => {
  errorMessage.value = '';
  successMessage.value = '';
};

const applyRouteSymbolPrefill = () => {
  const routeSymbol = normalizeSymbol(route.query.symbol);
  if (!routeSymbol) return;
  newSymbol.value = routeSymbol;
};

const loadPageData = async () => {
  if (loadPageDataPromise) {
    return loadPageDataPromise;
  }

  const firstLoad = watchedSymbols.value.length === 0 && !loading.value;
  loading.value = firstLoad;
  refreshing.value = !firstLoad;

  loadPageDataPromise = (async () => {
    try {
      const [watchlistRes, syncStatusRes, jobsRes] = await Promise.all([
        api.getWatchedSymbols(),
        api.getSyncStatus(),
        api.getSyncJobs({ activeOnly: true, limit: 200 }),
        loadPlans(),
        loadDataHealthCatalog({ includeOrphans: false, force: true }),
      ]);

      watchedSymbols.value = watchlistRes.code === 0 && Array.isArray(watchlistRes.data)
        ? watchlistRes.data.map(item => ({
            ...item,
            symbol: normalizeSymbol(item.symbol),
            base_ccy: item.base_ccy || normalizeSymbol(item.symbol).split('-')[0],
            spot_inst_id: item.spot_inst_id || normalizeSymbol(item.symbol),
            swap_inst_id: item.swap_inst_id || `${normalizeSymbol(item.symbol)}-SWAP`,
          }))
        : [];

      syncStatus.value = syncStatusRes.code === 0 && Array.isArray(syncStatusRes.data)
        ? syncStatusRes.data
        : [];

      activeJobs.value = jobsRes.code === 0 && Array.isArray(jobsRes.data)
        ? jobsRes.data
        : [];

      if (dataHealthError.value && !errorMessage.value) {
        errorMessage.value = dataHealthError.value;
      }
      if (guardianPlansError.value && !errorMessage.value) {
        errorMessage.value = guardianPlansError.value;
      }
    } catch (error) {
      errorMessage.value = error?.response?.data?.detail || error?.message || '加载关注币种失败';
    } finally {
      loading.value = false;
      refreshing.value = false;
      loadPageDataPromise = null;
    }
  })();

  return loadPageDataPromise;
};

const addSymbol = async () => {
  const symbol = normalizeSymbol(newSymbol.value);
  if (!symbol) return;

  clearMessages();
  adding.value = true;
  try {
    const res = await api.addWatchedSymbol(symbol, {
      syncSpot: true,
      syncSwap: true,
      archiveAllHistory: newArchiveAll.value,
    });
    const syncJobs = Array.isArray(res?.data?.sync_jobs) ? res.data.sync_jobs.length : 0;
    successMessage.value = res?.data?.existed
      ? `${symbol} 已在关注列表中`
      : `${symbol} 已加入关注，已启动 ${syncJobs} 个后台同步任务`;
    newSymbol.value = '';
    newArchiveAll.value = false;
    await loadPageData();
  } catch (error) {
    errorMessage.value = error?.response?.data?.detail || error?.message || '添加关注币种失败';
  } finally {
    adding.value = false;
  }
};

const buildRepairTargets = (row) => ({
  syncSpot: row.sync_spot !== false && row.spotHealthStatus !== 'healthy',
  syncSwap: row.sync_swap !== false && row.swapHealthStatus !== 'healthy',
});

const repairSymbolData = async (row) => {
  const targets = buildRepairTargets(row);
  if (!targets.syncSpot && !targets.syncSwap) {
    successMessage.value = `${row.symbol} 当前关键周期已覆盖，无需补齐`;
    errorMessage.value = '';
    return;
  }

  clearMessages();
  repairingSymbol.value = row.symbol;
  try {
    const res = await api.repairWatchedSymbol(row.symbol, targets);
    const startedCount = Number(res?.data?.started_count || 0);
    const reusedCount = Number(res?.data?.reused_count || 0);
    const marketLabels = [
      targets.syncSpot ? '现货' : '',
      targets.syncSwap ? '永续' : '',
    ].filter(Boolean).join(' / ');
    successMessage.value = startedCount > 0
      ? `${row.symbol} 已重新发起 ${marketLabels} 回补，新增 ${startedCount} 个任务${reusedCount > 0 ? `，复用 ${reusedCount} 个运行中任务` : ''}`
      : `${row.symbol} 的 ${marketLabels} 回补请求已提交${reusedCount > 0 ? `，复用 ${reusedCount} 个运行中任务` : ''}`;
    await loadPageData();
  } catch (error) {
    errorMessage.value = error?.response?.data?.detail || error?.message || '重新发起回补失败';
  } finally {
    repairingSymbol.value = '';
  }
};

const repairAllData = async () => {
  clearMessages();
  repairingAll.value = true;
  try {
    await api.runDataGuardianNow();
    successMessage.value = '已请求后台守护器立即扫描并补齐当前关注清单的数据缺口';
    await loadPageData();
  } catch (error) {
    errorMessage.value = error?.response?.data?.detail || error?.message || '请求后台补齐失败';
  } finally {
    repairingAll.value = false;
  }
};

const deleteSymbol = async (symbol) => {
  if (!window.confirm(`确认删除 ${symbol} 吗？这会清理该币种的本地历史、快照、成交和回测数据。`)) {
    return;
  }

  clearMessages();
  deletingSymbol.value = symbol;
  try {
    const res = await api.deleteWatchedSymbol(symbol);
    const deletedTotal = Number(res?.data?.deleted_counts?.total || 0);
    const cancelledJobCount = Array.isArray(res?.data?.active_sync_jobs) ? res.data.active_sync_jobs.length : 0;
    successMessage.value = cancelledJobCount > 0
      ? `${symbol} 已删除，本地共清理 ${formatCount(deletedTotal)} 条数据；已取消 ${cancelledJobCount} 个相关后台任务`
      : `${symbol} 已删除，本地共清理 ${formatCount(deletedTotal)} 条数据`;
    await loadPageData();
  } catch (error) {
    errorMessage.value = error?.response?.data?.detail || error?.message || '删除关注币种失败';
  } finally {
    deletingSymbol.value = '';
  }
};

const openMarket = async (symbol) => {
  await router.push({ path: '/', query: { symbol } });
};

onMounted(async () => {
  applyRouteSymbolPrefill();
  await loadPageData();
  pollTimer = window.setInterval(() => {
    void loadPageData();
  }, 3000);
});

watch(
  () => route.query.symbol,
  () => {
    applyRouteSymbolPrefill();
  },
);

onUnmounted(() => {
  if (pollTimer) {
    window.clearInterval(pollTimer);
    pollTimer = null;
  }
});
</script>

<style scoped>
.watchlist-view {
  display: flex;
  flex-direction: column;
  gap: 14px;
  height: 100%;
  padding: 14px 6px;
  color: var(--text-primary);
}

/* 工具栏 — 紧凑一体 */
.wl-toolbar {
  flex-shrink: 0;
  padding: 12px 16px;
  border-radius: var(--radius-lg);
  border: 1px solid rgba(255, 255, 255, 0.06);
  background: var(--bg-secondary);
}

.wl-toolbar-row {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.wl-inputs {
  display: flex;
  align-items: center;
  gap: 8px;
}

.wl-input {
  width: 220px;
  padding: 8px 12px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
  background: rgba(0, 0, 0, 0.3);
  color: var(--text-primary);
  font-size: 12px;
}

.wl-input:focus {
  border-color: var(--accent-color);
  outline: none;
  box-shadow: 0 0 0 3px rgba(247, 147, 26, 0.12);
}

.wl-stats {
  display: flex;
  align-items: center;
  gap: 6px;
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-secondary);
  margin-left: auto;
}

.wl-stat strong {
  color: var(--text-primary);
  font-size: 13px;
  margin-right: 2px;
}

.wl-stat.warning strong {
  color: var(--gold-color);
}

.wl-stat-sep {
  color: rgba(255, 255, 255, 0.1);
}

.wl-actions {
  display: flex;
  gap: 6px;
}

.wl-feedback {
  margin-top: 8px;
  font-size: 12px;
}

/* 空状态 */
.wl-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  color: var(--text-secondary);
}

/* 表格容器 — 占满剩余空间 */
.wl-table-shell {
  flex: 1;
  min-height: 0;
  overflow: auto;
}

.archive-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-family: var(--font-mono);
  color: var(--text-secondary);
  cursor: pointer;
  user-select: none;
  padding: 4px 12px;
  border-radius: var(--radius-pill);
  border: 1px solid var(--border-color);
  transition: all 0.2s ease;
}

.archive-toggle:hover {
  border-color: rgba(247, 147, 26, 0.3);
  color: var(--accent-color);
}

.archive-toggle input[type="checkbox"] {
  accent-color: var(--accent-color);
  cursor: pointer;
}

.archive-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  margin-left: 6px;
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 500;
  border-radius: var(--radius-pill);
  background: rgba(247, 147, 26, 0.12);
  color: var(--accent-color);
  border: 1px solid rgba(247, 147, 26, 0.25);
  letter-spacing: 0.5px;
}

.watchlist-notes {
  min-height: 22px;
  text-align: right;
}

.note-success {
  color: var(--color-success);
}

.note-error {
  color: var(--color-danger);
}

.note-muted {
  color: var(--text-muted);
}

.watchlist-empty {
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
  max-width: 560px;
}

.watchlist-table-shell {
  flex: 1;
  min-height: 0;
  border-radius: 24px;
  border: 1px solid var(--border-color);
  background: rgba(15, 17, 21, 0.94);
  overflow: auto;
}

.watchlist-table {
  min-width: 1080px;
}

.watchlist-table-head,
.watchlist-row {
  display: grid;
  grid-template-columns: 1.4fr 1.2fr 1.2fr 1fr 180px;
  gap: 16px;
  align-items: center;
  padding: 16px 20px;
}

.watchlist-table-head {
  position: sticky;
  top: 0;
  z-index: 1;
  background: rgba(3, 3, 4, 0.98);
  color: var(--text-muted);
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.watchlist-row {
  border-top: 1px solid rgba(255, 255, 255, 0.05);
}

.watchlist-row:hover {
  background: rgba(247, 147, 26, 0.04);
}

.symbol-main {
  font-size: 20px;
  font-weight: 700;
}

.symbol-meta {
  display: flex;
  gap: 12px;
  margin-top: 8px;
  color: var(--text-muted);
  font-size: 12px;
}

.watchlist-coverage {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.coverage-title {
  font-size: 12px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.coverage-line {
  line-height: 1.5;
}

.coverage-line-soft {
  color: var(--text-muted);
  font-size: 12px;
}

.coverage-health {
  margin-top: 8px;
}

.coverage-targets {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 2px;
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

.sync-plan-note {
  color: var(--text-muted);
  font-size: 12px;
}

.watchlist-jobs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.job-chip {
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(59, 130, 246, 0.14);
  color: var(--color-info);
  font-size: 12px;
}

.job-chip-idle {
  background: rgba(255, 255, 255, 0.05);
  color: var(--text-muted);
}

.watchlist-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.btn-sm {
  padding: 8px 12px;
}

.btn-danger {
  border-color: rgba(239, 68, 68, 0.24);
  color: var(--color-danger);
}

@media (max-width: 1200px) {
  .watchlist-header {
    flex-direction: column;
  }

  .watchlist-summary {
    min-width: 0;
    grid-template-columns: repeat(4, minmax(120px, 1fr));
  }

  .watchlist-toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .watchlist-notes {
    text-align: left;
  }
}

@media (max-width: 768px) {
  .watchlist-view {
    padding: 16px;
  }

  .watchlist-summary {
    grid-template-columns: repeat(2, minmax(120px, 1fr));
  }

  .watchlist-inputs {
    flex-direction: column;
    align-items: stretch;
  }

  .watchlist-input {
    width: 100%;
  }
}
</style>
