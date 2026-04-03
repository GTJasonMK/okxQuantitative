<template>
  <section class="card inventory-card">
    <div v-if="showInventoryCatalog" class="section-header">
      <div>
        <h3 class="card-title">本地数据目录</h3>
        <p class="section-desc">这里展示本地数据库当前实际持有的数据覆盖，用来判断哪些币种 / 周期已经入库、哪些还未补齐。</p>
      </div>
      <div class="toolbar">
        <button class="btn btn-secondary btn-sm" @click="loadDataInventory" :disabled="loadingDataInventory">
          {{ loadingDataInventory ? '刷新中...' : '刷新目录' }}
        </button>
      </div>
    </div>

    <div class="guardian-panel">
      <div class="guardian-panel-head">
        <div>
          <h4 class="guardian-title">后台数据守护器</h4>
          <p class="guardian-desc">自动读取行情监控页的监控池，先做窗口初始化，再推进历史回补与增量维护。</p>
        </div>
        <div class="guardian-actions">
          <button class="btn btn-secondary btn-sm" @click="loadGuardianStatus" :disabled="loadingGuardianStatus">
            {{ loadingGuardianStatus ? '读取中...' : '刷新状态' }}
          </button>
          <button class="btn btn-primary btn-sm" @click="triggerGuardianRun" :disabled="runningGuardianNow">
            {{ runningGuardianNow ? '已请求扫描...' : '立即扫描' }}
          </button>
        </div>
      </div>

      <div class="guardian-summary-grid">
        <div class="summary-card">
          <span class="summary-label">守护状态</span>
          <span class="summary-value">{{ guardianStateLabel }}</span>
        </div>
        <div class="summary-card">
          <span class="summary-label">监控币种</span>
          <span class="summary-value">{{ guardianStatus.watched_count || 0 }}</span>
        </div>
        <div class="summary-card">
          <span class="summary-label">扫描进度</span>
          <span class="summary-value">{{ guardianProgressText }}</span>
        </div>
        <div class="summary-card">
          <span class="summary-label">最近完成</span>
          <span class="summary-value">{{ formatRelativeTime(guardianStatus.last_run_finished_at) }}</span>
        </div>
      </div>

      <div class="guardian-meta-row">
        <span class="alert-badge" :class="guardianStatus.active ? 'badge-on' : 'badge-off'">
          {{ guardianStateLabel }}
        </span>
        <span>市场 {{ guardianStatus.inst_type || '--' }}</span>
        <span>轮询 {{ guardianStatus.scan_interval_seconds || 0 }} 秒</span>
        <span>每轮全量 {{ guardianStatus.max_full_backfill_jobs_per_cycle || 0 }} 个</span>
        <span>队列 {{ guardianStatus.backfill_queue_size || 0 }} 个</span>
        <span>当前 {{ guardianCurrentTargetLabel }}</span>
      </div>

      <div class="guardian-policy-row">
        <span>{{ guardianStatus.policy_summary }}</span>
        <span>全量回补周期：{{ guardianFullBackfillLabel }}</span>
        <span>滚动窗口周期：{{ guardianRollingWindowLabel }}</span>
      </div>

      <div v-if="guardianStatus.backfill_queue_preview.length > 0" class="guardian-queue-row">
        <span
          v-for="item in guardianStatus.backfill_queue_preview.slice(0, 8)"
          :key="`queue-${item.inst_id}-${item.timeframe}`"
          class="guardian-queue-chip"
          :class="item.selected_this_cycle ? 'queue-active' : 'queue-pending'"
        >
          {{ item.inst_id }} · {{ item.timeframe }} · {{ item.selected_this_cycle ? '本轮执行' : '排队中' }}
        </span>
      </div>

      <div v-if="guardianStatusError" class="error-message">{{ guardianStatusError }}</div>
      <div v-else-if="guardianLastError" class="inventory-note guardian-note-error">
        最近错误：{{ guardianLastError.scope }} · {{ guardianLastError.message }}
      </div>

      <div v-if="guardianStatus.watched_instruments.length > 0" class="guardian-chip-row">
        <span
          v-for="instId in guardianStatus.watched_instruments"
          :key="`guardian-${instId}`"
          class="guardian-chip"
        >
          {{ instId }}
        </span>
      </div>

      <div class="guardian-config-card">
        <div class="guardian-config-head">
          <div>
            <h4 class="guardian-config-title">归档策略配置</h4>
            <p class="guardian-config-desc">控制各周期做滚动维护还是长期全量归档。分钟级全量回补会进入队列，逐轮慢慢推进。</p>
          </div>
          <div class="guardian-actions">
            <button class="btn btn-secondary btn-sm" @click="loadGuardianConfig" :disabled="loadingGuardianConfig">
              {{ loadingGuardianConfig ? '读取中...' : '重载配置' }}
            </button>
            <button class="btn btn-secondary btn-sm" @click="restoreGuardianDefaults" :disabled="savingGuardianConfig || loadingGuardianConfig">
              恢复默认
            </button>
            <button class="btn btn-primary btn-sm" @click="saveGuardianConfig" :disabled="savingGuardianConfig || !guardianConfigDirty">
              {{ savingGuardianConfig ? '保存中...' : '保存配置' }}
            </button>
          </div>
        </div>

        <div class="guardian-config-grid">
          <label class="guardian-toggle">
            <span>启用后台守护器</span>
            <input v-model="guardianConfig.enabled" type="checkbox" />
          </label>
          <label class="guardian-field">
            <span>扫描间隔（秒）</span>
            <input v-model.number="guardianConfig.scan_interval_seconds" class="input" type="number" min="60" max="3600" />
          </label>
          <label class="guardian-field">
            <span>每轮全量回补任务数</span>
            <input v-model.number="guardianConfig.max_full_backfill_jobs_per_cycle" class="input" type="number" min="1" max="20" />
          </label>
        </div>

        <div class="guardian-config-note">
          <span>{{ guardianConfigDirty ? '有未保存修改' : '配置已同步' }}</span>
          <span>分钟级全量归档：{{ minuteFullArchiveLabel }}</span>
          <span>启用周期：{{ enabledGuardianPlanCount }}</span>
        </div>

        <div v-if="guardianConfigError" class="error-message">{{ guardianConfigError }}</div>

        <div class="guardian-plan-list">
          <article
            v-for="plan in guardianConfig.plans"
            :key="`plan-${plan.timeframe}`"
            class="guardian-plan-row"
          >
            <label class="guardian-plan-main">
              <input v-model="plan.enabled" type="checkbox" />
              <span class="guardian-plan-timeframe">{{ plan.timeframe }}</span>
              <span class="mini-badge" :class="plan.archive_mode === 'full' ? 'badge-purple' : 'badge-blue'">
                {{ plan.archive_mode === 'full' ? '长期归档' : '滚动维护' }}
              </span>
            </label>
            <div class="guardian-plan-controls">
              <select v-model="plan.archive_mode" class="select">
                <option value="rolling">滚动维护</option>
                <option value="full">长期全量归档</option>
              </select>
              <input
                v-model.number="plan.bootstrap_days"
                class="input guardian-days-input"
                type="number"
                min="1"
                max="3650"
              />
            </div>
            <div class="guardian-plan-hint">
              {{ getGuardianPlanHint(plan) }}
            </div>
          </article>
        </div>
      </div>

      <div v-if="guardianRecentResults.length > 0" class="guardian-results">
        <article
          v-for="result in guardianRecentResults"
          :key="`${result.inst_id}-${result.timeframe}-${result.finished_at}-${result.selected_mode}`"
          class="guardian-result-card"
        >
          <div class="guardian-result-head">
            <strong>{{ result.inst_id }}</strong>
            <span class="mini-badge" :class="result.status === 'success' ? 'badge-green' : 'badge-red'">
              {{ result.status === 'success' ? '成功' : '失败' }}
            </span>
          </div>
          <div class="guardian-result-meta">
            <span>{{ result.timeframe }}</span>
            <span>{{ formatSyncModeLabel(result.selected_mode) }}</span>
            <span>{{ formatRelativeTime(result.finished_at) }}</span>
          </div>
          <div class="guardian-result-meta">
            <span>获取 {{ formatLargeNumber(result.fetched_count) }}</span>
            <span>写入 {{ formatLargeNumber(result.saved_count) }}</span>
            <span>本地 {{ formatLargeNumber(result.candle_count) }}</span>
          </div>
        </article>
      </div>
    </div>

    <template v-if="showInventoryCatalog">
      <div class="inventory-summary-grid">
      <div class="summary-card">
        <span class="summary-label">已入库币种</span>
        <span class="summary-value">{{ dataInventorySummary.symbolCount }}</span>
      </div>
      <div class="summary-card">
        <span class="summary-label">周期记录</span>
        <span class="summary-value">{{ dataInventorySummary.timeframeRecordCount }}</span>
      </div>
      <div class="summary-card">
        <span class="summary-label">本地 K 线总数</span>
        <span class="summary-value">{{ formatLargeNumber(dataInventorySummary.totalCandles) }}</span>
      </div>
      <div class="summary-card">
        <span class="summary-label">已补齐周期</span>
        <span class="summary-value">{{ dataInventorySummary.completeTimeframeCount }}</span>
      </div>
      </div>

      <div class="inventory-toolbar">
      <input
        v-model.trim="dataInventorySearch"
        class="input"
        type="text"
        placeholder="搜索币种，例如 BTC / BTC-USDT / DOGE-USDT-SWAP"
      />
      <select v-model="dataInventoryInstType" class="select">
        <option value="ALL">全部市场</option>
        <option value="SPOT">仅现货</option>
        <option value="SWAP">仅永续</option>
      </select>
      <select v-model="dataInventoryHistoryFilter" class="select">
        <option value="all">全部状态</option>
        <option value="complete">仅历史已补齐</option>
        <option value="incomplete">仅待补齐</option>
      </select>
      </div>

      <div class="inventory-note">
      当前系统仍是“本地优先 + 覆盖不足时按需补拉”的模式。
      这个目录展示的是当前本地真正持有的数据，不代表交易所全量历史已经全部入库。
      </div>

      <div v-if="dataInventoryError" class="error-message">{{ dataInventoryError }}</div>
      <div v-if="loadingDataInventory" class="empty-state">加载数据目录中...</div>
      <div v-else-if="filteredDataInventory.length === 0" class="empty-state">
        当前没有符合筛选条件的数据目录记录
      </div>
      <div v-else class="inventory-list">
        <article
          v-for="item in filteredDataInventory"
          :key="item.key"
          class="inventory-item"
        >
          <button class="inventory-item-head" @click="toggleInventoryExpansion(item.key)">
            <div class="inventory-item-main">
              <div class="inventory-symbol-row">
                <span class="inventory-symbol">{{ item.inst_id }}</span>
                <span class="alert-badge" :class="item.inst_type === 'SWAP' ? 'badge-purple' : 'badge-blue'">
                  {{ item.inst_type === 'SWAP' ? '永续合约' : '现货' }}
                </span>
                <span class="alert-badge" :class="item.allHistoryComplete ? 'badge-on' : 'badge-off'">
                  {{ item.allHistoryComplete ? '历史已补齐' : `待补 ${item.incompleteTimeframeCount} 个周期` }}
                </span>
              </div>
              <div class="inventory-meta-row">
                <span>{{ item.timeframes.length }} 个周期</span>
                <span>{{ formatLargeNumber(item.totalCandles) }} 根</span>
                <span>覆盖 {{ formatCoverageDays(item.coverageDays) }}</span>
                <span>最新 {{ formatDateTime(item.newestTime) }}</span>
              </div>
            </div>

            <div class="inventory-item-side">
              <div class="inventory-timeframe-chips">
                <span
                  v-for="timeframeItem in item.timeframes"
                  :key="`${item.key}-${timeframeItem.timeframe}`"
                  class="inventory-timeframe-chip"
                  :class="timeframeItem.history_complete ? 'chip-complete' : 'chip-incomplete'"
                >
                  {{ timeframeItem.timeframe }}
                </span>
              </div>
              <span class="inventory-expand-indicator">
                {{ expandedInventoryKeys[item.key] ? '收起' : '展开' }}
              </span>
            </div>
          </button>

          <div v-if="expandedInventoryKeys[item.key]" class="table-wrapper inventory-table-wrapper">
            <table class="data-table inventory-table">
              <thead>
                <tr>
                  <th>周期</th>
                  <th>K线根数</th>
                  <th>最早时间</th>
                  <th>最新时间</th>
                  <th>覆盖天数</th>
                  <th>历史状态</th>
                  <th>最近同步</th>
                  <th>同步模式</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="timeframeItem in item.timeframes"
                  :key="`${item.key}-${timeframeItem.timeframe}-row`"
                >
                  <td>{{ timeframeItem.timeframe }}</td>
                  <td>{{ formatLargeNumber(timeframeItem.candle_count) }}</td>
                  <td>{{ formatDateTime(timeframeItem.oldest_time) }}</td>
                  <td>{{ formatDateTime(timeframeItem.newest_time) }}</td>
                  <td>{{ formatCoverageDays(timeframeItem.coverageDays) }}</td>
                  <td>
                    <span
                      class="mini-badge"
                      :class="timeframeItem.history_complete ? 'badge-green' : 'badge-red'"
                    >
                      {{ timeframeItem.history_complete ? '已补齐' : '待补齐' }}
                    </span>
                  </td>
                  <td>{{ formatDateTime(timeframeItem.last_sync_time) }}</td>
                  <td>{{ formatSyncModeLabel(timeframeItem.last_sync_mode) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </article>
      </div>
    </template>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue';
import { api } from '../../services/api';

const props = defineProps({
  mode: {
    type: String,
    default: 'full',
  },
});

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
  '1m': 1,
  '3m': 2,
  '5m': 3,
  '15m': 4,
  '30m': 5,
  '1H': 6,
  '2H': 7,
  '4H': 8,
  '6H': 9,
  '12H': 10,
  '1D': 11,
  '1W': 12,
  '1M': 13,
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
    .sort((left, right) => {
      const leftRank = TIMEFRAME_ORDER[left.timeframe] || 999;
      const rightRank = TIMEFRAME_ORDER[right.timeframe] || 999;
      return leftRank - rightRank;
    });

  return {
    enabled: Boolean(payload.enabled ?? true),
    scan_interval_seconds: Number(payload.scan_interval_seconds ?? payload.scanIntervalSeconds ?? 300) || 300,
    max_full_backfill_jobs_per_cycle: Number(
      payload.max_full_backfill_jobs_per_cycle ?? payload.maxFullBackfillJobsPerCycle ?? 1
    ) || 1,
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
  enabled: false,
  running: false,
  active: false,
  exchange_available: false,
  scan_interval_seconds: 300,
  max_full_backfill_jobs_per_cycle: 1,
  policy_summary: '',
  timeframes: [],
  full_backfill_timeframes: [],
  rolling_window_timeframes: [],
  watched_symbols: [],
  watched_instruments: [],
  watched_count: 0,
  inst_type: 'SPOT',
  current_inst_id: '',
  current_timeframe: '',
  current_mode: '',
  current_phase: 'idle',
  cycle_completed_units: 0,
  cycle_total_units: 0,
  backfill_queue_size: 0,
  backfill_queue_preview: [],
  last_run_started_at: null,
  last_run_finished_at: null,
  last_successful_run_at: null,
  last_triggered_at: null,
  last_run_summary: {
    success_count: 0,
    error_count: 0,
    total_units: 0,
  },
  last_sync_results: [],
  last_errors: [],
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
  return new Date(value).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
};
const formatCoverageDays = (value) => {
  const numeric = Number(value || 0);
  if (!Number.isFinite(numeric) || numeric <= 0) return '-';
  if (numeric >= 30) return `${numeric.toFixed(0)}天`;
  if (numeric >= 1) return `${numeric.toFixed(1)}天`;
  return `${numeric.toFixed(2)}天`;
};
const formatSyncModeLabel = (value) => {
  switch (value) {
    case 'full':
      return '全量回补';
    case 'incremental':
      return '增量更新';
    case 'window':
      return '最近窗口';
    default:
      return value || '--';
  }
};
const formatRelativeTime = (value) => {
  if (!value) return '未执行';
  const targetMs = new Date(value).getTime();
  if (!Number.isFinite(targetMs)) return '-';
  const diffMs = Date.now() - targetMs;
  const absMs = Math.abs(diffMs);
  if (absMs < 60 * 1000) return '刚刚';
  if (absMs < 60 * 60 * 1000) return `${Math.round(absMs / (60 * 1000))} 分钟前`;
  if (absMs < DAY_MS) return `${Math.round(absMs / (60 * 60 * 1000))} 小时前`;
  return `${Math.round(absMs / DAY_MS)} 天前`;
};
const calculateCoverageDays = (oldestTime, newestTime) => {
  if (!oldestTime || !newestTime) return 0;
  const oldestMs = new Date(oldestTime).getTime();
  const newestMs = new Date(newestTime).getTime();
  if (!Number.isFinite(oldestMs) || !Number.isFinite(newestMs) || newestMs < oldestMs) {
    return 0;
  }
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
    const coverageDays = calculateCoverageDays(oldestTime, newestTime);

    if (!grouped.has(key)) {
      grouped.set(key, {
        key,
        inst_id: instId,
        symbol: normalizeBaseSymbol(instId),
        inst_type: instType,
        totalCandles: 0,
        newestTime: newestTime,
        oldestTime: oldestTime,
        latestSyncTime: lastSyncTime,
        timeframes: [],
      });
    }

    const current = grouped.get(key);
    current.totalCandles += candleCount;
    if (oldestTime && (!current.oldestTime || new Date(oldestTime) < new Date(current.oldestTime))) {
      current.oldestTime = oldestTime;
    }
    if (newestTime && (!current.newestTime || new Date(newestTime) > new Date(current.newestTime))) {
      current.newestTime = newestTime;
    }
    if (lastSyncTime && (!current.latestSyncTime || new Date(lastSyncTime) > new Date(current.latestSyncTime))) {
      current.latestSyncTime = lastSyncTime;
    }
    current.timeframes.push({
      timeframe: row.timeframe,
      candle_count: candleCount,
      oldest_time: oldestTime,
      newest_time: newestTime,
      last_sync_time: lastSyncTime,
      history_complete: Boolean(row.history_complete),
      last_sync_mode: row.last_sync_mode || 'window',
      coverageDays,
    });
  });

  return [...grouped.values()]
    .map((item) => {
      item.timeframes.sort((left, right) => {
        const leftRank = TIMEFRAME_ORDER[left.timeframe] || 999;
        const rightRank = TIMEFRAME_ORDER[right.timeframe] || 999;
        return leftRank - rightRank;
      });
      item.coverageDays = calculateCoverageDays(item.oldestTime, item.newestTime);
      item.completeTimeframeCount = item.timeframes.filter(timeframeItem => timeframeItem.history_complete).length;
      item.incompleteTimeframeCount = item.timeframes.length - item.completeTimeframeCount;
      item.allHistoryComplete = item.timeframes.length > 0 && item.incompleteTimeframeCount === 0;
      return item;
    })
    .sort((left, right) => {
      const leftSync = left.latestSyncTime ? new Date(left.latestSyncTime).getTime() : 0;
      const rightSync = right.latestSyncTime ? new Date(right.latestSyncTime).getTime() : 0;
      if (rightSync !== leftSync) return rightSync - leftSync;
      return right.totalCandles - left.totalCandles;
    });
});

