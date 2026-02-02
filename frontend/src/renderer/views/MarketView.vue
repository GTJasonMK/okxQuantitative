<template>
  <div class="market-view">
    <!-- 连接状态提示 -->
    <div v-if="connectionError" class="connection-error">
      <span class="error-badge">!</span>
      <span>{{ connectionError }}</span>
      <button class="btn-link" @click="checkConnection">重新连接</button>
    </div>

    <!-- 工具栏 -->
    <div class="toolbar">
      <div class="toolbar-left">
        <!-- 监控币种下拉多选 -->
        <div class="dropdown-select dropdown-select-wide" ref="symbolDropdown">
          <div class="dropdown-trigger" @click="toggleSymbolDropdown">
            <span class="label">监控:</span>
            <span class="dropdown-value">
              {{ selectedSymbols.length }} 个币种
              <span v-if="holdingSymbols.length > 0" class="holding-badge">({{ holdingSymbols.length }} 持仓)</span>
            </span>
            <span class="dropdown-arrow" :class="{ open: showSymbolDropdown }">▼</span>
          </div>
          <div class="dropdown-menu dropdown-menu-symbols" v-show="showSymbolDropdown">
            <!-- 搜索框 -->
            <div class="dropdown-search">
              <input
                type="text"
                v-model="symbolSearch"
                placeholder="搜索或输入币种添加..."
                @keyup.enter="addCustomSymbol"
              />
              <button class="btn-add" @click="addCustomSymbol" v-if="symbolSearch.trim()">添加</button>
            </div>
            <!-- 币种列表 -->
            <div class="dropdown-options symbol-options">
              <div
                v-for="symbol in filteredSymbols"
                :key="symbol"
                class="dropdown-option"
                :class="{
                  selected: selectedSymbols.includes(symbol),
                  locked: isHoldingSymbol(symbol)
                }"
              >
                <label class="option-label" @click.prevent="toggleSymbol(symbol)">
                  <span class="checkbox-mark"></span>
                  <span class="symbol-name">{{ symbol }}</span>
                  <span v-if="isHoldingSymbol(symbol)" class="lock-icon" title="持仓币种（可取消监控，但不可从列表删除）">L</span>
                </label>
                <button
                  v-if="!isHoldingSymbol(symbol)"
                  class="btn-remove"
                  @click.stop="removeSymbol(symbol)"
                  title="从列表中删除"
                >X</button>
              </div>
            </div>
            <!-- 操作按钮 -->
            <div class="dropdown-actions">
              <button class="btn-text" @click="selectAllSymbols">全选</button>
              <button class="btn-text" @click="clearAllSymbols">仅保留持仓</button>
            </div>
          </div>
        </div>

        <!-- 时间周期下拉单选 -->
        <div class="dropdown-select" ref="timeframeDropdown">
          <div class="dropdown-trigger" @click="toggleTimeframeDropdown">
            <span class="label">周期:</span>
            <span class="dropdown-value">{{ currentTimeframeLabel }}</span>
            <span class="dropdown-arrow" :class="{ open: showTimeframeDropdown }">▼</span>
          </div>
          <div class="dropdown-menu dropdown-menu-sm" v-show="showTimeframeDropdown">
            <label
              v-for="tf in timeframes"
              :key="tf.value"
              class="dropdown-option"
              :class="{ selected: currentTimeframe === tf.value }"
              @click="selectTimeframe(tf.value)"
            >
              <span class="radio-mark"></span>
              {{ tf.label }}
            </label>
          </div>
        </div>

        <!-- 技术指标多选下拉 -->
        <div class="dropdown-select" ref="indicatorDropdown">
          <div class="dropdown-trigger" @click="toggleIndicatorDropdown">
            <span class="label">指标:</span>
            <span class="dropdown-value">已选 {{ selectedIndicatorsCount }} 个</span>
            <span class="dropdown-arrow" :class="{ open: showIndicatorDropdown }">▼</span>
          </div>
          <div class="dropdown-menu dropdown-menu-indicator" v-show="showIndicatorDropdown">
            <div class="dropdown-options">
              <!-- 均线组 -->
              <div class="indicator-group">
                <div class="group-header">均线 MA</div>
                <label
                  v-for="ma in maIndicators"
                  :key="ma.key"
                  class="dropdown-option"
                  :class="{ selected: indicators[ma.key] }"
                  @click.prevent="toggleIndicator(ma.key)"
                >
                  <span class="checkbox-mark"></span>
                  <span class="indicator-color" :style="{ background: ma.color }"></span>
                  {{ ma.label }}
                </label>
              </div>
              <!-- EMA组 -->
              <div class="indicator-group">
                <div class="group-header">指数均线 EMA</div>
                <label
                  v-for="ema in emaIndicators"
                  :key="ema.key"
                  class="dropdown-option"
                  :class="{ selected: indicators[ema.key] }"
                  @click.prevent="toggleIndicator(ema.key)"
                >
                  <span class="checkbox-mark"></span>
                  <span class="indicator-color" :style="{ background: ema.color }"></span>
                  {{ ema.label }}
                </label>
              </div>
              <!-- 布林带 -->
              <div class="indicator-group">
                <div class="group-header">布林带 BOLL</div>
                <label
                  class="dropdown-option"
                  :class="{ selected: indicators.boll }"
                  @click.prevent="toggleIndicator('boll')"
                >
                  <span class="checkbox-mark"></span>
                  <span class="indicator-color" style="background: #ff9800;"></span>
                  BOLL(20,2)
                </label>
              </div>
              <!-- SAR -->
              <div class="indicator-group">
                <div class="group-header">其他</div>
                <label
                  class="dropdown-option"
                  :class="{ selected: indicators.sar }"
                  @click.prevent="toggleIndicator('sar')"
                >
                  <span class="checkbox-mark"></span>
                  <span class="indicator-color" style="background: #e91e63;"></span>
                  SAR
                </label>
              </div>
            </div>
            <div class="dropdown-actions">
              <button class="btn-text" @click="clearAllIndicators">清空全部</button>
            </div>
          </div>
        </div>
      </div>

      <div class="toolbar-right">
        <!-- 自动刷新控制 -->
        <div class="auto-refresh-control">
          <label class="checkbox-label">
            <input type="checkbox" v-model="autoRefresh" @change="toggleAutoRefresh" />
            自动刷新
          </label>
          <select v-model="refreshInterval" class="select-small" @change="restartAutoRefresh" v-if="autoRefresh">
            <option :value="3">3秒</option>
            <option :value="5">5秒</option>
            <option :value="10">10秒</option>
            <option :value="30">30秒</option>
          </select>
        </div>

        <!-- 刷新所有按钮 -->
        <button class="btn" @click="refreshAllCharts" :disabled="loading">
          {{ loading ? '加载中...' : '刷新全部' }}
        </button>

        <!-- 行情监控仅展示“实盘持仓”作为锁定/快捷引用，避免模拟盘虚拟资产干扰 -->

        <!-- 刷新持仓按钮 -->
        <button class="btn" @click="refreshHoldings" :disabled="loading" title="刷新持仓币种">
          刷新持仓
        </button>

        <!-- 买卖标记开关 -->
        <label class="checkbox-label">
          <input type="checkbox" v-model="showTradeMarkers" @change="updateAllCharts" />
          买卖标记
        </label>

        <!-- 同步所有按钮 -->
        <button class="btn btn-primary" @click="syncAllData" :disabled="syncing">
          {{ syncing ? '同步中...' : '同步数据' }}
        </button>
      </div>
    </div>

    <!-- 多图表列表（垂直布局） -->
    <div class="charts-list" ref="chartsContainer">
      <div
        v-for="symbol in selectedSymbols"
        :key="symbol"
        class="chart-card"
      >
        <!-- 图表头部：币种信息和行情 -->
        <div class="chart-header">
          <div class="symbol-info">
            <span class="symbol-name">{{ symbol }}</span>
            <span
              class="symbol-price"
              :class="getTickerClass(symbol)"
            >
              {{ formatPrice(getTicker(symbol)?.last) }}
            </span>
            <span
              class="symbol-change"
              :class="getTickerClass(symbol)"
            >
              {{ formatChange(getTicker(symbol)?.change_24h) }}
            </span>
          </div>
          <div class="chart-actions">
            <button class="btn-icon" @click="refreshChart(symbol)" :disabled="chartLoading[symbol]">
              <span v-if="chartLoading[symbol]" class="spinner-small"></span>
              <span v-else>&#x21bb;</span>
            </button>
            <button class="btn-icon btn-remove" @click="toggleSymbol(symbol)">×</button>
          </div>
        </div>

        <!-- K线图表 -->
        <div class="chart-wrapper">
          <div :ref="el => setChartRef(symbol, el)" class="chart"></div>
          <div v-if="chartLoading[symbol]" class="chart-loading">
            <div class="spinner"></div>
          </div>
          <div v-else-if="chartErrors[symbol]" class="chart-error">
            <div class="error-icon">!</div>
            <div class="error-text">{{ chartErrors[symbol] }}</div>
            <button class="btn btn-sm" @click="refreshChart(symbol)">重试</button>
          </div>
        </div>

        <!-- 图表底部：24h数据 -->
        <div class="chart-footer" v-if="getTicker(symbol)">
          <span>高: {{ formatPrice(getTicker(symbol).high_24h) }}</span>
          <span>低: {{ formatPrice(getTicker(symbol).low_24h) }}</span>
          <span>量: {{ formatVolume(getTicker(symbol).vol_24h) }}</span>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-if="selectedSymbols.length === 0" class="empty-state">
      <div class="empty-text">当前无持仓币种</div>
      <div class="empty-hint">请先在交易页面购买币种，行情监控将自动显示您的持仓</div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, shallowReactive, markRaw, computed, onMounted, onUnmounted, onActivated, onDeactivated, watch, nextTick } from 'vue';
