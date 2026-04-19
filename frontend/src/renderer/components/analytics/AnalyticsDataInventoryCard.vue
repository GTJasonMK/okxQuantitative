<template>
  <section class="guardian-card">
    <!-- 区域 1：运行状态 -->
    <div class="gd-section">
      <div class="gd-section-head">
        <div>
          <h4 class="gd-title">运行状态</h4>
          <p class="gd-desc">守护器自动扫描关注池，推进窗口初始化、历史回补与增量维护。</p>
        </div>
        <div class="gd-actions">
          <button class="btn btn-sm" @click="loadGuardianStatus" :disabled="loadingGuardianStatus">
            {{ loadingGuardianStatus ? '读取中...' : '刷新' }}
          </button>
          <button class="btn btn-sm btn-primary" @click="triggerGuardianRun" :disabled="runningGuardianNow">
            {{ runningGuardianNow ? '已请求...' : '立即扫描' }}
          </button>
        </div>
      </div>

      <div class="gd-kpi-grid">
        <div class="gd-kpi">
          <span class="gd-kpi-label">状态</span>
          <span class="gd-kpi-value">
            <span class="status-dot" :class="guardianStatus.active ? 'dot-active' : (guardianStatus.enabled ? 'dot-idle' : 'dot-off')"></span>
            {{ guardianStateLabel }}
          </span>
        </div>
        <div class="gd-kpi">
          <span class="gd-kpi-label">监控币种</span>
          <span class="gd-kpi-value">{{ guardianStatus.watched_count || 0 }}</span>
        </div>
        <div class="gd-kpi">
          <span class="gd-kpi-label">本轮进度</span>
          <span class="gd-kpi-value">{{ guardianProgressText }}</span>
        </div>
        <div class="gd-kpi">
          <span class="gd-kpi-label">最近完成</span>
          <span class="gd-kpi-value">{{ formatRelativeTime(guardianStatus.last_run_finished_at) }}</span>
        </div>
        <div class="gd-kpi">
          <span class="gd-kpi-label">当前目标</span>
          <span class="gd-kpi-value">{{ guardianCurrentTargetLabel }}</span>
        </div>
        <div class="gd-kpi">
          <span class="gd-kpi-label">回补队列</span>
          <span class="gd-kpi-value">{{ guardianStatus.backfill_queue_size || 0 }} 个</span>
        </div>
      </div>

      <div class="gd-meta-row">
        <span>轮询 {{ guardianStatus.scan_interval_seconds || 0 }}s</span>
        <span>每轮全量 {{ guardianStatus.max_full_backfill_jobs_per_cycle || 0 }} 个</span>
        <span>全量周期 {{ guardianFullBackfillLabel }}</span>
        <span>滚动周期 {{ guardianRollingWindowLabel }}</span>
      </div>

      <div v-if="guardianStatusError" class="gd-error">{{ guardianStatusError }}</div>
      <div v-else-if="guardianLastError" class="gd-error">
        最近错误：{{ guardianLastError.scope }} · {{ guardianLastError.message }}
      </div>

      <div v-if="guardianStatus.backfill_queue_preview.length > 0" class="gd-chip-row">
        <span class="gd-chip-label">队列</span>
        <span
          v-for="item in guardianStatus.backfill_queue_preview.slice(0, 8)"
          :key="`queue-${item.inst_id}-${item.timeframe}`"
          class="gd-chip"
          :class="item.selected_this_cycle ? 'chip-active' : 'chip-pending'"
        >
          {{ item.inst_id }} · {{ item.timeframe }}
        </span>
      </div>

      <div v-if="guardianStatus.watched_instruments.length > 0" class="gd-chip-row">
        <span class="gd-chip-label">品种</span>
        <span
          v-for="instId in guardianStatus.watched_instruments"
          :key="`inst-${instId}`"
          class="gd-chip chip-neutral"
        >
          {{ instId }}
        </span>
      </div>
    </div>

    <!-- 区域 2：归档策略配置 -->
    <div class="gd-section">
      <div class="gd-section-head">
        <div>
          <h4 class="gd-title">归档策略</h4>
          <p class="gd-desc">控制各周期做滚动维护还是长期全量归档。</p>
        </div>
        <div class="gd-actions">
          <button class="btn btn-sm" @click="loadGuardianConfig" :disabled="loadingGuardianConfig">
            {{ loadingGuardianConfig ? '读取中...' : '重载' }}
          </button>
          <button class="btn btn-sm" @click="restoreGuardianDefaults" :disabled="savingGuardianConfig || loadingGuardianConfig">
            恢复默认
          </button>
          <button class="btn btn-sm btn-primary" @click="saveGuardianConfig" :disabled="savingGuardianConfig || !guardianConfigDirty">
            {{ savingGuardianConfig ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>

      <div class="gd-config-bar">
        <label class="gd-config-field">
          <input v-model="guardianConfig.enabled" type="checkbox" />
          <span>启用守护器</span>
        </label>
        <label class="gd-config-field">
          <span>扫描间隔</span>
          <input v-model.number="guardianConfig.scan_interval_seconds" class="gd-num-input" type="number" min="60" max="3600" />
          <span class="gd-unit">秒</span>
        </label>
        <label class="gd-config-field">
          <span>每轮全量</span>
          <input v-model.number="guardianConfig.max_full_backfill_jobs_per_cycle" class="gd-num-input" type="number" min="1" max="20" />
          <span class="gd-unit">个</span>
        </label>
        <span class="gd-config-dirty" :class="{ 'is-dirty': guardianConfigDirty }">
          {{ guardianConfigDirty ? '有未保存修改' : '已同步' }}
        </span>
      </div>

      <div v-if="guardianConfigError" class="gd-error">{{ guardianConfigError }}</div>

      <div class="gd-plan-table">
        <div class="gd-plan-head">
          <span>周期</span>
          <span>模式</span>
          <span>天数</span>
          <span>说明</span>
        </div>
        <div
          v-for="plan in guardianConfig.plans"
          :key="`plan-${plan.timeframe}`"
          class="gd-plan-row"
          :class="{ 'is-disabled': !plan.enabled }"
        >
          <label class="gd-plan-tf">
            <input v-model="plan.enabled" type="checkbox" />
            <strong>{{ plan.timeframe }}</strong>
          </label>
          <select v-model="plan.archive_mode" class="gd-plan-select">
            <option value="rolling">滚动</option>
            <option value="full">全量</option>
          </select>
          <input v-model.number="plan.bootstrap_days" class="gd-num-input" type="number" min="1" max="3650" />
          <span class="gd-plan-hint">{{ getGuardianPlanHint(plan) }}</span>
        </div>
      </div>
    </div>

    <!-- 区域 3：最近同步记录 -->
    <div v-if="guardianRecentResults.length > 0" class="gd-section">
      <h4 class="gd-title">最近同步</h4>
      <div class="gd-results-table">
        <div class="gd-results-head">
          <span>品种</span>
          <span>周期</span>
          <span>模式</span>
          <span>获取</span>
          <span>写入</span>
          <span>本地</span>
          <span>状态</span>
          <span>时间</span>
        </div>
        <div
          v-for="result in guardianRecentResults"
          :key="`${result.inst_id}-${result.timeframe}-${result.finished_at}`"
          class="gd-results-row"
        >
          <strong>{{ result.inst_id }}</strong>
          <span>{{ result.timeframe }}</span>
          <span>{{ formatSyncModeLabel(result.selected_mode) }}</span>
          <span>{{ formatLargeNumber(result.fetched_count) }}</span>
          <span>{{ formatLargeNumber(result.saved_count) }}</span>
          <span>{{ formatLargeNumber(result.candle_count) }}</span>
          <span class="mini-badge" :class="result.status === 'success' ? 'badge-green' : 'badge-red'">
            {{ result.status === 'success' ? '成功' : '失败' }}
          </span>
          <span>{{ formatRelativeTime(result.finished_at) }}</span>
        </div>
      </div>
    </div>

    <!-- 数据目录（mode=full 时展示，当前守护器 tab 不使用） -->
    <template v-if="showInventoryCatalog">
      <div class="gd-section">
        <div class="gd-section-head">
          <h4 class="gd-title">本地数据目录</h4>
          <button class="btn btn-sm" @click="loadDataInventory" :disabled="loadingDataInventory">
            {{ loadingDataInventory ? '刷新中...' : '刷新' }}
          </button>
        </div>

        <div class="gd-kpi-grid">
          <div class="gd-kpi">
            <span class="gd-kpi-label">已入库币种</span>
            <span class="gd-kpi-value">{{ dataInventorySummary.symbolCount }}</span>
          </div>
          <div class="gd-kpi">
            <span class="gd-kpi-label">周期记录</span>
            <span class="gd-kpi-value">{{ dataInventorySummary.timeframeRecordCount }}</span>
          </div>
          <div class="gd-kpi">
            <span class="gd-kpi-label">K 线总数</span>
            <span class="gd-kpi-value">{{ formatLargeNumber(dataInventorySummary.totalCandles) }}</span>
          </div>
          <div class="gd-kpi">
            <span class="gd-kpi-label">已补齐周期</span>
            <span class="gd-kpi-value">{{ dataInventorySummary.completeTimeframeCount }}</span>
          </div>
        </div>

        <div class="gd-filter-bar">
          <input v-model.trim="dataInventorySearch" class="gd-search-input" type="text" placeholder="搜索币种" />
          <select v-model="dataInventoryInstType" class="gd-plan-select">
            <option value="ALL">全部</option>
            <option value="SPOT">现货</option>
            <option value="SWAP">永续</option>
          </select>
          <select v-model="dataInventoryHistoryFilter" class="gd-plan-select">
            <option value="all">全部</option>
            <option value="complete">已补齐</option>
            <option value="incomplete">待补齐</option>
          </select>
        </div>

        <div v-if="dataInventoryError" class="gd-error">{{ dataInventoryError }}</div>
        <div v-if="loadingDataInventory" class="gd-empty">加载中...</div>
        <div v-else-if="filteredDataInventory.length === 0" class="gd-empty">无匹配记录</div>
        <div v-else class="gd-inv-list">
          <article v-for="item in filteredDataInventory" :key="item.key" class="gd-inv-item">
            <button class="gd-inv-head" @click="toggleInventoryExpansion(item.key)">
              <div class="gd-inv-main">
                <span class="gd-inv-symbol">{{ item.inst_id }}</span>
                <span class="mini-badge" :class="item.inst_type === 'SWAP' ? 'badge-purple' : 'badge-blue'">
                  {{ item.inst_type === 'SWAP' ? '永续' : '现货' }}
                </span>
                <span class="mini-badge" :class="item.allHistoryComplete ? 'badge-green' : 'badge-red'">
                  {{ item.allHistoryComplete ? '已补齐' : `待补 ${item.incompleteTimeframeCount}` }}
                </span>
                <span class="gd-inv-meta">{{ item.timeframes.length }} 周期 · {{ formatLargeNumber(item.totalCandles) }} 根 · {{ formatCoverageDays(item.coverageDays) }}</span>
              </div>
              <div class="gd-inv-chips">
                <span
                  v-for="tf in item.timeframes"
                  :key="`${item.key}-${tf.timeframe}`"
                  class="gd-tf-chip"
                  :class="tf.history_complete ? 'chip-complete' : 'chip-incomplete'"
                >{{ tf.timeframe }}</span>
                <span class="gd-expand-hint">{{ expandedInventoryKeys[item.key] ? '收起' : '展开' }}</span>
              </div>
            </button>
            <div v-if="expandedInventoryKeys[item.key]" class="gd-inv-detail">
              <div class="gd-results-head">
                <span>周期</span><span>K线</span><span>最早</span><span>最新</span><span>天数</span><span>状态</span><span>同步</span><span>模式</span>
              </div>
              <div v-for="tf in item.timeframes" :key="`${item.key}-${tf.timeframe}-d`" class="gd-results-row">
                <span>{{ tf.timeframe }}</span>
                <span>{{ formatLargeNumber(tf.candle_count) }}</span>
                <span>{{ formatDateTime(tf.oldest_time) }}</span>
                <span>{{ formatDateTime(tf.newest_time) }}</span>
                <span>{{ formatCoverageDays(tf.coverageDays) }}</span>
                <span class="mini-badge" :class="tf.history_complete ? 'badge-green' : 'badge-red'">{{ tf.history_complete ? '齐' : '缺' }}</span>
                <span>{{ formatDateTime(tf.last_sync_time) }}</span>
                <span>{{ formatSyncModeLabel(tf.last_sync_mode) }}</span>
              </div>
            </div>
          </article>
        </div>
      </div>
    </template>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue';
import { api } from '../../services/api';

const INVENTORY_CATALOG_MODES = new Set(['full']);
const GUARDIAN_ONLY_MODE = 'guardian-only';

const props = defineProps({
  mode: {
    type: String,
    default: 'full',
  },
});

const normalizedMode = computed(() => {
  const value = String(props.mode || '').trim().toLowerCase();
  return value || 'full';
});

const showInventoryCatalog = computed(() => INVENTORY_CATALOG_MODES.has(normalizedMode.value));

if (import.meta.env.DEV && !showInventoryCatalog.value && normalizedMode.value !== GUARDIAN_ONLY_MODE) {
  console.warn(`[AnalyticsDataInventoryCard] 未知 mode: ${props.mode}，已按 guardian-only 处理`);
}

const loadingDataInventory = ref(false);
const dataInventoryError = ref('');
const dataInventoryRows = ref([]);
const dataInventorySearch = ref('');
const dataInventoryInstType = ref('ALL');
const dataInventoryHistoryFilter = ref('all');
const expandedInventoryKeys = reactive({});
const loadingGuardianStatus = ref(false);
const guardianStatusError = ref('');
const runningGuardianNow = ref(false);
const loadingGuardianConfig = ref(false);
const guardianConfigError = ref('');
const savingGuardianConfig = ref(false);

const TIMEFRAME_ORDER = {
  '1m': 1, '3m': 2, '5m': 3, '15m': 4, '30m': 5,
  '1H': 6, '2H': 7, '4H': 8, '6H': 9, '12H': 10,
  '1D': 11, '1W': 12, '1M': 13,
};
const DAY_MS = 24 * 60 * 60 * 1000;
const DASHBOARD_REFRESH_INTERVAL = 30 * 1000;

const createGuardianConfig = (payload = {}) => {
  const rawPlans = Array.isArray(payload.plans) ? payload.plans : [];
  const normalizedPlans = rawPlans
    .map((plan) => ({
      timeframe: String(plan.timeframe || '').trim(),
      enabled: Boolean(plan.enabled),
      bootstrap_days: Number(plan.bootstrap_days ?? plan.bootstrapDays ?? 30) || 30,
      archive_mode: String(plan.archive_mode || plan.archiveMode || 'rolling').toLowerCase() === 'full' ? 'full' : 'rolling',
    }))
    .filter(plan => plan.timeframe)
    .sort((left, right) => (TIMEFRAME_ORDER[left.timeframe] || 999) - (TIMEFRAME_ORDER[right.timeframe] || 999));

  return {
    enabled: Boolean(payload.enabled ?? true),
    scan_interval_seconds: Number(payload.scan_interval_seconds ?? payload.scanIntervalSeconds ?? 300) || 300,
    max_full_backfill_jobs_per_cycle: Number(payload.max_full_backfill_jobs_per_cycle ?? payload.maxFullBackfillJobsPerCycle ?? 1) || 1,
    plans: normalizedPlans,
  };
};

const serializeGuardianConfig = (payload = {}) => JSON.stringify({
  ...createGuardianConfig(payload),
  plans: createGuardianConfig(payload).plans.map(plan => ({
    timeframe: plan.timeframe,
    enabled: Boolean(plan.enabled),
    bootstrap_days: Math.min(Math.max(Math.round(Number(plan.bootstrap_days) || 1), 1), 3650),
    archive_mode: plan.archive_mode === 'full' ? 'full' : 'rolling',
  })),
});

const createGuardianStatus = (payload = {}) => ({
  enabled: false, running: false, active: false, exchange_available: false,
  scan_interval_seconds: 300, max_full_backfill_jobs_per_cycle: 1,
  policy_summary: '', timeframes: [], full_backfill_timeframes: [], rolling_window_timeframes: [],
  watched_symbols: [], watched_instruments: [], watched_count: 0, inst_type: 'SPOT',
  current_inst_id: '', current_timeframe: '', current_mode: '', current_phase: 'idle',
  cycle_completed_units: 0, cycle_total_units: 0,
  backfill_queue_size: 0, backfill_queue_preview: [],
  last_run_started_at: null, last_run_finished_at: null,
  last_successful_run_at: null, last_triggered_at: null,
  last_run_summary: { success_count: 0, error_count: 0, total_units: 0 },
  last_sync_results: [], last_errors: [],
  ...payload,
});

const guardianStatus = ref(createGuardianStatus());
const guardianConfig = ref(createGuardianConfig());
const guardianConfigDefaults = ref(createGuardianConfig());
const guardianConfigLoadedSignature = ref(serializeGuardianConfig(createGuardianConfig()));
let dashboardRefreshTimer = null;

const normalizeBaseSymbol = (instId) => (instId || '').toUpperCase().replace(/-SWAP$/, '');
const formatLargeNumber = (value) => new Intl.NumberFormat('zh-CN').format(Number(value || 0));
const formatDateTime = (value) => {
  if (!value) return '-';
  return new Date(value).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
};
const formatCoverageDays = (value) => {
  const numeric = Number(value || 0);
  if (!Number.isFinite(numeric) || numeric <= 0) return '-';
  if (numeric >= 30) return `${numeric.toFixed(0)}天`;
  if (numeric >= 1) return `${numeric.toFixed(1)}天`;
  return `${numeric.toFixed(2)}天`;
};
const formatSyncModeLabel = (value) => {
  if (value === 'full') return '全量';
  if (value === 'incremental') return '增量';
  if (value === 'window') return '窗口';
  return value || '--';
};
const formatRelativeTime = (value) => {
  if (!value) return '未执行';
  const targetMs = new Date(value).getTime();
  if (!Number.isFinite(targetMs)) return '-';
  const absMs = Math.abs(Date.now() - targetMs);
  if (absMs < 60_000) return '刚刚';
  if (absMs < 3_600_000) return `${Math.round(absMs / 60_000)}分钟前`;
  if (absMs < DAY_MS) return `${Math.round(absMs / 3_600_000)}小时前`;
  return `${Math.round(absMs / DAY_MS)}天前`;
};
const calculateCoverageDays = (oldestTime, newestTime) => {
  if (!oldestTime || !newestTime) return 0;
  const oldestMs = new Date(oldestTime).getTime();
  const newestMs = new Date(newestTime).getTime();
  if (!Number.isFinite(oldestMs) || !Number.isFinite(newestMs) || newestMs < oldestMs) return 0;
  return (newestMs - oldestMs) / DAY_MS;
};

const groupedDataInventory = computed(() => {
  const grouped = new Map();
  (dataInventoryRows.value || []).forEach((row) => {
    const instId = String(row.inst_id || '').toUpperCase();
    const instType = String(row.inst_type || '').toUpperCase();
    const key = `${instType}:${instId}`;
    const candleCount = Number(row.candle_count || 0);
    const newestTime = row.newest_time || null;
    const oldestTime = row.oldest_time || null;
    const lastSyncTime = row.last_sync_time || null;
    if (!grouped.has(key)) {
      grouped.set(key, { key, inst_id: instId, symbol: normalizeBaseSymbol(instId), inst_type: instType, totalCandles: 0, newestTime, oldestTime, latestSyncTime: lastSyncTime, timeframes: [] });
    }
    const current = grouped.get(key);
    current.totalCandles += candleCount;
    if (oldestTime && (!current.oldestTime || new Date(oldestTime) < new Date(current.oldestTime))) current.oldestTime = oldestTime;
    if (newestTime && (!current.newestTime || new Date(newestTime) > new Date(current.newestTime))) current.newestTime = newestTime;
    if (lastSyncTime && (!current.latestSyncTime || new Date(lastSyncTime) > new Date(current.latestSyncTime))) current.latestSyncTime = lastSyncTime;
    current.timeframes.push({ timeframe: row.timeframe, candle_count: candleCount, oldest_time: oldestTime, newest_time: newestTime, last_sync_time: lastSyncTime, history_complete: Boolean(row.history_complete), last_sync_mode: row.last_sync_mode || 'window', coverageDays: calculateCoverageDays(oldestTime, newestTime) });
  });
  return [...grouped.values()]
    .map((item) => {
      item.timeframes.sort((a, b) => (TIMEFRAME_ORDER[a.timeframe] || 999) - (TIMEFRAME_ORDER[b.timeframe] || 999));
      item.coverageDays = calculateCoverageDays(item.oldestTime, item.newestTime);
      item.completeTimeframeCount = item.timeframes.filter(t => t.history_complete).length;
      item.incompleteTimeframeCount = item.timeframes.length - item.completeTimeframeCount;
      item.allHistoryComplete = item.timeframes.length > 0 && item.incompleteTimeframeCount === 0;
      return item;
    })
    .sort((a, b) => {
      const aSync = a.latestSyncTime ? new Date(a.latestSyncTime).getTime() : 0;
      const bSync = b.latestSyncTime ? new Date(b.latestSyncTime).getTime() : 0;
      return bSync !== aSync ? bSync - aSync : b.totalCandles - a.totalCandles;
    });
});

const dataInventorySummary = computed(() => {
  const items = groupedDataInventory.value;
  return {
    symbolCount: items.length,
    timeframeRecordCount: items.reduce((t, i) => t + i.timeframes.length, 0),
    totalCandles: items.reduce((t, i) => t + i.totalCandles, 0),
    completeTimeframeCount: items.reduce((t, i) => t + i.completeTimeframeCount, 0),
  };
});

const guardianStateLabel = computed(() => {
  if (guardianStatus.value.active) return '扫描中';
  if (guardianStatus.value.running) return '待机中';
  if (guardianStatus.value.enabled) return '未启动';
  return '已禁用';
});
const guardianProgressText = computed(() => {
  const c = Number(guardianStatus.value.cycle_completed_units || 0);
  const t = Number(guardianStatus.value.cycle_total_units || 0);
  return t <= 0 ? '0 / 0' : `${c} / ${t}`;
});
const guardianCurrentTargetLabel = computed(() => `${guardianStatus.value.current_inst_id || '--'} / ${guardianStatus.value.current_timeframe || '--'}`);
const guardianFullBackfillLabel = computed(() => (guardianStatus.value.full_backfill_timeframes || []).join(' · ') || '无');
const guardianRollingWindowLabel = computed(() => (guardianStatus.value.rolling_window_timeframes || []).join(' · ') || '无');
const guardianRecentResults = computed(() => (guardianStatus.value.last_sync_results || []).slice(0, 8));
const guardianLastError = computed(() => (guardianStatus.value.last_errors || [])[0] || null);
const guardianConfigDirty = computed(() => serializeGuardianConfig(guardianConfig.value) !== guardianConfigLoadedSignature.value);
const getGuardianPlanHint = (plan) => {
  if (!plan.enabled) return '已停用';
  return plan.archive_mode === 'full'
    ? `全量回补，先补最近 ${plan.bootstrap_days} 天再逐轮扩展`
    : `滚动维护最近 ${plan.bootstrap_days} 天`;
};

const filteredDataInventory = computed(() => {
  const keyword = dataInventorySearch.value.trim().toUpperCase();
  return groupedDataInventory.value.filter((item) => {
    if (dataInventoryInstType.value !== 'ALL' && item.inst_type !== dataInventoryInstType.value) return false;
    if (dataInventoryHistoryFilter.value === 'complete' && !item.allHistoryComplete) return false;
    if (dataInventoryHistoryFilter.value === 'incomplete' && item.allHistoryComplete) return false;
    if (!keyword) return true;
    return item.inst_id.includes(keyword) || item.symbol.includes(keyword);
  });
});
const toggleInventoryExpansion = (key) => { expandedInventoryKeys[key] = !expandedInventoryKeys[key]; };

const loadDataInventory = async ({ silent = false } = {}) => {
  if (!silent) loadingDataInventory.value = true;
  dataInventoryError.value = '';
  try {
    const res = await api.getSyncStatus();
    dataInventoryRows.value = Array.isArray(res.data) ? res.data : [];
    const firstItem = groupedDataInventory.value[0];
    if (firstItem && expandedInventoryKeys[firstItem.key] === undefined) expandedInventoryKeys[firstItem.key] = true;
  } catch (error) {
    dataInventoryError.value = error.response?.data?.detail || error.message || '加载数据目录失败';
  } finally {
    if (!silent) loadingDataInventory.value = false;
  }
};

const loadGuardianStatus = async ({ silent = false } = {}) => {
  if (!silent) loadingGuardianStatus.value = true;
  guardianStatusError.value = '';
  try {
    const res = await api.getDataGuardianStatus();
    guardianStatus.value = createGuardianStatus(res.data);
  } catch (error) {
    guardianStatusError.value = error.response?.data?.detail || error.message || '加载状态失败';
  } finally {
    if (!silent) loadingGuardianStatus.value = false;
  }
};

const loadGuardianConfig = async () => {
  loadingGuardianConfig.value = true;
  guardianConfigError.value = '';
  try {
    const res = await api.getDataGuardianConfig();
    guardianConfig.value = createGuardianConfig(res.data?.settings);
    guardianConfigDefaults.value = createGuardianConfig(res.data?.defaults);
    guardianConfigLoadedSignature.value = serializeGuardianConfig(guardianConfig.value);
  } catch (error) {
    guardianConfigError.value = error.response?.data?.detail || error.message || '加载配置失败';
  } finally {
    loadingGuardianConfig.value = false;
  }
};

const restoreGuardianDefaults = () => {
  guardianConfig.value = createGuardianConfig(guardianConfigDefaults.value);
  guardianConfigError.value = '';
};

const saveGuardianConfig = async () => {
  savingGuardianConfig.value = true;
  guardianConfigError.value = '';
  try {
    const payload = createGuardianConfig(guardianConfig.value);
    payload.plans = payload.plans.map(plan => ({ ...plan, bootstrap_days: Math.min(Math.max(Math.round(Number(plan.bootstrap_days) || 1), 1), 3650) }));
    const res = await api.updateDataGuardianConfig(payload);
    guardianConfig.value = createGuardianConfig(res.data?.settings);
    guardianConfigDefaults.value = createGuardianConfig(res.data?.defaults);
    guardianConfigLoadedSignature.value = serializeGuardianConfig(guardianConfig.value);
    guardianStatus.value = createGuardianStatus(res.data?.status);
  } catch (error) {
    guardianConfigError.value = error.response?.data?.detail || error.message || '保存配置失败';
  } finally {
    savingGuardianConfig.value = false;
  }
};

const triggerGuardianRun = async () => {
  runningGuardianNow.value = true;
  guardianStatusError.value = '';
  try {
    const res = await api.runDataGuardianNow();
    guardianStatus.value = createGuardianStatus(res.data);
  } catch (error) {
    guardianStatusError.value = error.response?.data?.detail || error.message || '触发扫描失败';
  } finally {
    runningGuardianNow.value = false;
  }
};

const refreshDashboard = async () => {
  const tasks = [loadGuardianStatus(), loadGuardianConfig()];
  if (showInventoryCatalog.value) tasks.unshift(loadDataInventory());
  await Promise.all(tasks);
};

onMounted(() => {
  void refreshDashboard();
  dashboardRefreshTimer = window.setInterval(() => {
    const tasks = [loadGuardianStatus({ silent: true })];
    if (showInventoryCatalog.value) tasks.unshift(loadDataInventory({ silent: true }));
    void Promise.all(tasks);
  }, DASHBOARD_REFRESH_INTERVAL);
});

onBeforeUnmount(() => {
  if (dashboardRefreshTimer) {
    window.clearInterval(dashboardRefreshTimer);
    dashboardRefreshTimer = null;
  }
});
</script>

<style scoped>
.guardian-card {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* 区域卡片 */
.gd-section {
  padding: 16px;
  border-radius: var(--radius-lg, 16px);
  background: rgba(15, 23, 42, 0.72);
  border: 1px solid rgba(71, 85, 105, 0.35);
}

.gd-section-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 14px;
}

.gd-title {
  margin: 0;
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
}

.gd-desc {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--text-secondary);
}

.gd-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

/* KPI 网格 */
.gd-kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
  gap: 10px;
  margin-bottom: 12px;
}