const dataInventorySummary = computed(() => {
  const items = groupedDataInventory.value;
  return {
    symbolCount: items.length,
    timeframeRecordCount: items.reduce((total, item) => total + item.timeframes.length, 0),
    totalCandles: items.reduce((total, item) => total + item.totalCandles, 0),
    completeTimeframeCount: items.reduce((total, item) => total + item.completeTimeframeCount, 0),
  };
});

const guardianStateLabel = computed(() => {
  if (guardianStatus.value.active) return '扫描中';
  if (guardianStatus.value.running) return '待机中';
  if (guardianStatus.value.enabled) return '未启动';
  return '已禁用';
});

const guardianProgressText = computed(() => {
  const completed = Number(guardianStatus.value.cycle_completed_units || 0);
  const total = Number(guardianStatus.value.cycle_total_units || 0);
  if (total <= 0) return '0 / 0';
  return `${completed} / ${total}`;
});

const guardianCurrentTargetLabel = computed(() => {
  const instId = guardianStatus.value.current_inst_id || '--';
  const timeframe = guardianStatus.value.current_timeframe || '--';
  return `${instId} / ${timeframe}`;
});

const guardianFullBackfillLabel = computed(() => {
  const items = guardianStatus.value.full_backfill_timeframes || [];
  return items.length > 0 ? items.join(' · ') : '无';
});