import * as echarts from 'echarts';
import { api, waitForBackend } from '../services/api';
import { useAppStore } from '../stores/app';

// 节流函数 - 限制函数执行频率
const throttle = (fn, delay) => {
  let lastCall = 0;
  return (...args) => {
    const now = Date.now();
    if (now - lastCall >= delay) {
      lastCall = now;
      fn(...args);
    }
  };
};

// 二分查找 - 在有序数组中查找目标时间戳所属的K线索引
const binarySearchCandleIndex = (candles, targetTs, duration) => {
  let left = 0;
  let right = candles.length - 1;

  while (left <= right) {
    const mid = Math.floor((left + right) / 2);
    const candleStart = candles[mid].timestamp;
    const candleEnd = candleStart + duration;

    if (targetTs >= candleStart && targetTs < candleEnd) {
      return mid;
    } else if (targetTs < candleStart) {
      right = mid - 1;
    } else {
      left = mid + 1;
    }
  }
  return -1;
};

// 定义组件名称，用于 keep-alive 缓存
defineOptions({
  name: 'MarketView'
})

const appStore = useAppStore();

// ========== 持久化存储（通过后端 API） ==========
const PREFERENCES_KEY = 'market_settings';

// 保存设置到后端
const saveSettings = async () => {
  try {
    const settings = {
      selectedSymbols: selectedSymbols.value,
      availableSymbols: availableSymbols.value,
      autoRefresh: autoRefresh.value,
      refreshInterval: refreshInterval.value,
      indicators: { ...indicators },
    };
    await api.updatePreferences({ [PREFERENCES_KEY]: settings });
  } catch (e) {
    console.warn('保存行情监控设置失败:', e);
  }
};

// 防抖保存（避免频繁调用 API）
let saveTimer = null;
const debouncedSave = () => {
  if (saveTimer) clearTimeout(saveTimer);
  saveTimer = setTimeout(() => {
    saveSettings();
  }, 500);
};

const availableSymbols = ref([]);   // 从交易所API加载，供下拉选择
const selectedSymbols = ref([]);    // 当前监控的币种
const holdingSymbols = ref([]);     // 持仓币种（锁定，不可删除）
const autoRefresh = ref(true);
const refreshInterval = ref(5);

// 技术指标设置
const indicators = reactive({
  ma5: true,
  ma10: true,
  ma20: false,
  ma60: false,
  ema12: false,
  ema26: false,
  boll: false,
  sar: false,
});

// 买卖标记设置
const showTradeMarkers = ref(true);
const fillsData = shallowReactive({});  // { 'BTC-USDT': [...fills] } - 使用 shallowReactive 减少开销

// 行情监控页：持仓与成交记录统一使用“实盘”，避免模拟盘虚拟资产干扰
const tradingMode = ref('live');

// 设置是否已加载
const settingsLoaded = ref(false);

// 从后端加载设置
const loadSettings = async () => {
  try {
    const res = await api.getPreferences();
    if (res.success && res.data && res.data[PREFERENCES_KEY]) {
      const saved = res.data[PREFERENCES_KEY];
      if (saved.selectedSymbols) selectedSymbols.value = saved.selectedSymbols;
      if (saved.availableSymbols) availableSymbols.value = saved.availableSymbols;
      if (saved.autoRefresh !== undefined) autoRefresh.value = saved.autoRefresh;
      if (saved.refreshInterval !== undefined) refreshInterval.value = saved.refreshInterval;
      if (saved.indicators) {
        Object.assign(indicators, saved.indicators);
      }
    }
  } catch (e) {
    // 加载失败时使用默认值
  } finally {
    settingsLoaded.value = true;
  }
};

// 加载账户持仓币种
const loadHoldingSymbols = async () => {
  try {
    const res = await api.getSpotHoldings(tradingMode.value);
    if (res.holdings && res.holdings.length > 0) {
      // 提取非稳定币的币种，转为交易对格式
      // API 返回字段: ccy, total, available, is_stablecoin
      const symbols = res.holdings
        .filter(h => !h.is_stablecoin && parseFloat(h.total || '0') > 0)
        .map(h => `${h.ccy}-USDT`);
      // 更新持仓币种引用（用于锁定保护）
      holdingSymbols.value = symbols;
      return symbols;
    }
  } catch (e) {
    // 加载持仓失败时返回空数组
  }
  holdingSymbols.value = [];
  return [];
};