.gd-kpi {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 12px;
  border-radius: 10px;
  background: rgba(15, 23, 42, 0.5);
  border: 1px solid rgba(71, 85, 105, 0.22);
}

.gd-kpi-label {
  font-size: 11px;
  color: var(--text-muted);
}

.gd-kpi-value {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.dot-active {
  background: #22c55e;
  box-shadow: 0 0 6px rgba(34, 197, 94, 0.5);
}

.dot-idle {
  background: #f59e0b;
}

.dot-off {
  background: #64748b;
}

/* 元信息行 */
.gd-meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 14px;
  margin-bottom: 10px;
  font-size: 11px;
  color: var(--text-secondary);
}

/* 芯片行 */
.gd-chip-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-top: 10px;
}

.gd-chip-label {
  font-size: 11px;
  font-weight: 700;
  color: var(--text-muted);
  margin-right: 2px;
}

.gd-chip {
  padding: 3px 9px;
  border-radius: 999px;
  font-size: 11px;
  border: 1px solid rgba(71, 85, 105, 0.3);
}

.chip-active {
  color: #fde68a;
  background: rgba(245, 158, 11, 0.14);
  border-color: rgba(245, 158, 11, 0.28);
}

.chip-pending {
  color: var(--text-secondary);
  background: rgba(30, 41, 59, 0.6);
}