const guardianRollingWindowLabel = computed(() => {
  const items = guardianStatus.value.rolling_window_timeframes || [];
  return items.length > 0 ? items.join(' · ') : '无';
});

const guardianRecentResults = computed(() => {
  return (guardianStatus.value.last_sync_results || []).slice(0, 6);
});

const showInventoryCatalog = computed(() => props.mode !== 'guardian-only');

const guardianLastError = computed(() => {
  return (guardianStatus.value.last_errors || [])[0] || null;
});

const guardianConfigDirty = computed(() => {
  return serializeGuardianConfig(guardianConfig.value) !== guardianConfigLoadedSignature.value;
});

const enabledGuardianPlanCount = computed(() => {
  return guardianConfig.value.plans.filter(plan => plan.enabled).length;
});

const minuteFullArchiveLabel = computed(() => {
  const items = guardianConfig.value.plans
    .filter(plan => plan.enabled && plan.archive_mode === 'full' && ['1m', '5m'].includes(plan.timeframe))
    .map(plan => plan.timeframe);
  return items.length > 0 ? items.join(' · ') : '无';
});

const getGuardianPlanHint = (plan) => {
  if (!plan.enabled) {
    return '该周期已停用，不会参与后台守护。';
  }
  if (plan.archive_mode === 'full') {
    return `${plan.timeframe} 会进入全量回补队列，先补最近 ${plan.bootstrap_days} 天，再逐轮向过去扩展。`;
  }
  return `${plan.timeframe} 只维护最近 ${plan.bootstrap_days} 天窗口，并持续做增量更新。`;
};