// 刷新持仓（更新持仓状态；仅刷新“持仓标记”，不强制把持仓加入监控列表）
const refreshHoldings = async () => {
  loading.value = true;
  try {
    const newHoldings = await loadHoldingSymbols();
    // holdingSymbols.value 已在 loadHoldingSymbols 中更新

    // 将持仓合并到可用列表（确保下拉栏中可选，但不强制加入监控）
    newHoldings.forEach(s => {
      if (!availableSymbols.value.includes(s)) {
        availableSymbols.value.push(s);
      }
    });

    // 如果当前没有任何监控币种（首次使用或用户清空），默认监控持仓
    if (selectedSymbols.value.length === 0 && newHoldings.length > 0) {
      selectedSymbols.value = [...newHoldings];
      await nextTick();
      newHoldings.forEach(s => {
        if (!chartInstances[s]) {
          initChart(s);
          loadChartData(s);
        }
      });
    }
  } catch (e) {
    // 刷新持仓失败时静默处理
  } finally {
    loading.value = false;
  }
};

// 是否已同步过成交记录
let fillsSynced = false;

// 从交易所同步成交记录到本地
const syncFillsFromExchange = async () => {
  if (fillsSynced) return;
  try {
    await api.syncFillsToLocal(tradingMode.value);
    fillsSynced = true;
  } catch (e) {
    // 同步失败不影响主流程
  }
};

// 加载单个币种的成交记录
const loadFillsForSymbol = async (symbol) => {
  try {
    let res = await api.getLocalFills(tradingMode.value, '', symbol, 500);
    // 本地无记录时，先同步再重新加载
    if ((!res.fills || res.fills.length === 0) && !fillsSynced) {
      await syncFillsFromExchange();
      res = await api.getLocalFills(tradingMode.value, '', symbol, 500);
    }
    if (res.fills) {
      fillsData[symbol] = res.fills;
    }
  } catch (e) {
    fillsData[symbol] = [];
  }
};

// 时间周期对应的毫秒数
const TIMEFRAME_MS = {
  '1m': 60 * 1000,
  '3m': 3 * 60 * 1000,
  '5m': 5 * 60 * 1000,
  '15m': 15 * 60 * 1000,
  '30m': 30 * 60 * 1000,
  '1H': 60 * 60 * 1000,
  '2H': 2 * 60 * 60 * 1000,
  '4H': 4 * 60 * 60 * 1000,
  '6H': 6 * 60 * 60 * 1000,
  '12H': 12 * 60 * 60 * 1000,
  '1D': 24 * 60 * 60 * 1000,
  '1W': 7 * 24 * 60 * 60 * 1000,
  '1M': 30 * 24 * 60 * 60 * 1000,
};

// 时间周期
const currentTimeframe = computed({
  get: () => appStore.currentTimeframe,
  set: (val) => appStore.setCurrentTimeframe(val)
});

const timeframes = [
  { value: '1m', label: '1分' },
  { value: '5m', label: '5分' },
  { value: '15m', label: '15分' },
  { value: '1H', label: '1时' },
  { value: '4H', label: '4时' },
  { value: '1D', label: '1天' },
];

// 加载状态
const loading = ref(false);
const syncing = ref(false);
const chartLoading = reactive({});
const chartErrors = reactive({});

// 连接状态
const connectionError = ref(null);

// 自动刷新定时器
let refreshTimer = null;

// 均线指标定义
const maIndicators = [
  { key: 'ma5', label: 'MA5', period: 5, color: '#f6c85d' },
  { key: 'ma10', label: 'MA10', period: 10, color: '#6be6c1' },
  { key: 'ma20', label: 'MA20', period: 20, color: '#3fb1e3' },
  { key: 'ma60', label: 'MA60', period: 60, color: '#a38bf8' },
];

// EMA指标定义
const emaIndicators = [
  { key: 'ema12', label: 'EMA12', period: 12, color: '#ff6b6b' },
  { key: 'ema26', label: 'EMA26', period: 26, color: '#4ecdc4' },
];

// 各币种数据 - 使用 shallowReactive 减少深层响应式追踪开销
const tickers = shallowReactive({});
const candlesData = shallowReactive({});

// 图表实例 - 使用 shallowReactive，图表实例不需要深层响应
const chartRefs = shallowReactive({});
const chartInstances = shallowReactive({});

// 下拉框控制
const showSymbolDropdown = ref(false);
const showTimeframeDropdown = ref(false);
const showIndicatorDropdown = ref(false);
const symbolSearch = ref('');
const symbolDropdown = ref(null);
const timeframeDropdown = ref(null);
const indicatorDropdown = ref(null);

// 过滤后的币种列表
const filteredSymbols = computed(() => {
  if (!symbolSearch.value) return availableSymbols.value;
  const search = symbolSearch.value.toUpperCase();
  return availableSymbols.value.filter(s => s.includes(search));
});

// 当前时间周期标签
const currentTimeframeLabel = computed(() => {
  const tf = timeframes.find(t => t.value === currentTimeframe.value);
  return tf ? tf.label : currentTimeframe.value;
});

// 切换下拉框
const toggleSymbolDropdown = () => {
  showSymbolDropdown.value = !showSymbolDropdown.value;
  showTimeframeDropdown.value = false;
  showIndicatorDropdown.value = false;
};

const toggleTimeframeDropdown = () => {
  showTimeframeDropdown.value = !showTimeframeDropdown.value;
  showSymbolDropdown.value = false;
  showIndicatorDropdown.value = false;
};

// 指标下拉框
const toggleIndicatorDropdown = () => {
  showIndicatorDropdown.value = !showIndicatorDropdown.value;
  showSymbolDropdown.value = false;
  showTimeframeDropdown.value = false;
};

// 已选指标数量
const selectedIndicatorsCount = computed(() => {
  return Object.values(indicators).filter(Boolean).length;
});

// 切换指标开关
const toggleIndicator = (key) => {
  indicators[key] = !indicators[key];
  updateAllCharts();
};

// 清空所有指标
const clearAllIndicators = () => {
  Object.keys(indicators).forEach(key => {
    indicators[key] = false;
  });
  updateAllCharts();
};

// 选择时间周期
const selectTimeframe = (tf) => {
  currentTimeframe.value = tf;
  showTimeframeDropdown.value = false;
  refreshAllCharts();
};

// 全选/清空币种
const selectAllSymbols = () => {
  selectedSymbols.value = [...availableSymbols.value];
  onSymbolsChange();
};

const clearAllSymbols = () => {
  // 只清理非持仓币种的图表资源
  selectedSymbols.value.forEach(symbol => {
    if (holdingSymbols.value.includes(symbol)) return;  // 跳过持仓币种
    if (chartInstances[symbol]) {
      chartInstances[symbol].dispose();
      delete chartInstances[symbol];
    }
    delete chartRefs[symbol];
    delete tickers[symbol];
    delete candlesData[symbol];
    delete chartLoading[symbol];
    delete chartErrors[symbol];
  });
  // 只保留持仓币种
  selectedSymbols.value = [...holdingSymbols.value];
};

// 切换单个币种选中状态
const toggleSymbol = (symbol) => {
  const index = selectedSymbols.value.indexOf(symbol);
  if (index > -1) {
    // 移除：先清理图表资源
    if (chartInstances[symbol]) {
      chartInstances[symbol].dispose();
      delete chartInstances[symbol];
    }
    delete chartRefs[symbol];
    delete tickers[symbol];
    delete candlesData[symbol];
    delete chartLoading[symbol];
    delete chartErrors[symbol];
    selectedSymbols.value.splice(index, 1);
  } else {
    // 添加
    selectedSymbols.value.push(symbol);
    nextTick(() => {
      initChart(symbol);
      loadChartData(symbol);
    });
  }
};

