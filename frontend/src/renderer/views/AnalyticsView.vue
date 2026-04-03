<template>
  <div class="analytics-view">
    <!-- 顶部命令栏 -->
    <header class="av-command-bar">
      <div class="av-left">
        <h1 class="av-title">分析中心</h1>
        <nav class="av-tabs">
          <button class="av-tab" :class="{ active: activeAnalyticsTab === 'alerts' }" @click="activeAnalyticsTab = 'alerts'">
            价格提醒
            <span v-if="alerts.length > 0" class="av-tab-count">{{ alerts.length }}</span>
          </button>
          <button class="av-tab" :class="{ active: activeAnalyticsTab === 'performance' }" @click="activeAnalyticsTab = 'performance'">
            交易绩效
          </button>
          <button class="av-tab" :class="{ active: activeAnalyticsTab === 'correlation' }" @click="activeAnalyticsTab = 'correlation'">
            市场相关性
          </button>
        </nav>
      </div>
    </header>

    <!-- 价格提醒 tab -->
    <div v-show="activeAnalyticsTab === 'alerts'" class="av-panel">
      <section class="card">
        <div class="section-header">
          <div>
            <h3 class="card-title">价格提醒</h3>
            <p class="section-desc">到价或 24H 涨跌幅触发后，会通过 WebSocket 推送桌面通知。</p>
          </div>
            <div class="header-actions">
            <button class="btn btn-ghost btn-sm" @click="alertFormOpen = !alertFormOpen">
              {{ alertFormOpen ? '收起' : '展开新增' }}
            </button>
            <button class="btn btn-primary" @click="createAlert" :disabled="creatingAlert || availableSymbols.length === 0 || !alertFormOpen">
              {{ creatingAlert ? '创建中...' : '新增提醒' }}
            </button>
          </div>
        </div>

        <div v-show="alertFormOpen" class="form-grid">
          <div class="form-group">
            <label>市场类型</label>
            <select v-model="alertForm.instType" class="select">
              <option value="SPOT">现货</option>
              <option value="SWAP">永续合约</option>
            </select>
          </div>
          <div class="form-group">
            <label>币种</label>
            <select v-model="alertForm.symbol" class="select">
              <option v-for="symbol in availableSymbols" :key="symbol" :value="symbol">{{ symbol }}</option>
            </select>
          </div>
          <div class="form-group">
            <label>提醒类型</label>
            <select v-model="alertForm.alertType" class="select">
              <option value="price">目标价</option>
              <option value="change">24H 涨跌幅</option>
            </select>
          </div>
          <div class="form-group">
            <label>方向</label>
            <select v-model="alertForm.direction" class="select">
              <option value="above">向上突破</option>
              <option value="below">向下跌破</option>
            </select>
          </div>
          <div class="form-group">
            <label>{{ alertTargetLabel }}</label>
            <input
              v-model.number="alertForm.targetValue"
              class="input"
              type="number"
              :step="alertForm.alertType === 'price' ? 0.01 : 0.1"
              :placeholder="alertForm.alertType === 'price' ? '例如 65000' : '例如 5 表示 5%'"
            />
          </div>
          <div class="form-group">
            <label>冷却时间（秒）</label>
            <input v-model.number="alertForm.cooldownSeconds" class="input" type="number" min="0" max="86400" />
          </div>
          <div class="form-group form-group-span-2">
            <label>备注</label>
            <input v-model="alertForm.note" class="input" type="text" placeholder="例如：突破区间上沿后关注回踩" />
          </div>
          <label class="checkbox-row">
            <input v-model="alertForm.triggerOnce" type="checkbox" />
            <span>触发一次后自动关闭</span>
          </label>
        </div>

        <div v-if="alertError" class="error-message">{{ alertError }}</div>

        <!-- 已配置提醒 + 最近触发 横向双栏 -->
        <div class="alerts-two-col">
          <div class="alerts-col">
            <div class="list-header">
              <h4>已配置提醒</h4>
              <button class="btn btn-secondary btn-sm" @click="loadAlerts" :disabled="loadingAlerts">刷新</button>
            </div>
            <div v-if="loadingAlerts" class="empty-state">加载中...</div>
            <div v-else-if="alerts.length === 0" class="empty-state">暂无提醒</div>
            <div v-else class="alert-list">
              <div v-for="alert in alerts" :key="alert.id" class="alert-item">
                <div class="alert-main">
                  <div class="alert-title-row">
                    <span class="alert-symbol">{{ alert.inst_id }}</span>
                    <span class="alert-badge" :class="alert.enabled ? 'badge-on' : 'badge-off'">
                      {{ alert.enabled ? '启用' : '关闭' }}
                    </span>
                  </div>
                  <div class="alert-meta">
                    <span>{{ alert.alert_type === 'price' ? '目标价' : '涨跌幅' }}</span>
                    <span>{{ alert.direction === 'above' ? '↑' : '↓' }}</span>
                    <span>{{ formatAlertThreshold(alert) }}</span>
                  </div>
                </div>
                <div class="alert-actions">
                  <button class="btn btn-secondary btn-sm" @click="toggleAlert(alert)">
                    {{ alert.enabled ? '停' : '启' }}
                  </button>
                  <button class="btn btn-danger btn-sm" @click="removeAlert(alert.id)">删</button>
                </div>
              </div>
            </div>
          </div>

          <div class="alerts-col">
            <div class="list-header">
              <h4>最近触发</h4>
            </div>
            <div v-if="recentAlerts.length === 0" class="empty-state">暂无触发记录</div>
            <div v-else class="recent-alerts">
              <div v-for="item in recentAlerts" :key="`${item.id}-${item.triggered_at}`" class="recent-alert-item">
                <div class="recent-alert-header">
                  <div class="recent-alert-title">{{ item.title }}</div>
                  <div class="recent-alert-badges">
                    <span class="mini-badge" :class="item.alert_type === 'price' ? 'badge-blue' : 'badge-purple'">{{ item.alert_type === 'price' ? '目标价' : '涨跌幅' }}</span>
                    <span class="mini-badge" :class="item.direction === 'above' ? 'badge-green' : 'badge-red'">{{ item.direction === 'above' ? '↑' : '↓' }}</span>
                  </div>
                </div>
                <div class="recent-alert-message">{{ item.message }}</div>
                <div class="recent-alert-time">{{ formatDateTime(item.triggered_at) }}</div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>

    <!-- 交易绩效 tab -->
    <div v-show="activeAnalyticsTab === 'performance'" class="av-panel">
      <section class="card">
        <div class="section-header">
          <div>
            <h3 class="card-title">交易记录与绩效统计</h3>
            <p class="section-desc">基于本地成交记录计算已实现盈亏、胜率、盈亏比和回撤。</p>
          </div>
          <div class="toolbar">
            <button class="btn btn-secondary btn-sm" @click="loadPerformance" :disabled="loadingPerformance">
              {{ loadingPerformance ? '刷新中...' : '刷新' }}
            </button>
            <button class="btn btn-primary btn-sm" @click="exportPerformance" :disabled="loadingPerformance">
              导出 CSV
            </button>
          </div>
        </div>

        <div class="form-grid">
          <div class="form-group">
            <label>交易模式</label>
            <select v-model="performanceFilter.mode" class="select">
              <option value="simulated">模拟盘</option>
              <option value="live">实盘</option>
            </select>
          </div>
          <div class="form-group">
            <label>交易对过滤</label>
            <select v-model="performanceFilter.instId" class="select">
              <option value="">全部交易对</option>
              <option v-for="symbol in availableSymbols" :key="`perf-${symbol}`" :value="symbol">{{ symbol }}</option>
            </select>
          </div>
        </div>

        <div v-if="performanceError" class="error-message">{{ performanceError }}</div>

        <div class="summary-grid">
          <div class="summary-card">
            <span class="summary-label">已实现盈亏</span>
            <span class="summary-value" :class="performance.summary.realized_pnl >= 0 ? 'price-up' : 'price-down'">
              {{ formatMoney(performance.summary.realized_pnl) }}
            </span>
          </div>
          <div class="summary-card">
            <span class="summary-label">胜率</span>
            <span class="summary-value">{{ formatPercent(performance.summary.win_rate) }}</span>
          </div>
          <div class="summary-card">
            <span class="summary-label">盈亏比</span>
            <span class="summary-value">{{ formatRatio(performance.summary.profit_loss_ratio) }}</span>
          </div>
          <div class="summary-card">
            <span class="summary-label">利润因子</span>
            <span class="summary-value">{{ formatRatio(performance.summary.profit_factor) }}</span>
          </div>
          <div class="summary-card">
            <span class="summary-label">最大回撤</span>
            <span class="summary-value price-down">
              {{ formatMoney(performance.summary.max_drawdown_amount) }} / {{ formatPercent(performance.summary.max_drawdown_pct) }}
            </span>
          </div>
          <div class="summary-card">
            <span class="summary-label">成交次数</span>
            <span class="summary-value">{{ performance.summary.trade_count || 0 }}</span>
          </div>
        </div>

        <!-- 收益曲线 + 统计表 横向双栏 -->
        <div class="perf-two-col">
          <div class="perf-col-chart">
            <div class="pnl-chart-header">
              <span class="pnl-chart-title">累计盈亏曲线</span>
            </div>
            <div v-if="pnlChartData.length > 0" ref="pnlChartRef" class="pnl-chart"></div>
            <div v-else class="empty-state pnl-chart-empty">暂无数据</div>
          </div>

          <div class="perf-col-table">
            <div class="segmented">
              <button class="segment" :class="{ active: performanceTab === 'daily' }" @click="performanceTab = 'daily'">日统计</button>
              <button class="segment" :class="{ active: performanceTab === 'monthly' }" @click="performanceTab = 'monthly'">月统计</button>
            </div>
            <div v-if="currentPerformancePeriods.length === 0" class="empty-state">暂无统计</div>
            <div v-else class="table-wrapper">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>周期</th>
                    <th>盈亏</th>
                    <th>成交额</th>
                    <th>次数</th>
                    <th>胜率</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="row in currentPerformancePeriods" :key="`${performanceTab}-${row.period}`">
                    <td>{{ row.period }}</td>
                    <td :class="row.realized_pnl >= 0 ? 'price-up' : 'price-down'">{{ formatMoney(row.realized_pnl) }}</td>
                    <td>{{ formatMoney(row.turnover) }}</td>
                    <td>{{ row.trade_count }}</td>
                    <td>{{ formatPercent(row.win_rate) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <div class="list-header">
          <h4>最近已实现盈亏成交</h4>
        </div>
        <div v-if="performance.recent_trades.length === 0" class="empty-state">暂无已平仓成交</div>
        <div v-else class="table-wrapper">
          <table class="data-table">
            <thead>
              <tr>
                <th>时间</th>
                <th>交易对</th>
                <th>价格</th>
                <th>数量</th>
                <th>成本</th>
                <th>已实现盈亏</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="trade in performance.recent_trades" :key="`${trade.inst_id}-${trade.ts}`">
                <td>{{ formatTimestamp(trade.ts) }}</td>
                <td>{{ trade.inst_id }}</td>
                <td>{{ formatPrice(trade.fill_px) }}</td>
                <td>{{ formatNumber(trade.fill_sz, 6) }}</td>
                <td>{{ formatMoney(trade.cost_basis) }}</td>
                <td :class="trade.realized_pnl >= 0 ? 'price-up' : 'price-down'">{{ formatMoney(trade.realized_pnl) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>

    <!-- 市场相关性 tab -->
    <div v-show="activeAnalyticsTab === 'correlation'" class="av-panel">
      <section class="card">
        <div class="section-header">
          <div>
            <h3 class="card-title">市场相关性分析</h3>
            <p class="section-desc">基于公共时间轴上的收益率序列计算 Pearson 相关系数。</p>
          </div>
          <button class="btn btn-primary btn-sm" @click="loadCorrelation" :disabled="loadingCorrelation">
            {{ loadingCorrelation ? '分析中...' : '开始分析' }}
          </button>
        </div>

        <div class="form-grid">
          <div class="form-group">
            <label>市场类型</label>
            <select v-model="correlationFilter.instType" class="select">
              <option value="SPOT">现货</option>
              <option value="SWAP">永续合约</option>
            </select>
          </div>
          <div class="form-group">
            <label>时间周期</label>
            <select v-model="correlationFilter.timeframe" class="select">
              <option value="1m">1分钟</option>
              <option value="5m">5分钟</option>
              <option value="1H">1小时</option>
              <option value="4H">4小时</option>
              <option value="1D">1天</option>
            </select>
          </div>
          <div class="form-group">
            <label>分析天数</label>
            <input v-model.number="correlationFilter.days" class="input" type="number" min="1" max="365" />
          </div>
        </div>

        <div class="symbol-picker-header">
          <span class="symbol-picker-label">选择币种</span>
          <span class="symbol-picker-count" :class="{ 'count-full': correlationFilter.symbols.length >= 6 }">
            已选 {{ correlationFilter.symbols.length }}/6
          </span>
        </div>
        <div class="symbol-picker">
          <button
            v-for="symbol in availableSymbols.slice(0, 12)"
            :key="`corr-${symbol}`"
            class="symbol-chip"
            :class="{ active: correlationFilter.symbols.includes(symbol), disabled: !correlationFilter.symbols.includes(symbol) && correlationFilter.symbols.length >= 6 }"
            @click="toggleCorrelationSymbol(symbol)"
          >
            {{ symbol }}
          </button>
          <span v-if="availableSymbols.length > 12" class="symbol-chip-more">+{{ availableSymbols.length - 12 }}</span>
        </div>

        <div v-if="correlationError" class="error-message">{{ correlationError }}</div>

        <div class="correlation-layout">
          <div ref="correlationChartRef" class="correlation-chart"></div>

          <div class="correlation-side">
            <div class="pair-block">
              <h4>最高正相关</h4>
              <div v-if="correlation.top_positive.length === 0" class="empty-state small">暂无数据</div>
              <div v-else class="pair-list">
                <div v-for="item in correlation.top_positive" :key="`pos-${item.pair}`" class="pair-item">
                  <span>{{ item.pair }}</span>
                  <strong>{{ formatRatio(item.correlation) }}</strong>
                </div>
              </div>
            </div>

            <div class="pair-block">
              <h4>最低相关</h4>
              <div v-if="correlation.top_negative.length === 0" class="empty-state small">暂无数据</div>
              <div v-else class="pair-list">
                <div v-for="item in correlation.top_negative" :key="`neg-${item.pair}`" class="pair-item">
                  <span>{{ item.pair }}</span>
                  <strong>{{ formatRatio(item.correlation) }}</strong>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onActivated, onDeactivated, onMounted, onUnmounted, reactive, ref, watch } from 'vue';
import * as echarts from 'echarts';
import { api } from '../services/api';
import marketWS from '../services/websocket';
import {
  normalizeMonitorSymbol,
  formatMoney,
  formatPrice,
  formatPercentValue,
  formatTimestamp,
  formatDateTime,
  toFiniteNumber,
} from '../utils/formatting';

const activeAnalyticsTab = ref('alerts');

defineOptions({
  name: 'AnalyticsView',
});

const alertFormOpen = ref(false);
const loadingAlerts = ref(false);
const creatingAlert = ref(false);
const alertError = ref('');
const alerts = ref([]);
const recentAlerts = ref([]);

const DEFAULT_SUMMARY = {
  realized_pnl: 0,
  win_rate: 0,
  profit_loss_ratio: 0,
  profit_factor: 0,
  max_drawdown_amount: 0,
  max_drawdown_pct: 0,
  trade_count: 0,
};
const performance = reactive({
  summary: { ...DEFAULT_SUMMARY },
  daily: [],
  monthly: [],
  recent_trades: [],
});
const performanceTab = ref('daily');
const performanceError = ref('');
const loadingPerformance = ref(false);

const correlation = reactive({
  symbols: [],
  matrix: [],
  top_positive: [],
  top_negative: [],
});
const loadingCorrelation = ref(false);
const correlationError = ref('');
const correlationChartRef = ref(null);

const availableSymbols = ref([]);
const correlationFilter = reactive({
  instType: 'SPOT',
  timeframe: '1H',
  days: 30,
  symbols: ['BTC-USDT', 'ETH-USDT', 'SOL-USDT'],
});
const alertForm = reactive({
  instType: 'SPOT',
  symbol: 'BTC-USDT',
  alertType: 'price',
  direction: 'above',
  targetValue: null,
  cooldownSeconds: 300,
  triggerOnce: true,
  note: '',
});
const performanceFilter = reactive({
  mode: 'simulated',
  instId: '',
});

const alertTargetLabel = computed(() => {
  return alertForm.alertType === 'price' ? '目标价格（USDT）' : '目标涨跌幅（%）';
});

const currentPerformancePeriods = computed(() => {
  return performanceTab.value === 'monthly' ? performance.monthly : performance.daily;
});

const pnlChartRef = ref(null);
let pnlChart = null;
let pnlResizeHandler = null;

const pnlChartData = computed(() => {
  const rows = performance.daily;
  if (!rows || rows.length === 0) return [];
  let cumulative = 0;
  return rows.map(row => {
    cumulative += Number(row.realized_pnl || 0);
    return { period: row.period, value: cumulative };
  });
});

const updatePnlChart = () => {
  nextTick(() => {
    // v-if 切换后 DOM 节点是新的，旧实例需销毁重建
    if (pnlChart) {
      window.removeEventListener('resize', pnlResizeHandler);
      pnlChart.dispose();
      pnlChart = null;
    }
    if (!pnlChartRef.value) return;
    pnlChart = echarts.init(pnlChartRef.value);
    pnlResizeHandler = () => pnlChart?.resize();
    window.addEventListener('resize', pnlResizeHandler);
    const data = pnlChartData.value;
    if (data.length === 0) return;
    const isPositive = data[data.length - 1]?.value >= 0;
    pnlChart.setOption({
      tooltip: {
        trigger: 'axis',
        formatter: (params) => {
          const p = params[0];
          return `${p.name}<br/>累计盈亏：$${Number(p.value).toFixed(2)}`;
        },
      },
      grid: { top: 16, left: 56, right: 16, bottom: 28 },
      xAxis: {
        type: 'category',
        data: data.map(d => d.period),
        axisLabel: { color: 'var(--text-muted)', fontSize: 10 },
        axisLine: { lineStyle: { color: 'var(--border-color)' } },
        boundaryGap: false,
      },
      yAxis: {
        type: 'value',
        axisLabel: { color: 'var(--text-muted)', fontSize: 10, formatter: v => `$${v}` },
        splitLine: { lineStyle: { color: 'rgba(255,255,255,0.08)' } },
      },
      series: [{
        type: 'line',
        data: data.map(d => d.value),
        smooth: true,
        symbol: 'none',
        lineStyle: { color: isPositive ? 'var(--color-success)' : 'var(--color-danger)', width: 2 },
        areaStyle: {
          color: {
            type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: isPositive ? 'rgba(34,197,94,0.24)' : 'rgba(239,68,68,0.24)' },
              { offset: 1, color: 'rgba(0,0,0,0)' },
            ],
          },
        },
      }],
    });
  });
};

let correlationChart = null;
let resizeHandler = null;
let alertListener = null;
let perfLoadTimer = null;

const buildInstId = (symbol, instType) => (instType === 'SWAP' ? `${symbol}-SWAP` : symbol);

const formatRatio = (value) => toFiniteNumber(value).toFixed(2);
const formatNumber = (value, digits = 2) => toFiniteNumber(value).toFixed(digits);
const formatPercent = (value) => formatPercentValue(value);
const formatAlertThreshold = (alert) => {
  if (alert.alert_type === 'change') {
    return `${Number(alert.change_percent || 0).toFixed(2)}%`;
  }
  return `$${Number(alert.target_price || 0).toFixed(2)}`;
};

const loadAvailableSymbols = async () => {
  try {
    const res = await api.getAvailableSymbols();
    if (res.code === 0 && Array.isArray(res.data) && res.data.length > 0) {
      const unique = [...new Set(res.data.map(item => normalizeMonitorSymbol(item.inst_id || item)).filter(Boolean))];
      availableSymbols.value = unique;
    } else {
      availableSymbols.value = ['BTC-USDT', 'ETH-USDT', 'SOL-USDT', 'DOGE-USDT'];
    }
  } catch (error) {
    console.error('加载可用币种失败:', error);
    availableSymbols.value = ['BTC-USDT', 'ETH-USDT', 'SOL-USDT', 'DOGE-USDT'];
  }

  if (!availableSymbols.value.includes(alertForm.symbol)) {
    alertForm.symbol = availableSymbols.value[0] || 'BTC-USDT';
  }
  correlationFilter.symbols = correlationFilter.symbols.filter(symbol => availableSymbols.value.includes(symbol));
  if (correlationFilter.symbols.length < 2) {
    correlationFilter.symbols = availableSymbols.value.slice(0, 3);
  }
};

const loadAlerts = async () => {
  loadingAlerts.value = true;
  alertError.value = '';
  try {
    const res = await api.getPriceAlerts();
    alerts.value = res.data || [];
  } catch (error) {
    console.error('加载价格提醒失败:', error);
    alertError.value = error.response?.data?.detail || error.message || '加载价格提醒失败';
  } finally {
    loadingAlerts.value = false;
  }
};

const createAlert = async () => {
  creatingAlert.value = true;
  alertError.value = '';
  try {
    const instId = buildInstId(alertForm.symbol, alertForm.instType);
    const payload = {
      inst_id: instId,
      inst_type: alertForm.instType,
      symbol: alertForm.symbol,
      alert_type: alertForm.alertType,
      direction: alertForm.direction,
      note: alertForm.note,
      trigger_once: alertForm.triggerOnce,
      cooldown_seconds: alertForm.cooldownSeconds,
    };

    if (alertForm.alertType === 'price') {
      payload.target_price = Number(alertForm.targetValue);
    } else {
      payload.change_percent = Number(alertForm.targetValue);
    }

    await api.createPriceAlert(payload);
    alertForm.targetValue = null;
    alertForm.note = '';
    await loadAlerts();
  } catch (error) {
    console.error('创建价格提醒失败:', error);
    alertError.value = error.response?.data?.detail || error.message || '创建价格提醒失败';
  } finally {
    creatingAlert.value = false;
  }
};

const toggleAlert = async (alert) => {
  try {
    await api.updatePriceAlert(alert.id, { enabled: !alert.enabled });
    await loadAlerts();
  } catch (error) {
    console.error('更新价格提醒失败:', error);
    alertError.value = error.response?.data?.detail || error.message || '更新价格提醒失败';
  }
};

const removeAlert = async (alertId) => {
  try {
    await api.deletePriceAlert(alertId);
    alerts.value = alerts.value.filter(item => item.id !== alertId);
  } catch (error) {
    console.error('删除价格提醒失败:', error);
    alertError.value = error.response?.data?.detail || error.message || '删除价格提醒失败';
  }
};

const loadPerformance = async () => {
  loadingPerformance.value = true;
  performanceError.value = '';
  try {
    const res = await api.getTradePerformance(performanceFilter.mode, performanceFilter.instId);
    performance.summary = { ...DEFAULT_SUMMARY, ...(res.summary || {}) };
    performance.daily = res.daily || [];
    performance.monthly = res.monthly || [];
    performance.recent_trades = res.recent_trades || [];
    updatePnlChart();
  } catch (error) {
    console.error('加载绩效统计失败:', error);
    performanceError.value = error.response?.data?.detail || error.message || '加载绩效统计失败';
  } finally {
    loadingPerformance.value = false;
  }
};

const debouncedLoadPerformance = () => {
  clearTimeout(perfLoadTimer);
  perfLoadTimer = setTimeout(loadPerformance, 300);
};

const exportPerformance = async () => {
  try {
    const blob = await api.exportTradePerformance(performanceFilter.mode, performanceFilter.instId);
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `trade-performance-${performanceFilter.mode}-${performanceFilter.instId || 'all'}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  } catch (error) {
    console.error('导出绩效统计失败:', error);
    performanceError.value = error.response?.data?.detail || error.message || '导出绩效统计失败';
  }
};

const toggleCorrelationSymbol = (symbol) => {
  if (correlationFilter.symbols.includes(symbol)) {
    if (correlationFilter.symbols.length <= 2) return;
    correlationFilter.symbols = correlationFilter.symbols.filter(item => item !== symbol);
    return;
  }
  if (correlationFilter.symbols.length >= 6) return;
  correlationFilter.symbols = [...correlationFilter.symbols, symbol];
};

const initCorrelationChart = () => {
  if (!correlationChartRef.value) return;
  correlationChart = echarts.init(correlationChartRef.value);
  resizeHandler = () => {
    correlationChart?.resize();
  };
  window.addEventListener('resize', resizeHandler);
};

const updateCorrelationChart = () => {
  nextTick(() => {
    if (!correlationChart && correlationChartRef.value) {
      initCorrelationChart();
    }
    if (!correlationChart) return;

    correlationChart.setOption({
      tooltip: {
        position: 'top',
        formatter: (params) => {
          const xIndex = params.data[0];
          const yIndex = params.data[1];
          const value = params.data[2];
          const xSymbol = correlation.symbols[xIndex];
          const ySymbol = correlation.symbols[yIndex];
          return `${ySymbol} / ${xSymbol}<br/>相关系数：${Number(value).toFixed(4)}`;
        },
      },
      grid: {
        top: 40,
        left: 80,
        right: 20,
        bottom: 60,
      },
      xAxis: {
        type: 'category',
        data: correlation.symbols,
        axisLabel: { color: 'var(--text-secondary)', rotate: 20 },
        axisLine: { lineStyle: { color: 'rgba(255,255,255,0.12)' } },
      },
      yAxis: {
        type: 'category',
        data: correlation.symbols,
        axisLabel: { color: 'var(--text-secondary)' },
        axisLine: { lineStyle: { color: 'rgba(255,255,255,0.12)' } },
      },
      visualMap: {
        min: -1,
        max: 1,
        calculable: false,
        orient: 'horizontal',
        left: 'center',
        bottom: 0,
        textStyle: { color: 'var(--text-secondary)' },
        inRange: {
          color: ['#1E293B', '#3B82F6', '#FFD600', '#F7931A', '#C2410C'],
        },
      },
      series: [
        {
          type: 'heatmap',
          data: correlation.matrix.flatMap((row, y) => row.map((value, x) => [x, y, value])),
          label: {
            show: true,
            color: '#030304',
            formatter: ({ data }) => Number(data[2]).toFixed(2),
          },
          emphasis: {
            itemStyle: {
              borderColor: 'rgba(255,255,255,0.8)',
              borderWidth: 1,
            },
          },
        },
      ],
    });
  });
};

const loadCorrelation = async () => {
  if (correlationFilter.symbols.length < 2) {
    correlationError.value = '至少选择 2 个币种';
    return;
  }

  loadingCorrelation.value = true;
  correlationError.value = '';

  try {
    const symbols = correlationFilter.symbols.map(symbol => buildInstId(symbol, correlationFilter.instType));
    const res = await api.getMarketCorrelation({
      symbols,
      timeframe: correlationFilter.timeframe,
      days: correlationFilter.days,
      limit: 300,
      inst_type: correlationFilter.instType,
    });

    correlation.symbols = res.data?.symbols || [];
    correlation.matrix = res.data?.matrix || [];
    correlation.top_positive = res.data?.top_positive || [];
    correlation.top_negative = res.data?.top_negative || [];
    updateCorrelationChart();
  } catch (error) {
    console.error('加载相关性分析失败:', error);
    correlationError.value = error.response?.data?.detail || error.message || '加载相关性分析失败';
  } finally {
    loadingCorrelation.value = false;
  }
};

watch(() => performanceFilter.mode, debouncedLoadPerformance);
watch(() => performanceFilter.instId, debouncedLoadPerformance);

onMounted(async () => {
  await Promise.all([
    loadAvailableSymbols(),
    loadAlerts(),
    loadPerformance(),
  ]);
  await loadCorrelation();

  alertListener = (alert) => {
    recentAlerts.value = [alert, ...recentAlerts.value].slice(0, 8);
  };
  marketWS.subscribeAlerts(alertListener);
});

onActivated(() => {
  if (resizeHandler) window.addEventListener('resize', resizeHandler);
  if (pnlResizeHandler) window.addEventListener('resize', pnlResizeHandler);
  nextTick(() => {
    correlationChart?.resize();
    pnlChart?.resize();
  });
});

onDeactivated(() => {
  if (resizeHandler) window.removeEventListener('resize', resizeHandler);
  if (pnlResizeHandler) window.removeEventListener('resize', pnlResizeHandler);
});

onUnmounted(() => {
  if (alertListener) marketWS.unsubscribeAlerts(alertListener);
  if (resizeHandler) window.removeEventListener('resize', resizeHandler);
  if (pnlResizeHandler) window.removeEventListener('resize', pnlResizeHandler);
  clearTimeout(perfLoadTimer);
  if (correlationChart) { correlationChart.dispose(); correlationChart = null; }
  if (pnlChart) { pnlChart.dispose(); pnlChart = null; }
});
</script>

<style scoped>
.analytics-view {
  display: flex;
  flex-direction: column;
  gap: 0;
  height: 100%;
  overflow: hidden;
}

/* 命令栏 */
.av-command-bar {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 6px 14px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.av-left {
  display: flex;
  align-items: center;
  gap: 20px;
  min-width: 0;
}

.av-title {
  margin: 0;
  font-family: var(--font-heading);
  font-size: 17px;
  font-weight: 700;
  white-space: nowrap;
  background: linear-gradient(to right, var(--text-primary), var(--accent-color));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.av-tabs {
  display: inline-flex;
  gap: 4px;
  padding: 3px;
  border-radius: var(--radius-pill);
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.av-tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 18px;
  font-size: 12px;
  font-weight: 600;
  font-family: var(--font-mono);
  letter-spacing: 0.3px;
  border-radius: var(--radius-pill);
  border: none;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.18s ease;
}

.av-tab:hover {
  color: var(--text-primary);
  background: rgba(255, 255, 255, 0.06);
}

.av-tab.active {
  color: #fff;
  background: linear-gradient(135deg, #EA580C, #F7931A);
  box-shadow: 0 0 16px -4px rgba(247, 147, 26, 0.4);
}

.av-tab-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  font-size: 10px;
  font-weight: 700;
  border-radius: var(--radius-pill);
  background: rgba(255, 255, 255, 0.2);
}

.av-tab.active .av-tab-count {
  background: rgba(255, 255, 255, 0.25);
}

/* 面板 */
.av-panel {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 14px 6px;
}

/* 提醒双栏 */
.alerts-two-col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-top: 16px;
}

.alerts-col {
  min-width: 0;
}

/* 绩效双栏 */
.perf-two-col {
  display: grid;
  grid-template-columns: 1.2fr 1fr;
  gap: 16px;
  margin-top: 16px;
}

.perf-col-chart,
.perf-col-table {
  min-width: 0;
}

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

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.form-group-span-2 {
  grid-column: span 2;
}

.checkbox-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--text-primary);
}

.list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin: 16px 0 12px;
}

.list-header h4 {
  font-size: 13px;
  font-weight: 600;
}

.empty-state {
  padding: 18px;
  border: 1px dashed var(--border-color);
  border-radius: 10px;
  font-size: 12px;
  color: var(--text-secondary);
  text-align: center;
}

.empty-state.small {
  padding: 12px;
}

.alert-list,
.recent-alerts {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.alert-item,
.recent-alert-item {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 12px;
  border: 1px solid var(--border-color);
  border-radius: 10px;
  background: rgba(15, 17, 21, 0.6);
}

.alert-main {
  flex: 1;
  min-width: 0;
}

.alert-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
}

.alert-symbol {
  font-weight: 600;
}

.alert-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
}

.badge-on {
  color: var(--color-success);
  background: rgba(34, 197, 94, 0.14);
}

.badge-off {
  color: var(--text-secondary);
  background: rgba(148, 163, 184, 0.12);
}

.alert-meta,
.alert-submeta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  font-size: 12px;
  color: var(--text-secondary);
}

.alert-submeta {
  margin-top: 6px;
}

.alert-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.btn-danger {
  background: rgba(239, 68, 68, 0.18);
  color: var(--color-danger);
  border: 1px solid rgba(239, 68, 68, 0.3);
}

.recent-alert-item {
  flex-direction: column;
}

.recent-alert-title {
  font-weight: 600;
}

.recent-alert-message,
.recent-alert-time {
  font-size: 12px;
  color: var(--text-secondary);
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.summary-card {
  padding: 14px;
  border-radius: 12px;
  background: linear-gradient(180deg, rgba(15, 17, 21, 0.72), rgba(15, 17, 21, 0.38));
  border: 1px solid rgba(255, 255, 255, 0.08);
  transition: border-color 0.3s ease, box-shadow 0.3s ease, transform 0.3s ease;
}

.summary-card:hover {
  border-color: rgba(247, 147, 26, 0.25);
  box-shadow: 0 0 20px -5px rgba(247, 147, 26, 0.1);
  transform: translateY(-1px);
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

.segmented {
  display: inline-flex;
  gap: 8px;
  padding: 4px;
  border-radius: 999px;
  background: rgba(15, 17, 21, 0.5);
  margin-bottom: 16px;
}

.segment {
  padding: 8px 14px;
  border: none;
  border-radius: 999px;
  color: var(--text-secondary);
  background: transparent;
  cursor: pointer;
}

.segment.active {
  color: #030304;
  background: var(--accent-color);
}

.table-wrapper {
  overflow: auto;
  border: 1px solid var(--border-color);
  border-radius: 10px;
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
}

.data-table th {
  color: var(--text-secondary);
  background: rgba(15, 17, 21, 0.72);
}

.symbol-picker {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 16px;
}

.symbol-chip {
  padding: 8px 12px;
  border: 1px solid var(--border-color);
  border-radius: 999px;
  background: rgba(15, 17, 21, 0.5);
  color: var(--text-secondary);
  cursor: pointer;
}

.symbol-chip.active {
  color: #030304;
  background: var(--accent-color);
  border-color: var(--accent-color);
}

.correlation-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 280px;
  gap: 16px;
  align-items: start;
}

.correlation-chart {
  height: 360px;
  overflow: hidden;
  border-radius: 8px;
}

.correlation-side {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.pair-block h4 {
  margin-bottom: 10px;
  font-size: 13px;
}

.pair-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.pair-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 10px;
  background: rgba(15, 17, 21, 0.58);
  border: 1px solid var(--border-color);
}

.header-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.btn-ghost {
  background: transparent;
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
}

.btn-ghost:hover {
  background: rgba(255,255,255,0.04);
  color: var(--text-primary);
}

.pnl-chart-header {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 8px;
}

.pnl-chart-title {
  font-size: 13px;
  font-weight: 600;
}

.pnl-chart-hint {
  font-size: 11px;
  color: var(--text-muted);
}

.pnl-chart {
  height: 160px;
  width: 100%;
  margin-bottom: 16px;
  border-radius: 10px;
  overflow: hidden;
  position: relative;
  contain: strict;
}

.pnl-chart-empty {
  height: 60px;
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.recent-alert-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 4px;
}

.recent-alert-badges {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}

.mini-badge {
  padding: 1px 7px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 600;
}

.badge-blue  { background: rgba(59,130,246,0.18); color: var(--color-info); }
.badge-purple { background: rgba(234,88,12,0.16); color: var(--secondary-color); }
.badge-green { background: rgba(34,197,94,0.18);  color: var(--color-success); }
.badge-red   { background: rgba(239,68,68,0.18);  color: var(--color-danger); }

.symbol-picker-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.symbol-picker-label {
  font-size: 12px;
  color: var(--text-secondary);
}

.symbol-picker-count {
  font-size: 11px;
  color: var(--text-muted);
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(255,255,255,0.04);
}

.symbol-picker-count.count-full {
  color: var(--gold-color);
  background: rgba(247,147,26,0.12);
}

.symbol-chip.disabled {
  opacity: 0.38;
  cursor: not-allowed;
}

.symbol-chip-more {
  display: inline-flex;
  align-items: center;
  padding: 8px 12px;
  font-size: 12px;
  color: var(--text-muted);
}

.error-message {
  padding: 10px 12px;
  margin-bottom: 12px;
  border-radius: 8px;
  color: var(--color-danger);
  background: rgba(127, 29, 29, 0.22);
  border: 1px solid rgba(239, 68, 68, 0.3);
  font-size: 12px;
}

@media (max-width: 1280px) {
  .analytics-grid {
    grid-template-columns: 1fr;
  }

  .correlation-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .form-grid,
  .summary-grid {
    grid-template-columns: 1fr;
  }

  .form-group-span-2 {
    grid-column: span 1;
  }

  .section-header {
    flex-direction: column;
  }
}
</style>