const filteredDataInventory = computed(() => {
  const keyword = dataInventorySearch.value.trim().toUpperCase();

  return groupedDataInventory.value.filter((item) => {
    if (dataInventoryInstType.value !== 'ALL' && item.inst_type !== dataInventoryInstType.value) {
      return false;
    }
    if (dataInventoryHistoryFilter.value === 'complete' && !item.allHistoryComplete) {
      return false;
    }
    if (dataInventoryHistoryFilter.value === 'incomplete' && item.allHistoryComplete) {
      return false;
    }
    if (!keyword) {
      return true;
    }
    return item.inst_id.includes(keyword) || item.symbol.includes(keyword);
  });
});

const toggleInventoryExpansion = (key) => {
  expandedInventoryKeys[key] = !expandedInventoryKeys[key];
};

const loadDataInventory = async ({ silent = false } = {}) => {
  if (!silent) {
    loadingDataInventory.value = true;
  }
  dataInventoryError.value = '';
  try {
    const res = await api.getSyncStatus();
    dataInventoryRows.value = Array.isArray(res.data) ? res.data : [];
    const firstItem = groupedDataInventory.value[0];
    if (firstItem && expandedInventoryKeys[firstItem.key] === undefined) {
      expandedInventoryKeys[firstItem.key] = true;
    }
  } catch (error) {
    console.error('加载数据目录失败:', error);
    dataInventoryError.value = error.response?.data?.detail || error.message || '加载数据目录失败';
  } finally {
    if (!silent) {
      loadingDataInventory.value = false;
    }
  }
};