// 判断币种是否为持仓（锁定）
const isHoldingSymbol = (symbol) => {
  return holdingSymbols.value.includes(symbol);
};

// 从列表中彻底删除币种（持仓币种不可删除）
const removeSymbol = (symbol) => {
  if (isHoldingSymbol(symbol)) return;

  // 从可用列表中删除
  const availIdx = availableSymbols.value.indexOf(symbol);
  if (availIdx > -1) {
    availableSymbols.value.splice(availIdx, 1);
  }

  // 从选中列表中删除
  const selectedIdx = selectedSymbols.value.indexOf(symbol);
  if (selectedIdx > -1) {
    // 清理图表资源
    if (chartInstances[symbol]) {
      chartInstances[symbol].dispose();
      delete chartInstances[symbol];
    }
    delete chartRefs[symbol];
    delete tickers[symbol];
    delete candlesData[symbol];
    delete chartLoading[symbol];
    delete chartErrors[symbol];
    delete fillsData[symbol];
    selectedSymbols.value.splice(selectedIdx, 1);
  }
};

// 添加自定义币种
const addCustomSymbol = () => {
  if (!symbolSearch.value.trim()) return;

  let symbol = symbolSearch.value.trim().toUpperCase();
  if (!symbol.includes('-')) {
    symbol = symbol + '-USDT';
  }

  if (!availableSymbols.value.includes(symbol)) {
    availableSymbols.value.push(symbol);
  }

  if (!selectedSymbols.value.includes(symbol)) {
    selectedSymbols.value.push(symbol);
    onSymbolsChange();
  }

  symbolSearch.value = '';
};

// 点击外部关闭下拉框
const handleClickOutside = (e) => {
  if (symbolDropdown.value && !symbolDropdown.value.contains(e.target)) {
    showSymbolDropdown.value = false;
  }
  if (timeframeDropdown.value && !timeframeDropdown.value.contains(e.target)) {
    showTimeframeDropdown.value = false;
  }
  if (indicatorDropdown.value && !indicatorDropdown.value.contains(e.target)) {
    showIndicatorDropdown.value = false;
  }
};

// 设置图表ref
const setChartRef = (symbol, el) => {
  if (el) {
    chartRefs[symbol] = el;
  }
};

// 获取ticker数据
const getTicker = (symbol) => tickers[symbol];

// 获取ticker样式类
const getTickerClass = (symbol) => {
  const t = tickers[symbol];
  if (!t) return '';
  return t.change_24h >= 0 ? 'price-up' : 'price-down';
};

// 格式化函数
const formatPrice = (price) => {
  if (!price) return '-';
  if (price >= 1000) return price.toFixed(2);
  if (price >= 1) return price.toFixed(4);
  return price.toFixed(6);
};

const formatChange = (change) => {
  if (change === null || change === undefined) return '-';
  const sign = change >= 0 ? '+' : '';
  return `${sign}${change.toFixed(2)}%`;
};

const formatVolume = (vol) => {
  if (!vol) return '-';
  if (vol >= 1e9) return (vol / 1e9).toFixed(2) + 'B';
  if (vol >= 1e6) return (vol / 1e6).toFixed(2) + 'M';
  if (vol >= 1e3) return (vol / 1e3).toFixed(2) + 'K';
  return vol.toFixed(2);
};

// 初始化单个图表
const initChart = (symbol) => {
  const el = chartRefs[symbol];
  if (!el) return;

  if (chartInstances[symbol]) {
    chartInstances[symbol].dispose();
  }

  // 使用 useDirtyRect 优化渲染性能（仅重绘变化区域）
  const chart = echarts.init(el, 'dark', {
    renderer: 'canvas',
    useDirtyRect: true,
  });
  chartInstances[symbol] = chart;

  // 设置初始空配置，避免未设置数据时报错
  chart.setOption({
    backgroundColor: 'transparent',
    grid: [
      { left: 50, right: 10, top: 10, bottom: 100 },
      { left: 50, right: 10, height: 35, bottom: 55 },
    ],
    xAxis: [
      { type: 'category', data: [] },
      { type: 'category', gridIndex: 1, data: [] },
    ],
    yAxis: [
      { type: 'value' },
      { type: 'value', gridIndex: 1 },
    ],
    dataZoom: [
      { id: 'inside', type: 'inside', xAxisIndex: [0, 1] },
      {
        id: 'slider',
        type: 'slider',
        xAxisIndex: [0, 1],
        height: 24,
        bottom: 5,
        borderColor: '#30363d',
        backgroundColor: 'rgba(47, 69, 84, 0.3)',
        fillerColor: 'rgba(88, 217, 249, 0.2)',
        handleStyle: { color: '#58D9F9', borderColor: '#58D9F9' },
        textStyle: { color: '#8b949e', fontSize: 10 },
        dataBackground: {
          lineStyle: { color: '#30363d' },
          areaStyle: { color: 'rgba(47, 69, 84, 0.3)' },
        },
      },
    ],
    series: [
      { type: 'candlestick', data: [] },
      { type: 'bar', xAxisIndex: 1, yAxisIndex: 1, data: [] },
    ],
  });

  // 确保图表获取正确尺寸
  setTimeout(() => {
    chart.resize();
  }, 100);
};

// 计算移动平均线
const calculateMA = (data, period) => {
  const result = [];
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) {
      result.push(null);
    } else {
      let sum = 0;
      for (let j = 0; j < period; j++) {
        sum += data[i - j];
      }
      result.push(sum / period);
    }
  }
  return result;
};

// 计算指数移动平均线
const calculateEMA = (data, period) => {
  const result = [];
  const multiplier = 2 / (period + 1);
  let ema = null;
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) {
      result.push(null);
    } else if (i === period - 1) {
      // 首个EMA用SMA初始化
      let sum = 0;
      for (let j = 0; j < period; j++) {
        sum += data[i - j];
      }
      ema = sum / period;
      result.push(ema);
    } else {
      ema = (data[i] - ema) * multiplier + ema;
      result.push(ema);
    }
  }
  return result;
};

// 计算布林带 (period=20, multiplier=2)
const calculateBOLL = (data, period = 20, mult = 2) => {
  const upper = [];
  const middle = [];
  const lower = [];
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) {
      upper.push(null);
      middle.push(null);
      lower.push(null);
    } else {
      let sum = 0;
      for (let j = 0; j < period; j++) {
        sum += data[i - j];
      }
      const ma = sum / period;
      let sqSum = 0;
      for (let j = 0; j < period; j++) {
        sqSum += Math.pow(data[i - j] - ma, 2);
      }
      const std = Math.sqrt(sqSum / period);
      middle.push(ma);
      upper.push(ma + mult * std);
      lower.push(ma - mult * std);
    }
  }
  return { upper, middle, lower };
};