.chip-neutral {
  color: var(--text-primary);
  background: rgba(30, 41, 59, 0.6);
}

/* 配置条 */
.gd-config-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 16px;
  margin-bottom: 14px;
  padding: 10px 14px;
  border-radius: 10px;
  background: rgba(15, 23, 42, 0.4);
  border: 1px solid rgba(71, 85, 105, 0.2);
}

.gd-config-field {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-secondary);
  white-space: nowrap;
}

.gd-config-field input[type="checkbox"] {
  width: 15px;
  height: 15px;
}

.gd-num-input {
  width: 72px;
  padding: 5px 8px;
  border-radius: 6px;
  border: 1px solid var(--border-color);
  background: rgba(0, 0, 0, 0.3);
  color: var(--text-primary);
  font-size: 12px;
  text-align: center;
}

.gd-unit {
  font-size: 11px;
  color: var(--text-muted);
}

.gd-config-dirty {
  margin-left: auto;
  font-size: 11px;
  color: var(--text-muted);
}

.gd-config-dirty.is-dirty {
  color: #f59e0b;
}

/* 周期配置表格 */
.gd-plan-table {
  display: flex;
  flex-direction: column;
  gap: 0;
  border: 1px solid rgba(71, 85, 105, 0.22);
  border-radius: 10px;
  overflow: hidden;
}