const loadGuardianStatus = async ({ silent = false } = {}) => {
  if (!silent) {
    loadingGuardianStatus.value = true;
  }
  guardianStatusError.value = '';
  try {
    const res = await api.getDataGuardianStatus();
    guardianStatus.value = createGuardianStatus(res.data);
  } catch (error) {
    console.error('加载数据守护器状态失败:', error);
    guardianStatusError.value = error.response?.data?.detail || error.message || '加载数据守护器状态失败';
  } finally {
    if (!silent) {
      loadingGuardianStatus.value = false;
    }
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
    console.error('加载数据守护器配置失败:', error);
    guardianConfigError.value = error.response?.data?.detail || error.message || '加载数据守护器配置失败';
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
    payload.plans = payload.plans.map(plan => ({
      ...plan,
      bootstrap_days: Math.min(Math.max(Math.round(Number(plan.bootstrap_days) || 1), 1), 3650),
    }));
    const res = await api.updateDataGuardianConfig(payload);
    guardianConfig.value = createGuardianConfig(res.data?.settings);
    guardianConfigDefaults.value = createGuardianConfig(res.data?.defaults);
    guardianConfigLoadedSignature.value = serializeGuardianConfig(guardianConfig.value);
    guardianStatus.value = createGuardianStatus(res.data?.status);
  } catch (error) {
    console.error('保存数据守护器配置失败:', error);
    guardianConfigError.value = error.response?.data?.detail || error.message || '保存数据守护器配置失败';
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
    console.error('触发数据守护器扫描失败:', error);
    guardianStatusError.value = error.response?.data?.detail || error.message || '触发数据守护器扫描失败';
  } finally {
    runningGuardianNow.value = false;
  }
};