// 计算抛物线SAR
const calculateSAR = (candles, af0 = 0.02, afMax = 0.2, afStep = 0.02) => {
  const result = [];
  if (candles.length < 2) return result;

  let isUpTrend = candles[1].close > candles[0].close;
  let ep = isUpTrend ? candles[0].high : candles[0].low;
  let sar = isUpTrend ? candles[0].low : candles[0].high;
  let af = af0;

  result.push(null); // 第一根无法计算

  for (let i = 1; i < candles.length; i++) {
    const high = candles[i].high;
    const low = candles[i].low;

    // 计算当前SAR
    sar = sar + af * (ep - sar);

    if (isUpTrend) {
      // 确保SAR不高于前两根K线的最低价
      if (i >= 2) {
        sar = Math.min(sar, candles[i - 1].low, candles[i - 2].low);
      } else {
        sar = Math.min(sar, candles[i - 1].low);
      }

      if (low < sar) {
        // 转为下降趋势
        isUpTrend = false;
        sar = ep;
        ep = low;
        af = af0;
      } else {
        if (high > ep) {
          ep = high;
          af = Math.min(af + afStep, afMax);
        }
      }
    } else {
      // 确保SAR不低于前两根K线的最高价
      if (i >= 2) {
        sar = Math.max(sar, candles[i - 1].high, candles[i - 2].high);
      } else {
        sar = Math.max(sar, candles[i - 1].high);
      }

      if (high > sar) {
        // 转为上升趋势
        isUpTrend = true;
        sar = ep;
        ep = high;
        af = af0;
      } else {
        if (low < ep) {
          ep = low;
          af = Math.min(af + afStep, afMax);
        }
      }
    }

    result.push(sar);
  }
  return result;
};

// 更新单个图表
const updateChart = (symbol) => {
  const chart = chartInstances[symbol];
  const candles = candlesData[symbol];

  // 验证数据有效性
  if (!chart || !candles || !Array.isArray(candles) || candles.length === 0) {
    return;
  }

  // 验证数据结构
  const firstCandle = candles[0];
  if (!firstCandle || typeof firstCandle.open !== 'number') {
    console.warn(`${symbol} K线数据格式无效`);
    return;
  }

  try {
    const dates = candles.map(c => {
      const dt = c.datetime
        ? new Date(c.datetime)
        : new Date(c.timestamp);
      const tf = currentTimeframe.value;
      const MM = String(dt.getMonth() + 1).padStart(2, '0');
      const DD = String(dt.getDate()).padStart(2, '0');
      const hh = String(dt.getHours()).padStart(2, '0');
      const mm = String(dt.getMinutes()).padStart(2, '0');
      // 日线及以上只显示日期
      if (tf === '1D' || tf === '1W' || tf === '1M') {
        return `${MM}-${DD}`;
      }
      // 小时线显示日期+时间
      if (tf === '1H' || tf === '4H') {
        return `${MM}-${DD} ${hh}:${mm}`;
      }
      // 分钟线只显示时间
      return `${hh}:${mm}`;
    });
    const ohlc = candles.map(c => [c.open, c.close, c.low, c.high]);
    const closeData = candles.map(c => c.close);
    const volumes = candles.map(c => {
      const color = c.close >= c.open ? '#26a69a' : '#ef5350';
      return { value: c.volume || 0, itemStyle: { color } };
    });

    // 计算均线
    const ma5 = indicators.ma5 ? calculateMA(closeData, 5) : null;
    const ma10 = indicators.ma10 ? calculateMA(closeData, 10) : null;
    const ma20 = indicators.ma20 ? calculateMA(closeData, 20) : null;
    const ma60 = indicators.ma60 ? calculateMA(closeData, 60) : null;

    // 计算EMA
    const ema12 = indicators.ema12 ? calculateEMA(closeData, 12) : null;
    const ema26 = indicators.ema26 ? calculateEMA(closeData, 26) : null;

    // 计算布林带
    const boll = indicators.boll ? calculateBOLL(closeData) : null;

    // 计算SAR
    const sarData = indicators.sar ? calculateSAR(candles) : null;

    // 构建series数组
    const series = [
      {
        name: 'K线',
        type: 'candlestick',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: ohlc,
        itemStyle: {
          color: '#26a69a',
          color0: '#ef5350',
          borderColor: '#26a69a',
          borderColor0: '#ef5350',
        },
      },
    ];

    // 添加MA均线
    const maConfigs = [
      { data: ma5, name: 'MA5', color: '#f6c85d' },
      { data: ma10, name: 'MA10', color: '#6be6c1' },
      { data: ma20, name: 'MA20', color: '#3fb1e3' },
      { data: ma60, name: 'MA60', color: '#a38bf8' },
    ];
    maConfigs.forEach(cfg => {
      if (cfg.data) {
        series.push({
          name: cfg.name,
          type: 'line',
          xAxisIndex: 0,
          yAxisIndex: 0,
          data: cfg.data,
          smooth: true,
          showSymbol: false,
          lineStyle: { width: 1, color: cfg.color },
        });
      }
    });

    // 添加EMA
    const emaConfigs = [
      { data: ema12, name: 'EMA12', color: '#ff6b6b' },
      { data: ema26, name: 'EMA26', color: '#4ecdc4' },
    ];
    emaConfigs.forEach(cfg => {
      if (cfg.data) {
        series.push({
          name: cfg.name,
          type: 'line',
          xAxisIndex: 0,
          yAxisIndex: 0,
          data: cfg.data,
          smooth: true,
          showSymbol: false,
          lineStyle: { width: 1, color: cfg.color },
        });
      }
    });

    // 添加布林带
    if (boll) {
      series.push({
        name: 'BOLL上轨',
        type: 'line',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: boll.upper,
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 1, color: '#ff9800', type: 'dashed' },
      });
      series.push({
        name: 'BOLL中轨',
        type: 'line',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: boll.middle,
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 1, color: '#ff9800' },
      });
      series.push({
        name: 'BOLL下轨',
        type: 'line',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: boll.lower,
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 1, color: '#ff9800', type: 'dashed' },
      });
    }

    // 添加SAR
    if (sarData) {
      series.push({
        name: 'SAR',
        type: 'scatter',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: sarData,
        symbolSize: 4,
        itemStyle: { color: '#e91e63' },
      });
    }

    // 添加买卖标记
    if (showTradeMarkers.value && fillsData[symbol] && fillsData[symbol].length > 0) {
      const fills = fillsData[symbol];
      const buyMarkers = [];
      const sellMarkers = [];
      const duration = TIMEFRAME_MS[currentTimeframe.value] || 60 * 60 * 1000;

      // 将成交记录映射到K线时间轴（使用二分查找优化性能）
      fills.forEach(fill => {
        const fillTime = parseInt(fill.ts);
        // 使用二分查找找到对应的K线索引（O(log n) 复杂度）
        const idx = binarySearchCandleIndex(candles, fillTime, duration);

        if (idx >= 0) {
          const price = parseFloat(fill.fill_px);
          if (fill.side === 'buy') {
            buyMarkers.push([idx, price]);
          } else {
            sellMarkers.push([idx, price]);
          }
        }
      });

      // 买入标记 (绿色向上三角)
      if (buyMarkers.length > 0) {
        series.push({
          name: '买入',
          type: 'scatter',
          xAxisIndex: 0,
          yAxisIndex: 0,
          data: buyMarkers,
          symbolSize: 14,
          symbol: 'triangle',
          symbolRotate: 0,
          itemStyle: { color: '#26a69a' },
          label: {
            show: true,
            position: 'bottom',
            formatter: 'B',
            fontSize: 10,
            fontWeight: 'bold',
            color: '#26a69a'
          },
          z: 10,
        });
      }

      // 卖出标记 (红色向下三角)
      if (sellMarkers.length > 0) {
        series.push({
          name: '卖出',
          type: 'scatter',
          xAxisIndex: 0,
          yAxisIndex: 0,
          data: sellMarkers,
          symbolSize: 14,
          symbol: 'triangle',
          symbolRotate: 180,
          itemStyle: { color: '#ef5350' },
          label: {
            show: true,
            position: 'top',
            formatter: 'S',
            fontSize: 10,
            fontWeight: 'bold',
            color: '#ef5350'
          },
          z: 10,
        });
      }
    }

    // 成交量
    series.push({
      name: '成交量',
      type: 'bar',
      xAxisIndex: 1,
      yAxisIndex: 1,
      data: volumes,
    });

  const option = {
    backgroundColor: 'transparent',
    animation: false,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      backgroundColor: 'rgba(22, 27, 34, 0.9)',
      borderColor: '#30363d',
      textStyle: { color: '#e6edf3', fontSize: 10 },
      confine: true,
    },
    grid: [
      { left: 50, right: 10, top: 10, bottom: 100 },
      { left: 50, right: 10, height: 35, bottom: 55 },
    ],
    xAxis: [
      {
        type: 'category',
        data: dates,
        axisLine: { lineStyle: { color: '#30363d' } },
        axisLabel: { color: '#8b949e', fontSize: 9 },
        splitLine: { show: false },
      },
      {
        type: 'category',
        gridIndex: 1,
        data: dates,
        axisLine: { lineStyle: { color: '#30363d' } },
        axisLabel: { show: false },
        splitLine: { show: false },
      },
    ],
    yAxis: [
      {
        scale: true,
        axisLine: { lineStyle: { color: '#30363d' } },
        axisLabel: { color: '#8b949e', fontSize: 9 },
        splitLine: { lineStyle: { color: '#21262d' } },
      },
      {
        scale: true,
        gridIndex: 1,
        axisLine: { lineStyle: { color: '#30363d' } },
        axisLabel: { show: false },
        splitLine: { show: false },
      },
    ],
    series: series,
  };

  // 不重新设置dataZoom，保持其状态
  chart.setOption(option);
  } catch (error) {
    console.error(`更新 ${symbol} 图表失败:`, error);
    chartErrors[symbol] = '图表渲染失败';
  }
};