.gd-plan-head {
  display: grid;
  grid-template-columns: 120px 90px 80px 1fr;
  gap: 10px;
  padding: 8px 14px;
  font-size: 11px;
  font-weight: 700;
  color: var(--text-muted);
  background: rgba(15, 23, 42, 0.5);
  border-bottom: 1px solid rgba(71, 85, 105, 0.22);
}

.gd-plan-row {
  display: grid;
  grid-template-columns: 120px 90px 80px 1fr;
  gap: 10px;
  padding: 8px 14px;
  align-items: center;
  border-bottom: 1px solid rgba(71, 85, 105, 0.12);
  font-size: 12px;
}

.gd-plan-row.is-disabled {
  opacity: 0.45;
}

.gd-plan-tf {
  display: flex;
  align-items: center;
  gap: 6px;
}

.gd-plan-tf input[type="checkbox"] {
  width: 14px;
  height: 14px;
}

.gd-plan-select {
  padding: 4px 8px;
  border-radius: 6px;
  border: 1px solid var(--border-color);
  background: rgba(0, 0, 0, 0.3);
  color: var(--text-primary);
  font-size: 11px;
}

.gd-plan-hint {
  font-size: 11px;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 同步记录表格 */
.gd-results-table {
  border: 1px solid rgba(71, 85, 105, 0.22);
  border-radius: 10px;
  overflow: auto;
}

.gd-results-head {
  display: grid;
  grid-template-columns: minmax(100px, 1.2fr) 50px 50px 60px 60px 60px 50px 80px;
  gap: 8px;
  padding: 8px 12px;
  font-size: 11px;
  font-weight: 700;
  color: var(--text-muted);
  background: rgba(15, 23, 42, 0.5);
  border-bottom: 1px solid rgba(71, 85, 105, 0.22);
}

.gd-results-row {
  display: grid;
  grid-template-columns: minmax(100px, 1.2fr) 50px 50px 60px 60px 60px 50px 80px;
  gap: 8px;
  padding: 7px 12px;
  font-size: 12px;
  border-bottom: 1px solid rgba(71, 85, 105, 0.1);
  align-items: center;
}

/* 错误消息 */
.gd-error {
  padding: 8px 12px;
  margin-bottom: 10px;
  border-radius: 8px;
  color: #fca5a5;
  background: rgba(127, 29, 29, 0.2);
  border: 1px solid rgba(239, 68, 68, 0.25);
  font-size: 12px;
}

.gd-empty {
  padding: 16px;
  text-align: center;
  color: var(--text-secondary);
  font-size: 12px;
}

/* 数据目录 */
.gd-filter-bar {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.gd-search-input {
  flex: 1;
  min-width: 120px;
  padding: 6px 10px;
  border-radius: 6px;
  border: 1px solid var(--border-color);
  background: rgba(0, 0, 0, 0.3);
  color: var(--text-primary);
  font-size: 12px;
}

.gd-inv-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.gd-inv-item {
  border: 1px solid rgba(71, 85, 105, 0.22);
  border-radius: 10px;
  overflow: hidden;
}

.gd-inv-head {
  width: 100%;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  background: transparent;
  border: none;
  color: inherit;
  cursor: pointer;
  text-align: left;
}

.gd-inv-head:hover {
  background: rgba(255, 255, 255, 0.02);
}

.gd-inv-main {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  min-width: 0;
}

.gd-inv-symbol {
  font-size: 13px;
  font-weight: 700;
}

.gd-inv-meta {
  font-size: 11px;
  color: var(--text-muted);
}

.gd-inv-chips {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.gd-tf-chip {
  padding: 2px 6px;
  border-radius: 999px;
  font-size: 10px;
  border: 1px solid rgba(71, 85, 105, 0.3);
}

.chip-complete {
  color: #86efac;
  border-color: rgba(34, 197, 94, 0.28);
  background: rgba(34, 197, 94, 0.1);
}

.chip-incomplete {
  color: #fbbf24;
  border-color: rgba(245, 158, 11, 0.28);
  background: rgba(245, 158, 11, 0.1);
}

.gd-expand-hint {
  font-size: 10px;
  color: var(--text-muted);
  margin-left: 4px;
}

.gd-inv-detail {
  border-top: 1px solid rgba(71, 85, 105, 0.18);
  overflow: auto;
}

/* Badge 通用 */
.mini-badge {
  display: inline-flex;
  align-items: center;
  padding: 1px 7px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 600;
}

.badge-blue { background: rgba(59, 130, 246, 0.18); color: #93c5fd; }
.badge-purple { background: rgba(139, 92, 246, 0.18); color: #c4b5fd; }
.badge-green { background: rgba(34, 197, 94, 0.18); color: #86efac; }
.badge-red { background: rgba(239, 68, 68, 0.18); color: #fca5a5; }

@media (max-width: 768px) {
  .gd-section-head,
  .gd-config-bar {
    flex-direction: column;
    align-items: stretch;
  }

  .gd-plan-head,
  .gd-plan-row {
    grid-template-columns: 1fr;
    gap: 4px;
  }

  .gd-results-head,
  .gd-results-row {
    grid-template-columns: 1fr;
    gap: 4px;
  }
}
</style>