const refreshDashboard = async () => {
  const tasks = [loadGuardianStatus(), loadGuardianConfig()];
  if (showInventoryCatalog.value) {
    tasks.unshift(loadDataInventory());
  }
  await Promise.all(tasks);
};

onMounted(() => {
  void refreshDashboard();
  dashboardRefreshTimer = window.setInterval(() => {
    const tasks = [loadGuardianStatus({ silent: true })];
    if (showInventoryCatalog.value) {
      tasks.unshift(loadDataInventory({ silent: true }));
    }
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
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 16px;
}

.section-desc {
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-secondary);
}

.toolbar {
  display: flex;
  gap: 8px;
}

.inventory-summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.summary-card {
  padding: 14px;
  border-radius: 12px;
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.65), rgba(15, 23, 42, 0.32));
  border: 1px solid rgba(71, 85, 105, 0.45);
}

.guardian-panel {
  margin-bottom: 16px;
  padding: 16px;
  border-radius: 16px;
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.88), rgba(15, 23, 42, 0.62));
  border: 1px solid rgba(71, 85, 105, 0.45);
}

.guardian-panel-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 14px;
}

.guardian-title {
  margin: 0;
  font-size: 14px;
  font-weight: 700;
}

.guardian-desc {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--text-secondary);
}