// 加载单个币种数据
const loadChartData = async (symbol) => {
  chartLoading[symbol] = true;
  chartErrors[symbol] = null;

  try {
    // 并行获取数据
    const tasks = [];

    // 获取 ticker
    tasks.push(
      api.getTicker(symbol)
        .then(res => {
          if (res.code === 0) {
            tickers[symbol] = res.data;
          }
        })
        .catch(e => console.warn(`获取 ${symbol} ticker 失败:`, e.message))
    );

    // 获取成交记录（用于买卖标记）
    if (showTradeMarkers.value) {
      tasks.push(loadFillsForSymbol(symbol));
    }

    // 获取 K线数据
    const candlesTask = (async () => {
      // 先尝试从本地获取
      let candlesRes = await api.getCandles(symbol, {
        timeframe: currentTimeframe.value,
        limit: 300,
        source: 'local',
      });

      // 本地数据不足时，从交易所获取
      if (!candlesRes.data || candlesRes.data.length < 10) {
        candlesRes = await api.getCandles(symbol, {
          timeframe: currentTimeframe.value,
          limit: 300,
          source: 'exchange',
        });
      }

      if (candlesRes.code === 0 && candlesRes.data && candlesRes.data.length > 0) {
        candlesData[symbol] = candlesRes.data;
      } else {
        chartErrors[symbol] = '暂无K线数据，请先同步数据';
      }
    })();
    tasks.push(candlesTask);

    // 等待所有任务完成
    await Promise.all(tasks);

    // 更新图表
    if (candlesData[symbol] && candlesData[symbol].length > 0) {
      await nextTick();
      updateChart(symbol);
    }
  } catch (error) {
    console.error(`加载 ${symbol} 数据失败:`, error);
    chartErrors[symbol] = '数据加载失败';
  } finally {
    chartLoading[symbol] = false;
  }
};

// 更新所有图表（仅重绘，不重新加载数据）
const updateAllCharts = () => {
  selectedSymbols.value.forEach(symbol => {
    if (candlesData[symbol]) {
      updateChart(symbol);
    }
  });
};

// 刷新单个图表（重新加载数据）
const refreshChart = (symbol) => {
  loadChartData(symbol);
};

// 刷新所有图表
const refreshAllCharts = async () => {
  loading.value = true;
  try {
    await Promise.all(selectedSymbols.value.map(symbol => loadChartData(symbol)));
  } finally {
    loading.value = false;
  }
};

// 只刷新ticker数据（轻量级）
const refreshAllTickers = async () => {
  await Promise.all(
    selectedSymbols.value.map(async (symbol) => {
      try {
        const res = await api.getTicker(symbol);
        if (res.code === 0) {
          tickers[symbol] = res.data;
        }
      } catch (e) {
        // 静默处理：某些币种可能不存在交易对
      }
    })
  );
};

// 同步所有数据
const syncAllData = async () => {
  syncing.value = true;
  try {
    await Promise.all(
      selectedSymbols.value.map(symbol =>
        api.syncCandles(symbol, { timeframe: currentTimeframe.value, days: 30 })
      )
    );
    await refreshAllCharts();
  } catch (error) {
    console.error('同步数据失败:', error);
  } finally {
    syncing.value = false;
  }
};

// 币种选择变化
const onSymbolsChange = () => {
  nextTick(() => {
    initAllCharts();
    refreshAllCharts();
  });
};

// 初始化所有图表
const initAllCharts = () => {
  selectedSymbols.value.forEach(symbol => {
    initChart(symbol);
  });
};

// 自动刷新控制
const startAutoRefresh = () => {
  stopAutoRefresh();
  if (autoRefresh.value && refreshInterval.value > 0) {
    refreshTimer = setInterval(() => {
      refreshAllTickers();
    }, refreshInterval.value * 1000);
  }
};

const stopAutoRefresh = () => {
  if (refreshTimer) {
    clearInterval(refreshTimer);
    refreshTimer = null;
  }
};

const toggleAutoRefresh = () => {
  if (autoRefresh.value) {
    startAutoRefresh();
  } else {
    stopAutoRefresh();
  }
};

const restartAutoRefresh = () => {
  if (autoRefresh.value) {
    startAutoRefresh();
  }
};

// 窗口大小变化时调整图表
// 图表 resize 处理（内部实现）
const doResize = () => {
  Object.values(chartInstances).forEach(chart => {
    chart?.resize();
  });
};

// 节流后的 resize 处理函数（每 100ms 最多执行一次）
const handleResize = throttle(doResize, 100);