.guardian-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.guardian-summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 12px;
}

.guardian-meta-row,
.guardian-policy-row,
.guardian-chip-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
}

.guardian-meta-row,
.guardian-policy-row {
  margin-bottom: 10px;
  font-size: 12px;
  color: var(--text-secondary);
}

.guardian-chip-row {
  margin-bottom: 12px;
}

.guardian-chip {
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(30, 41, 59, 0.78);
  border: 1px solid rgba(71, 85, 105, 0.38);
  font-size: 12px;
  color: var(--text-primary);
}

.guardian-results {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 10px;
}

.guardian-result-card {
  padding: 12px;
  border-radius: 12px;
  background: rgba(15, 23, 42, 0.52);
  border: 1px solid rgba(71, 85, 105, 0.35);
}

.guardian-result-head,
.guardian-result-meta {
  display: flex;
  justify-content: space-between;
  gap: 8px;
}

.guardian-result-head {
  margin-bottom: 8px;
  align-items: center;
}

.guardian-result-meta {
  font-size: 12px;
  color: var(--text-secondary);
}

.guardian-note-error {
  margin-bottom: 12px;
  color: #fecaca;
  background: rgba(127, 29, 29, 0.18);
  border-color: rgba(248, 113, 113, 0.28);
}

.guardian-queue-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.guardian-queue-chip {
  display: inline-flex;
  align-items: center;
  min-height: 26px;
  padding: 0 10px;
  border-radius: 999px;
  font-size: 11px;
  border: 1px solid rgba(71, 85, 105, 0.35);
}

.guardian-queue-chip.queue-active {
  color: #fde68a;
  background: rgba(245, 158, 11, 0.14);
  border-color: rgba(245, 158, 11, 0.28);
}

.guardian-queue-chip.queue-pending {
  color: #cbd5f5;
  background: rgba(30, 41, 59, 0.62);
}

.guardian-config-card {
  margin-bottom: 14px;
  padding: 14px;
  border-radius: 14px;
  background: rgba(15, 23, 42, 0.48);
  border: 1px solid rgba(71, 85, 105, 0.32);
}

.guardian-config-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 12px;
}

.guardian-config-title {
  margin: 0;
  font-size: 13px;
  font-weight: 700;
}

.guardian-config-desc {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--text-secondary);
}

.guardian-config-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 12px;
}

.guardian-toggle,
.guardian-field {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
  font-size: 12px;
  color: var(--text-secondary);
}

.guardian-toggle {
  justify-content: space-between;
  padding: 12px;
  border-radius: 12px;
  background: rgba(15, 23, 42, 0.36);
  border: 1px solid rgba(71, 85, 105, 0.28);
}

.guardian-toggle input {
  width: 16px;
  height: 16px;
}

.guardian-config-note {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 12px;
  margin-bottom: 12px;
  font-size: 12px;
  color: var(--text-secondary);
}

.guardian-plan-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.guardian-plan-row {
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) minmax(220px, 0.9fr);
  gap: 12px;
  padding: 12px;
  border-radius: 12px;
  background: rgba(2, 6, 23, 0.34);
  border: 1px solid rgba(71, 85, 105, 0.22);
}

.guardian-plan-main {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 12px;
  color: var(--text-primary);
}

.guardian-plan-main input {
  width: 15px;
  height: 15px;
}

.guardian-plan-timeframe {
  font-size: 13px;
  font-weight: 700;
}

.guardian-plan-controls {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 120px;
  gap: 10px;
  align-items: center;
}

.guardian-days-input {
  width: 100%;
}

.guardian-plan-hint {
  grid-column: 1 / -1;
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.6;
}

.summary-label {
  display: block;
  margin-bottom: 8px;
  font-size: 12px;
  color: var(--text-secondary);
}

.summary-value {
  font-size: 18px;
  font-weight: 700;
}

.inventory-toolbar {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) 160px 180px;
  gap: 12px;
  margin-bottom: 12px;
}

.inventory-note {
  margin-bottom: 14px;
  padding: 12px 14px;
  border-radius: 10px;
  background: rgba(15, 23, 42, 0.35);
  border: 1px solid rgba(71, 85, 105, 0.28);
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.7;
}

.error-message {
  padding: 10px 12px;
  margin-bottom: 12px;
  border-radius: 8px;
  color: #fca5a5;
  background: rgba(127, 29, 29, 0.22);
  border: 1px solid rgba(239, 68, 68, 0.3);
  font-size: 12px;
}

.empty-state {
  padding: 18px;
  border: 1px dashed var(--border-color);
  border-radius: 10px;
  font-size: 12px;
  color: var(--text-secondary);
  text-align: center;
}

.inventory-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.inventory-item {
  border: 1px solid var(--border-color);
  border-radius: 12px;
  background: rgba(15, 23, 42, 0.32);
  overflow: hidden;
}

.inventory-item-head {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 16px;
  background: transparent;
  border: none;
  color: inherit;
  cursor: pointer;
  text-align: left;
}

.inventory-item-head:hover {
  background: rgba(255, 255, 255, 0.03);
}

.inventory-item-main {
  flex: 1;
  min-width: 0;
}

.inventory-symbol-row,
.inventory-meta-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.inventory-symbol-row {
  margin-bottom: 8px;
}

.inventory-symbol {
  font-size: 15px;
  font-weight: 700;
}

.inventory-meta-row {
  color: var(--text-secondary);
  font-size: 12px;
}

.inventory-item-side {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 10px;
}

.inventory-timeframe-chips {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.inventory-timeframe-chip {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 8px;
  border-radius: 999px;
  border: 1px solid rgba(71, 85, 105, 0.4);
  background: rgba(15, 23, 42, 0.45);
  font-size: 11px;
  color: var(--text-secondary);
}

.inventory-timeframe-chip.chip-complete {
  color: #86efac;
  border-color: rgba(34, 197, 94, 0.28);
  background: rgba(34, 197, 94, 0.12);
}

.inventory-timeframe-chip.chip-incomplete {
  color: #fbbf24;
  border-color: rgba(245, 158, 11, 0.28);
  background: rgba(245, 158, 11, 0.12);
}

.inventory-expand-indicator {
  font-size: 11px;
  color: var(--text-muted);
}

.table-wrapper {
  overflow: auto;
  border: 1px solid var(--border-color);
  border-radius: 10px;
}

.inventory-table-wrapper {
  border-top: 1px solid rgba(71, 85, 105, 0.25);
  border-left: none;
  border-right: none;
  border-bottom: none;
  border-radius: 0;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
}

.data-table th,
.data-table td {
  padding: 12px;
  font-size: 12px;
  text-align: left;
  border-bottom: 1px solid rgba(71, 85, 105, 0.25);
  white-space: nowrap;
}

.data-table th {
  color: var(--text-secondary);
  background: rgba(15, 23, 42, 0.55);
}

.alert-badge,
.mini-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
}

.mini-badge {
  font-size: 10px;
  padding: 1px 7px;
}

.badge-on {
  color: #16a34a;
  background: rgba(22, 163, 74, 0.14);
}

.badge-off {
  color: #94a3b8;
  background: rgba(148, 163, 184, 0.12);
}

.badge-blue  { background: rgba(59,130,246,0.18); color: #93c5fd; }
.badge-purple { background: rgba(139,92,246,0.18); color: #c4b5fd; }
.badge-green { background: rgba(34,197,94,0.18); color: #86efac; }
.badge-red { background: rgba(239,68,68,0.18); color: #fca5a5; }

@media (max-width: 768px) {
  .guardian-summary-grid,
  .guardian-config-grid,
  .inventory-summary-grid,
  .inventory-toolbar {
    grid-template-columns: 1fr;
  }

  .section-header,
  .guardian-panel-head,
  .guardian-config-head {
    flex-direction: column;
  }

  .inventory-item-head,
  .inventory-item-side {
    align-items: flex-start;
  }

  .inventory-item-head {
    flex-direction: column;
  }

  .guardian-actions {
    justify-content: flex-start;
  }

  .guardian-plan-row,
  .guardian-plan-controls {
    grid-template-columns: 1fr;
  }

  .inventory-timeframe-chips {
    justify-content: flex-start;
  }
}
</style>