// 检查后端连接
const checkConnection = async () => {
  try {
    const res = await api.healthCheck();
    if (res.status === 'healthy') {
      connectionError.value = null;

      // 如果尚未初始化（首次连接失败导致中断），执行完整初始化
      if (!isInitialized) {
        await loadSettings();

        // 加载实盘持仓（仅用于锁定/快捷引用，不强制加入监控）
        const holdings = await loadHoldingSymbols();
        holdings.forEach(s => {
          if (!availableSymbols.value.includes(s)) {
            availableSymbols.value.push(s);
          }
        });

        // 如果没有任何监控币种（首次使用或设置为空），默认监控持仓
        if (selectedSymbols.value.length === 0 && holdings.length > 0) {
          selectedSymbols.value = [...holdings];
        }

        await loadAvailableSymbols();
        await nextTick();
        initAllCharts();
        refreshAllCharts();
        startAutoRefresh();
        window.addEventListener('resize', handleResize);
        document.addEventListener('click', handleClickOutside);
        isInitialized = true;
      } else {
        refreshAllCharts();
      }
    }
  } catch (error) {
    connectionError.value = '无法连接到后端服务，请确保后端已启动';
  }
};

// 加载可用币种
const loadAvailableSymbols = async () => {
  try {
    const res = await api.getAvailableSymbols();
    if (res.code === 0 && res.data && res.data.length > 0) {
      const symbols = res.data.map(item => item.inst_id || item);
      // 合并到可用列表，去重
      const merged = [...new Set([...availableSymbols.value, ...symbols])];
      availableSymbols.value = merged;
    }
  } catch (e) {
    console.error('获取可用币种失败:', e);
  }
};

// ========== 设置变更监听（自动保存） ==========
// 监听选中的币种变化
watch(selectedSymbols, () => {
  if (settingsLoaded.value) debouncedSave();
}, { deep: true });

// 监听可用币种变化（用户添加自定义币种时）
watch(availableSymbols, () => {
  if (settingsLoaded.value) debouncedSave();
}, { deep: true });

// 监听自动刷新设置
watch([autoRefresh, refreshInterval], () => {
  if (settingsLoaded.value) debouncedSave();
});

// 监听指标设置变化
watch(indicators, () => {
  if (settingsLoaded.value) debouncedSave();
}, { deep: true });

// 是否已初始化
let isInitialized = false

// 生命周期
onMounted(async () => {
  // 等待后端服务启动（最多重试 10 次，每次间隔 1 秒）
  const connected = await waitForBackend(10, 1000);
  if (!connected) {
    connectionError.value = '无法连接到后端服务，请确保后端已启动 (http://127.0.0.1:8000)';
    return; // 连接失败，中断初始化
  }

  connectionError.value = null;

  // 从后端加载用户设置
  await loadSettings();

  // 行情监控只展示实盘持仓，不跟随默认模式切换（避免模拟盘虚拟资产干扰）

  // 加载持仓币种
  const holdings = await loadHoldingSymbols();

  // 合并持仓到可用列表（确保下拉栏中可选，但不强制监控）
  holdings.forEach(s => {
    if (!availableSymbols.value.includes(s)) {
      availableSymbols.value.push(s);
    }
  });

  // 如果没有任何监控币种（首次使用或设置为空），默认监控持仓
  if (selectedSymbols.value.length === 0 && holdings.length > 0) {
    selectedSymbols.value = [...holdings];
  }

  await loadAvailableSymbols();
  await nextTick();
  initAllCharts();
  refreshAllCharts();
  startAutoRefresh();
  window.addEventListener('resize', handleResize);
  document.addEventListener('click', handleClickOutside);

  isInitialized = true
});

// keep-alive 激活时调用
onActivated(() => {
  if (!isInitialized) return

  // 重新添加事件监听
  window.addEventListener('resize', handleResize);
  document.addEventListener('click', handleClickOutside);

  // 重新启动自动刷新
  startAutoRefresh();

  // 图表 resize（可能容器大小变化了）
  nextTick(() => {
    Object.values(chartInstances).forEach(chart => {
      chart?.resize();
    });
  });

  // 后台静默刷新最新数据
  refreshAllCharts();
});

// keep-alive 停用时调用
onDeactivated(() => {
  // 停止自动刷新（节省资源）
  stopAutoRefresh();

  // 移除事件监听
  window.removeEventListener('resize', handleResize);
  document.removeEventListener('click', handleClickOutside);
});

onUnmounted(() => {
  stopAutoRefresh();
  if (saveTimer) clearTimeout(saveTimer);
  window.removeEventListener('resize', handleResize);
  document.removeEventListener('click', handleClickOutside);
  Object.values(chartInstances).forEach(chart => {
    chart?.dispose();
  });
});
</script>

<style scoped>
.market-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  gap: 12px;
}

.connection-error {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  background-color: rgba(255, 77, 79, 0.1);
  border: 1px solid rgba(255, 77, 79, 0.3);
  border-radius: 6px;
  color: #ff4d4f;
  font-size: 13px;
}

.error-badge {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background-color: #ff4d4f;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: bold;
}

.btn-link {
  background: none;
  border: none;
  color: var(--accent-color);
  cursor: pointer;
  font-size: 13px;
  padding: 0;
  margin-left: auto;
}

.btn-link:hover {
  text-decoration: underline;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background-color: var(--bg-secondary);
  border-radius: 8px;
  flex-wrap: wrap;
  gap: 12px;
}

.toolbar-left,
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

/* 下拉选择框 */
.dropdown-select {
  position: relative;
}

.dropdown-trigger {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  cursor: pointer;
  transition: border-color 0.2s ease, background-color 0.2s ease;
  font-size: 12px;
  user-select: none;
}

.dropdown-trigger:hover {
  border-color: var(--accent-color);
}

.dropdown-trigger .label {
  color: var(--text-secondary);
  white-space: nowrap;
}

.dropdown-value {
  color: var(--text-primary);
  font-weight: 500;
}

.dropdown-arrow {
  color: var(--text-secondary);
  font-size: 8px;
  transition: transform 0.2s;
}

.dropdown-arrow.open {
  transform: rotate(180deg);
}

.dropdown-menu {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  min-width: 200px;
  max-height: 320px;
  background-color: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  z-index: 100;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.dropdown-menu-sm {
  min-width: 120px;
  max-height: none;
}

.dropdown-menu-indicator {
  min-width: 220px;
}

.indicator-group {
  padding: 4px 0;
}

.indicator-group + .indicator-group {
  border-top: 1px solid var(--border-color);
}

.group-header {
  padding: 6px 12px 4px;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.indicator-color {
  display: inline-block;
  width: 16px;
  height: 3px;
  border-radius: 1.5px;
  flex-shrink: 0;
}

.dropdown-search {
  display: flex;
  gap: 8px;
  align-items: center;
  padding: 8px;
  border-bottom: 1px solid var(--border-color);
}

.dropdown-search input {
  flex: 1;
  padding: 6px 8px;
  border: 1px solid var(--border-color);
  border-radius: 4px;
  background-color: var(--bg-tertiary);
  color: var(--text-primary);
  font-size: 12px;
  outline: none;
}

.dropdown-search input:focus {
  border-color: var(--accent-color);
}

.dropdown-options {
  overflow-y: auto;
  max-height: 230px;
  padding: 4px 0;
}

.dropdown-options::-webkit-scrollbar {
  width: 6px;
}

.dropdown-options::-webkit-scrollbar-track {
  background: transparent;
}

.dropdown-options::-webkit-scrollbar-thumb {
  background: var(--border-color);
  border-radius: 3px;
}

.dropdown-options::-webkit-scrollbar-thumb:hover {
  background: #555;
}

.dropdown-option {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  cursor: pointer;
  font-size: 12px;
  color: var(--text-primary);
  transition: background-color 0.15s;
}

.dropdown-option:hover {
  background-color: var(--bg-hover);
}

.dropdown-option.selected {
  color: var(--accent-color);
}

.checkbox-mark {
  width: 14px;
  height: 14px;
  border: 1.5px solid var(--border-color);
  border-radius: 3px;
  flex-shrink: 0;
  position: relative;
  transition: border-color 0.15s ease, background-color 0.15s ease;
}

.dropdown-option.selected .checkbox-mark {
  background-color: var(--accent-color);
  border-color: var(--accent-color);
}

.dropdown-option.selected .checkbox-mark::after {
  content: '';
  position: absolute;
  left: 3.5px;
  top: 1px;
  width: 4px;
  height: 7px;
  border: solid white;
  border-width: 0 1.5px 1.5px 0;
  transform: rotate(45deg);
}

/* 宽版下拉（币种选择） */
.dropdown-select-wide .dropdown-trigger {
  min-width: 180px;
}

.dropdown-menu-symbols {
  min-width: 280px;
  max-height: 400px;
}

.dropdown-search .btn-add {
  padding: 6px 12px;
  background: var(--accent-color);
  color: white;
  border: none;
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
  white-space: nowrap;
}

.dropdown-search .btn-add:hover {
  background: var(--accent-hover);
}

.symbol-options {
  max-height: 280px;
}

.symbol-options .dropdown-option {
  justify-content: space-between;
}

.symbol-options .option-label {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.btn-remove {
  width: 20px;
  height: 20px;
  padding: 0;
  border: none;
  background: transparent;
  color: var(--text-tertiary);
  font-size: 12px;
  cursor: pointer;
  border-radius: 3px;
  opacity: 0;
  transition: border-color 0.15s ease, background-color 0.15s ease;
}

.dropdown-option:hover .btn-remove {
  opacity: 1;
}

.btn-remove:hover {
  background: #ef5350;
  color: white;
}

.holding-badge {
  font-size: 10px;
  color: var(--text-tertiary);
  margin-left: 4px;
}

/* 锁定状态（持仓币种） */
.dropdown-option.locked {
  background-color: rgba(100, 181, 246, 0.08);
}

.dropdown-option.locked .checkbox-mark.disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.lock-icon {
  margin-left: auto;
  font-size: 10px;
  color: var(--accent-color);
  font-weight: bold;
}

.radio-mark {
  width: 14px;
  height: 14px;
  border: 1.5px solid var(--border-color);
  border-radius: 50%;
  flex-shrink: 0;
  position: relative;
  transition: border-color 0.15s ease, background-color 0.15s ease;
}

.dropdown-option.selected .radio-mark {
  border-color: var(--accent-color);
}

.dropdown-option.selected .radio-mark::after {
  content: '';
  position: absolute;
  left: 3px;
  top: 3px;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background-color: var(--accent-color);
}

.dropdown-actions {
  display: flex;
  gap: 8px;
  padding: 8px 12px;
  border-top: 1px solid var(--border-color);
}

.dropdown-empty {
  padding: 12px;
  text-align: center;
  font-size: 12px;
  color: var(--text-secondary);
}

.btn-text {
  background: none;
  border: none;
  color: var(--accent-color);
  cursor: pointer;
  font-size: 12px;
  padding: 2px 4px;
}

.btn-text:hover {
  text-decoration: underline;
}

.select-small {
  padding: 4px 8px;
  font-size: 12px;
  border: 1px solid var(--border-color);
  border-radius: 4px;
  background-color: var(--bg-tertiary);
  color: var(--text-primary);
  cursor: pointer;
}

/* 自动刷新 */
.auto-refresh-control {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-right: 12px;
  border-right: 1px solid var(--border-color);
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--text-secondary);
  cursor: pointer;
}

/* 图表列表 - 添加 contain 优化滚动性能 */
.charts-list {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow-y: auto;
  padding: 4px;
  padding-right: 8px;
  contain: layout style;
}

.chart-card {
  background-color: var(--bg-secondary);
  border-radius: 8px;
  border: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  min-height: 400px;
  flex-shrink: 0;
  width: 100%;
  contain: layout paint;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  border-bottom: 1px solid var(--border-color);
}

.symbol-info {
  display: flex;
  align-items: center;
  gap: 10px;
}

.symbol-name {
  font-weight: 600;
  font-size: 14px;
}

.symbol-price {
  font-family: var(--font-mono);
  font-size: 16px;
  font-weight: 600;
}

.symbol-change {
  font-size: 12px;
  font-weight: 500;
}

.chart-actions {
  display: flex;
  gap: 4px;
}

.btn-icon {
  width: 24px;
  height: 24px;
  border: none;
  border-radius: 4px;
  background-color: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
}

.btn-icon:hover {
  background-color: var(--bg-hover);
  color: var(--text-primary);
}

.btn-remove:hover {
  background-color: rgba(255, 77, 79, 0.2);
  color: #ff4d4f;
}

.chart-wrapper {
  flex: 1;
  position: relative;
  min-height: 300px;
  overflow: visible;
}

.chart {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  width: 100%;
  height: 100%;
}

.chart-loading {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: rgba(13, 17, 23, 0.6);
}

.chart-error {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  background-color: rgba(13, 17, 23, 0.8);
}

.error-icon {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background-color: rgba(255, 77, 79, 0.2);
  color: #ff4d4f;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  font-size: 18px;
}

.error-text {
  color: var(--text-secondary);
  font-size: 12px;
  text-align: center;
  max-width: 80%;
}

.btn-sm {
  padding: 4px 12px;
  font-size: 11px;
}

.chart-footer {
  display: flex;
  justify-content: space-around;
  padding: 8px 12px;
  border-top: 1px solid var(--border-color);
  font-size: 11px;
  color: var(--text-secondary);
}

/* 空状态 */
.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
}

.empty-text {
  color: var(--text-secondary);
  font-size: 14px;
}

.empty-hint {
  color: var(--text-tertiary);
  font-size: 12px;
  text-align: center;
  max-width: 300px;
}

/* 价格颜色 */
.price-up {
  color: #26a69a;
}

.price-down {
  color: #ef5350;
}

/* 加载动画 - 使用 will-change 提示 GPU 加速 */
.spinner {
  width: 24px;
  height: 24px;
  border: 2px solid var(--border-color);
  border-top-color: var(--accent-color);
  border-radius: 50%;
  animation: spin 1s linear infinite;
  will-change: transform;
}

.spinner-small {
  display: inline-block;
  width: 12px;
  height: 12px;
  border: 2px solid var(--border-color);
  border-top-color: var(--accent-color);
  border-radius: 50%;
  animation: spin 1s linear infinite;
  will-change: transform;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* 滚动条样式 */
.charts-list::-webkit-scrollbar {
  width: 8px;
}

.charts-list::-webkit-scrollbar-track {
  background: var(--bg-tertiary);
  border-radius: 4px;
}

.charts-list::-webkit-scrollbar-thumb {
  background: var(--border-color);
  border-radius: 4px;
}

.charts-list::-webkit-scrollbar-thumb:hover {
  background: #555;
}
</style>
