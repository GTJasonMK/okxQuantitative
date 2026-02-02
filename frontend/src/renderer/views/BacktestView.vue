<template>
  <div class="backtest-view">
    <div class="page-header">
      <h1>策略回测</h1>
      <p>使用历史数据验证交易策略的表现</p>
    </div>

    <div class="backtest-layout">
      <!-- 左侧：配置面板 -->
      <div class="config-panel card">
        <h3 class="card-title">回测配置</h3>

        <div class="form-group">
          <label>交易对</label>
          <select v-model="config.symbol" class="select" :disabled="loadingSymbols">
            <option v-if="loadingSymbols" value="">加载中...</option>
            <option v-else-if="symbols.length === 0" value="">无可用交易对</option>
            <option v-for="s in symbols" :key="s" :value="s">{{ s }}</option>
          </select>
        </div>

        <div class="form-group">
          <label>时间周期</label>
          <select v-model="config.timeframe" class="select">
            <option value="15m">15分钟</option>
            <option value="30m">30分钟</option>
            <option value="1H">1小时</option>
            <option value="2H">2小时</option>
            <option value="4H">4小时</option>
            <option value="6H">6小时</option>
            <option value="12H">12小时</option>
            <option value="1D">1天</option>
          </select>
        </div>

        <div class="form-group">
          <label>策略</label>
          <select v-model="config.strategy" class="select" :disabled="loadingStrategies">
            <option v-if="loadingStrategies" value="">加载中...</option>
            <option v-else-if="strategies.length === 0" value="">无可用策略</option>
            <option v-for="s in strategies" :key="s.id" :value="s.id">{{ s.name }}</option>
          </select>
        </div>

        <div class="form-group">
          <label>初始资金 (USDT)</label>
          <input type="number" v-model.number="config.capital" class="input" />
        </div>

        <div class="form-group">
          <label>回测天数</label>
          <input type="number" v-model.number="config.days" class="input" min="1" max="365" />
        </div>

        <!-- 通用参数 -->
        <div class="form-group">
          <label>仓位比例</label>
          <input type="number" v-model.number="config.positionSize" class="input" min="0.1" max="1" step="0.1" />
        </div>

        <div class="form-group">
          <label>止损比例</label>
          <input type="number" v-model.number="config.stopLoss" class="input" min="0" max="0.5" step="0.01" />
        </div>

        <div class="form-group">
          <label>止盈比例</label>
          <input type="number" v-model.number="config.takeProfit" class="input" min="0" max="1" step="0.01" />
        </div>

        <!-- 动态策略参数 -->
        <template v-if="currentStrategyParams.length > 0">
          <div class="strategy-params">
            <h4>策略参数</h4>
            <div v-for="param in currentStrategyParams" :key="param.name" class="form-group">
              <label>{{ param.label || param.name }}</label>

              <!-- 布尔类型 -->
              <template v-if="param.type === 'bool'">
                <label class="checkbox-label">
                  <input type="checkbox" v-model="strategyParams[param.name]" />
                  {{ param.label || param.name }}
                </label>
              </template>

              <!-- 选择类型 -->
              <template v-else-if="param.type === 'select' || param.options">
                <select v-model="strategyParams[param.name]" class="select">
                  <option v-for="opt in param.options" :key="opt" :value="opt">
                    {{ opt === 'arithmetic' ? '等差网格' : opt === 'geometric' ? '等比网格' : opt }}
                  </option>
                </select>
              </template>

              <!-- 数字类型 -->
              <template v-else-if="param.type === 'int' || param.type === 'float'">
                <input
                  type="number"
                  v-model.number="strategyParams[param.name]"
                  class="input"
                  :min="param.min"
                  :max="param.max"
                  :step="param.type === 'float' ? 0.01 : 1"
                />
              </template>

              <!-- 默认文本 -->
              <template v-else>
                <input type="text" v-model="strategyParams[param.name]" class="input" />
              </template>
            </div>
          </div>
        </template>

        <button class="btn btn-primary btn-block" @click="runBacktest" :disabled="running || loadingSymbols || loadingStrategies">
          {{ running ? '回测中...' : (loadingSymbols || loadingStrategies) ? '加载中...' : '开始回测' }}
        </button>

        <div v-if="error" class="error-message">{{ error }}</div>
      </div>

      <!-- 右侧：结果展示 -->
      <div class="result-panel">
        <template v-if="result.strategyName">
        <!-- 回测概览 -->
        <div class="overview-card card">
          <h3 class="card-title">回测概览</h3>
          <div class="overview-grid">
            <div class="overview-item">
              <span class="label">策略名称</span>
              <span class="value">{{ result.strategyName }}</span>
            </div>
            <div class="overview-item">
              <span class="label">交易对</span>
              <span class="value">{{ result.symbol }}</span>
            </div>
            <div class="overview-item">
              <span class="label">时间周期</span>
              <span class="value">{{ result.timeframe }}</span>
            </div>
            <div class="overview-item">
              <span class="label">回测周期</span>
              <span class="value">{{ result.durationDays }} 根K线</span>
            </div>
            <div class="overview-item">
              <span class="label">开始时间</span>
              <span class="value">{{ formatDateTime(result.startTime) }}</span>
            </div>
            <div class="overview-item">
              <span class="label">结束时间</span>
              <span class="value">{{ formatDateTime(result.endTime) }}</span>
            </div>
          </div>
        </div>

        <!-- 收益指标 -->
        <div class="section-title">收益指标</div>
        <div class="stats-grid">
          <div class="stat-card">
            <div class="stat-label">初始资金</div>
            <div class="stat-value">{{ formatMoney(result.initialCapital) }}</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">最终资金</div>
            <div class="stat-value" :class="result.finalCapital >= result.initialCapital ? 'price-up' : 'price-down'">
              {{ formatMoney(result.finalCapital) }}
            </div>
          </div>
          <div class="stat-card">
            <div class="stat-label">总收益率</div>
            <div class="stat-value" :class="result.totalReturn >= 0 ? 'price-up' : 'price-down'">
              {{ formatPercent(result.totalReturn) }}
            </div>
          </div>
          <div class="stat-card">
            <div class="stat-label">年化收益率</div>
            <div class="stat-value" :class="result.annualReturn >= 0 ? 'price-up' : 'price-down'">
              {{ formatPercent(result.annualReturn) }}
            </div>
          </div>
        </div>

        <!-- 风险指标 -->
        <div class="section-title">风险指标</div>
        <div class="stats-grid">
          <div class="stat-card">
            <div class="stat-label">最大回撤</div>
            <div class="stat-value price-down">{{ formatPercent(result.maxDrawdown) }}</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">夏普比率</div>
            <div class="stat-value" :class="result.sharpeRatio >= 1 ? 'price-up' : ''">
              {{ formatRatio(result.sharpeRatio) }}
            </div>
          </div>
          <div class="stat-card">
            <div class="stat-label">索提诺比率</div>
            <div class="stat-value" :class="result.sortinoRatio >= 1 ? 'price-up' : ''">
              {{ formatRatio(result.sortinoRatio) }}
            </div>
          </div>
          <div class="stat-card">
            <div class="stat-label">卡尔玛比率</div>
            <div class="stat-value" :class="result.calmarRatio >= 1 ? 'price-up' : ''">
              {{ formatRatio(result.calmarRatio) }}
            </div>
          </div>
        </div>

        <!-- 交易统计 -->
        <div class="section-title">交易统计</div>
        <div class="stats-grid">
          <div class="stat-card">
            <div class="stat-label">总交易次数</div>
            <div class="stat-value">{{ result.totalTrades }}</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">盈利次数</div>
            <div class="stat-value price-up">{{ result.winningTrades }}</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">亏损次数</div>
            <div class="stat-value price-down">{{ result.losingTrades }}</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">胜率</div>
            <div class="stat-value" :class="result.winRate >= 50 ? 'price-up' : 'price-down'">
              {{ formatPercent(result.winRate) }}
            </div>
          </div>
          <div class="stat-card">
            <div class="stat-label">盈亏比</div>
            <div class="stat-value" :class="result.profitFactor >= 1 ? 'price-up' : 'price-down'">
              {{ formatRatio(result.profitFactor) }}
            </div>
          </div>
          <div class="stat-card">
            <div class="stat-label">总手续费</div>
            <div class="stat-value">{{ formatMoney(result.totalCommission) }}</div>
          </div>
        </div>

        <!-- 盈亏详情 -->
        <div class="section-title">盈亏详情</div>
        <div class="stats-grid">
          <div class="stat-card">
            <div class="stat-label">平均盈利</div>
            <div class="stat-value price-up">{{ formatMoney(result.avgProfit) }}</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">平均亏损</div>
            <div class="stat-value price-down">{{ formatMoney(result.avgLoss) }}</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">最大单笔盈利</div>
            <div class="stat-value price-up">{{ formatMoney(result.largestProfit) }}</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">最大单笔亏损</div>
            <div class="stat-value price-down">{{ formatMoney(result.largestLoss) }}</div>
          </div>
        </div>

        <!-- 收益曲线 -->
        <div class="chart-card card">
          <h3 class="card-title">收益曲线</h3>
          <div ref="equityChartRef" class="equity-chart"></div>
        </div>

        <!-- 交易记录 -->
        <div class="trades-card card" v-if="trades.length > 0">
          <h3 class="card-title">交易记录 (共{{ trades.length }}条，显示最近20条)</h3>
          <div class="trades-table-wrapper">
            <table class="trades-table">
              <thead>
                <tr>
                  <th>时间</th>
                  <th>方向</th>
                  <th>价格</th>
                  <th>数量</th>
                  <th>金额</th>
                  <th>手续费</th>
                  <th>盈亏</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(trade, index) in trades.slice(-20)" :key="index">
                  <td>{{ formatTime(trade.timestamp) }}</td>
                  <td :class="trade.side === 'buy' ? 'price-up' : 'price-down'">
                    {{ trade.side === 'buy' ? '买入' : '卖出' }}
                  </td>
                  <td>{{ formatPrice(trade.price) }}</td>
                  <td>{{ safeNum(trade.quantity).toFixed(6) }}</td>
                  <td>{{ formatMoney(trade.value) }}</td>
                  <td>{{ formatMoney(trade.commission) }}</td>
                  <td :class="(trade.pnl || 0) >= 0 ? 'price-up' : 'price-down'">
                    {{ trade.pnl ? formatMoney(trade.pnl) : '-' }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
        </template>

        <!-- 空状态提示 -->
        <div v-if="!result.strategyName" class="empty-result">
          <div class="empty-icon">{ }</div>
          <div class="empty-text">配置参数后点击"开始回测"查看结果</div>
        </div>

        <!-- 回测历史列表 -->
        <div class="history-section card">
          <div class="history-header" @click="showHistory = !showHistory">
            <h3 class="card-title">回测历史</h3>
            <span class="toggle-icon">{{ showHistory ? '-' : '+' }}</span>
          </div>
          <div v-if="showHistory" class="history-content">
            <div v-if="loadingHistory" class="history-loading">加载中...</div>
            <div v-else-if="backtestHistory.length === 0" class="history-empty">暂无回测记录</div>
            <div v-else class="history-list">
              <div
                v-for="item in backtestHistory"
                :key="item.id"
                class="history-item"
              >
                <div class="history-info" @click="viewHistoryDetail(item)">
                  <div class="history-main">
                    <span class="history-strategy">{{ item.strategy_name }}</span>
                    <span class="history-symbol">{{ item.symbol }}</span>
                    <span class="history-timeframe">{{ item.timeframe }}</span>
                  </div>
                  <div class="history-stats">
                    <span :class="item.total_return >= 0 ? 'price-up' : 'price-down'">
                      {{ formatPercent(item.total_return) }}
                    </span>
                    <span class="history-trades">{{ item.total_trades }}笔</span>
                    <span class="history-time">{{ formatDateTime(item.created_at) }}</span>
                  </div>
                </div>
                <button class="btn-delete" @click.stop="deleteHistoryItem(item.id)" title="删除">x</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, onActivated, onDeactivated, watch, nextTick } from 'vue';
import * as echarts from 'echarts';
import { api } from '../services/api';

// 定义组件名称，用于 keep-alive 缓存
defineOptions({
  name: 'BacktestView'
})

// 基础配置
const config = reactive({
  symbol: 'BTC-USDT',
  timeframe: '1H',
  strategy: 'dual_ma',
  capital: 10000,
  days: 30,
  positionSize: 0.5,
  stopLoss: 0.05,
  takeProfit: 0.10,
});

// 动态策略参数
const strategyParams = reactive({});

// 策略列表（从API获取）
const strategies = ref([]);
const loadingStrategies = ref(false);

// 当前策略的参数定义
const currentStrategyParams = computed(() => {
  const strategy = strategies.value.find(s => s.id === config.strategy);
  return strategy?.params || [];
});

// 初始化策略参数默认值（需要在 watch 之前定义）
const initStrategyParams = () => {
  const params = currentStrategyParams.value;
  // 收集当前策略需要的参数名
  const validNames = new Set(params.map(p => p.name));
  // 删除不属于当前策略的旧参数
  Object.keys(strategyParams).forEach(key => {
    if (!validNames.has(key)) {
      delete strategyParams[key];
    }
  });
  // 设置当前策略参数的默认值
  params.forEach(param => {
    if (!(param.name in strategyParams)) {
      strategyParams[param.name] = param.default;
    }
  });
};

// 监听策略变化，初始化参数默认值
watch(() => config.strategy, () => {
  initStrategyParams();
}, { immediate: true });

// 监听策略列表加载完成
watch(strategies, () => {
  initStrategyParams();
});

// 结果
const result = reactive({
  strategyName: '',
  symbol: '',
  timeframe: '',
  startTime: '',
  endTime: '',
  durationDays: 0,
  initialCapital: 0,
  finalCapital: 0,
  totalReturn: 0,
  annualReturn: 0,
  maxDrawdown: 0,
  sharpeRatio: 0,
  sortinoRatio: 0,
  calmarRatio: 0,
  totalTrades: 0,
  winningTrades: 0,
  losingTrades: 0,
  winRate: 0,
  profitFactor: 0,
  totalCommission: 0,
  avgProfit: 0,
  avgLoss: 0,
  largestProfit: 0,
  largestLoss: 0,
});

// 交易对列表（从API获取）
const symbols = ref([]);
const loadingSymbols = ref(false);
const running = ref(false);
const error = ref('');
const equityChartRef = ref(null);
const trades = ref([]);
const equityCurve = ref([]);

// 回测历史
const backtestHistory = ref([]);
const loadingHistory = ref(false);
const showHistory = ref(true);

let equityChart = null;

// 格式化函数
const safeNum = (value) => {
  if (value === null || value === undefined || !isFinite(value)) return 0;
  return value;
};

const formatPercent = (value) => {
  return safeNum(value).toFixed(2) + '%';
};

const formatMoney = (value) => {
  const v = safeNum(value);
  if (v === 0) return '$0.00';
  return '$' + v.toFixed(2);
};

const formatPrice = (value) => {
  return safeNum(value).toFixed(2);
};

const formatRatio = (value) => {
  return safeNum(value).toFixed(2);
};

const formatTime = (timestamp) => {
  if (!timestamp) return '-';
  const date = new Date(timestamp);
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
};

const formatDateTime = (isoString) => {
  if (!isoString) return '-';
  const date = new Date(isoString);
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
};

// 运行回测
const runBacktest = async () => {
  running.value = true;
  error.value = '';

  try {
    // 构建策略特定参数
    const params = currentStrategyParams.value;
    const strategySpecificParams = {};
    params.forEach(param => {
      strategySpecificParams[param.name] = strategyParams[param.name];
    });

    // 调用通用回测接口
    const response = await api.runBacktest(config.strategy, {
      symbol: config.symbol,
      timeframe: config.timeframe,
      days: config.days,
      initialCapital: config.capital,
      positionSize: config.positionSize,
      stopLoss: config.stopLoss,
      takeProfit: config.takeProfit,
      strategyParams: strategySpecificParams,
    });

    if (response && response.code === 0 && response.data) {
      const data = response.data;

      // 更新结果
      result.strategyName = data.strategy_name || '';
      result.symbol = data.symbol || '';
      result.timeframe = data.timeframe || '';
      result.startTime = data.start_time || '';
      result.endTime = data.end_time || '';
      result.durationDays = data.duration_days || 0;
      result.initialCapital = data.initial_capital || config.capital;
      result.finalCapital = data.final_capital || config.capital;
      result.totalReturn = data.total_return || 0;
      result.annualReturn = data.annual_return || 0;
      result.maxDrawdown = data.max_drawdown || 0;
      result.sharpeRatio = data.sharpe_ratio || 0;
      result.sortinoRatio = data.sortino_ratio || 0;
      result.calmarRatio = data.calmar_ratio || 0;
      result.totalTrades = data.total_trades || 0;
      result.winningTrades = data.winning_trades || 0;
      result.losingTrades = data.losing_trades || 0;
      result.winRate = data.win_rate || 0;
      result.profitFactor = data.profit_factor || 0;
      result.totalCommission = data.total_commission || 0;
      result.avgProfit = data.avg_profit || 0;
      result.avgLoss = data.avg_loss || 0;
      result.largestProfit = data.largest_profit || 0;
      result.largestLoss = data.largest_loss || 0;

      trades.value = data.trades || [];
      equityCurve.value = data.equity_curve || [];
      updateEquityChart();
      // 刷新历史列表
      loadBacktestHistory();
    } else {
      throw new Error(response?.message || '回测失败');
    }
  } catch (err) {
    console.error('回测错误:', err);
    error.value = err.response?.data?.detail || err.message || '回测执行失败';
  } finally {
    running.value = false;
  }
};

// 更新收益曲线图表
const updateEquityChart = () => {
  if (equityCurve.value.length === 0) return;

  // 等待DOM更新后再初始化/更新图表
  nextTick(() => {
    if (!equityChart && equityChartRef.value) {
      initChart();
    }
    if (!equityChart) return;

    const times = equityCurve.value.map(item => {
      const date = new Date(item.timestamp);
      return date.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' });
    });
    const equities = equityCurve.value.map(item => item.equity);
    const initialLine = equityCurve.value.map(() => result.initialCapital);

    equityChart.setOption({
      tooltip: {
        trigger: 'axis',
        formatter: (params) => {
          let html = `${params[0].name}<br/>`;
          params.forEach(p => {
            html += `${p.seriesName}: $${p.value.toFixed(2)}<br/>`;
          });
          return html;
        },
      },
      legend: {
        data: ['资产曲线', '初始资金'],
        textStyle: { color: '#888' },
        top: 0,
      },
      grid: {
        left: '10%',
        right: '5%',
        top: '15%',
        bottom: '15%',
      },
      xAxis: {
        type: 'category',
        data: times,
        axisLine: { lineStyle: { color: '#404040' } },
        axisLabel: { color: '#888' },
      },
      yAxis: {
        type: 'value',
        axisLine: { lineStyle: { color: '#404040' } },
        axisLabel: { color: '#888' },
        splitLine: { lineStyle: { color: '#2a2a2a' } },
      },
      series: [
        {
          name: '资产曲线',
          type: 'line',
          data: equities,
          smooth: true,
          lineStyle: { color: '#00d4aa', width: 2 },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(0, 212, 170, 0.3)' },
              { offset: 1, color: 'rgba(0, 212, 170, 0.05)' },
            ]),
          },
          itemStyle: { color: '#00d4aa' },
        },
        {
          name: '初始资金',
          type: 'line',
          data: initialLine,
          lineStyle: { color: '#666', width: 1, type: 'dashed' },
          itemStyle: { color: '#666' },
          symbol: 'none',
        },
      ],
    });
  });
};

// 初始化图表
const initChart = () => {
  if (!equityChartRef.value) return;

  equityChart = echarts.init(equityChartRef.value);
  equityChart.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    grid: {
      left: '10%',
      right: '5%',
      top: '15%',
      bottom: '15%',
    },
    xAxis: {
      type: 'category',
      data: [],
      axisLine: { lineStyle: { color: '#404040' } },
      axisLabel: { color: '#888' },
    },
    yAxis: {
      type: 'value',
      axisLine: { lineStyle: { color: '#404040' } },
      axisLabel: { color: '#888' },
      splitLine: { lineStyle: { color: '#2a2a2a' } },
    },
    series: [{
      type: 'line',
      data: [],
      smooth: true,
    }],
  });

  // 使用具名函数以便移除
  handleChartResize = () => {
    equityChart?.resize();
  };
  window.addEventListener('resize', handleChartResize);
};

// 图表 resize 处理函数
let handleChartResize = null;

// 组件卸载时清理资源
onUnmounted(() => {
  if (handleChartResize) {
    window.removeEventListener('resize', handleChartResize);
  }
  if (equityChart) {
    equityChart.dispose();
    equityChart = null;
  }
});

// keep-alive 缓存激活时
onActivated(() => {
  // 重新添加resize事件监听
  if (handleChartResize) {
    window.addEventListener('resize', handleChartResize);
  }
  // 触发图表resize，确保尺寸正确
  nextTick(() => {
    if (equityChart) {
      equityChart.resize();
    }
  });
  // 刷新回测历史列表（可能有新的回测记录）
  loadBacktestHistory();
});

// keep-alive 缓存停用时
onDeactivated(() => {
  // 移除resize事件监听，节省资源
  if (handleChartResize) {
    window.removeEventListener('resize', handleChartResize);
  }
});

// 加载可用交易对列表
const loadSymbols = async () => {
  loadingSymbols.value = true;
  try {
    // 优先获取本地已有数据的交易对
    const res = await api.getAvailableSymbols();
    if (res.code === 0 && res.data && res.data.length > 0) {
      // API 返回的是对象数组 {inst_id, inst_type, timeframes}，需要提取 inst_id
      symbols.value = res.data.map(item => item.inst_id || item);
    } else {
      // 如果本地没有数据，获取OKX支持的交易对
      const instrumentsRes = await api.getInstruments('SPOT');
      if (instrumentsRes.code === 0 && instrumentsRes.data) {
        // 取前20个常用的交易对
        const commonSymbols = ['BTC-USDT', 'ETH-USDT', 'SOL-USDT', 'DOGE-USDT', 'XRP-USDT'];
        const available = instrumentsRes.data.map(i => i.instId || i.inst_id);
        // 优先显示常用的，再显示其他的
        const sorted = [
          ...commonSymbols.filter(s => available.includes(s)),
          ...available.filter(s => !commonSymbols.includes(s)).slice(0, 15)
        ];
        symbols.value = sorted;
      }
    }
    // 如果当前选中的交易对不在列表中，选择第一个
    if (symbols.value.length > 0 && !symbols.value.includes(config.symbol)) {
      config.symbol = symbols.value[0];
    }
  } catch (e) {
    console.error('获取交易对列表失败:', e);
    // 失败时使用默认列表
    symbols.value = ['BTC-USDT', 'ETH-USDT', 'SOL-USDT', 'DOGE-USDT'];
  } finally {
    loadingSymbols.value = false;
  }
};

// 加载可用策略列表
const loadStrategies = async () => {
  loadingStrategies.value = true;
  try {
    const res = await api.getStrategies();
    if (res.code === 0 && res.data) {
      strategies.value = res.data;
      if (strategies.value.length > 0) {
        const ids = strategies.value.map(s => s.id);
        if (!ids.includes(config.strategy)) {
          config.strategy = strategies.value[0].id;
        }
      }
    }
  } catch (e) {
    console.error('获取策略列表失败:', e);
  } finally {
    loadingStrategies.value = false;
  }
};

// 加载回测历史
const loadBacktestHistory = async () => {
  loadingHistory.value = true;
  try {
    const res = await api.getBacktestHistory({ limit: 20 });
    if (res.code === 0 && res.data) {
      backtestHistory.value = res.data;
    }
  } catch (e) {
    console.error('获取回测历史失败:', e);
  } finally {
    loadingHistory.value = false;
  }
};

// 查看历史回测详情
const viewHistoryDetail = async (item) => {
  try {
    const res = await api.getBacktestDetail(item.id);
    if (res.code === 0 && res.data) {
      const data = res.data;
      // 更新结果
      result.strategyName = data.strategy_name || '';
      result.symbol = data.symbol || '';
      result.timeframe = data.timeframe || '';
      result.startTime = data.start_time || '';
      result.endTime = data.end_time || '';
      result.durationDays = data.duration_days || 0;
      result.initialCapital = data.initial_capital || 0;
      result.finalCapital = data.final_capital || 0;
      result.totalReturn = data.total_return || 0;
      result.annualReturn = data.annual_return || 0;
      result.maxDrawdown = data.max_drawdown || 0;
      result.sharpeRatio = data.sharpe_ratio || 0;
      result.sortinoRatio = data.sortino_ratio || 0;
      result.calmarRatio = data.calmar_ratio || 0;
      result.totalTrades = data.total_trades || 0;
      result.winningTrades = data.winning_trades || 0;
      result.losingTrades = data.losing_trades || 0;
      result.winRate = data.win_rate || 0;
      result.profitFactor = data.profit_factor || 0;
      result.totalCommission = data.total_commission || 0;
      result.avgProfit = data.avg_profit || 0;
      result.avgLoss = data.avg_loss || 0;
      result.largestProfit = data.largest_profit || 0;
      result.largestLoss = data.largest_loss || 0;
      trades.value = data.trades || [];
      equityCurve.value = data.equity_curve || [];
      updateEquityChart();
    }
  } catch (e) {
    console.error('获取回测详情失败:', e);
    error.value = '获取回测详情失败';
  }
};

// 删除回测历史记录
const deleteHistoryItem = async (id) => {
  if (!confirm('确定要删除这条回测记录吗？')) return;
  try {
    await api.deleteBacktestResult(id);
    // 从列表中移除
    backtestHistory.value = backtestHistory.value.filter(item => item.id !== id);
  } catch (e) {
    console.error('删除回测记录失败:', e);
    error.value = '删除失败';
  }
};

onMounted(() => {
  loadSymbols();
  loadStrategies();
  loadBacktestHistory();
});
</script>

<style scoped>
.backtest-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-header {
  margin-bottom: 8px;
}

.page-header h1 {
  font-size: 20px;
  font-weight: 600;
  margin-bottom: 4px;
}

.page-header p {
  font-size: 13px;
  color: var(--text-secondary);
}

.backtest-layout {
  flex: 1;
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: 16px;
  overflow: hidden;
}

.config-panel {
  height: fit-content;
  max-height: 100%;
  overflow-y: auto;
}

.form-group {
  margin-bottom: 12px;
}

.form-group label {
  display: block;
  margin-bottom: 6px;
  font-size: 13px;
  color: var(--text-secondary);
}

.form-group .select,
.form-group .input {
  width: 100%;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-size: 13px;
  color: var(--text-primary);
}

.checkbox-label input[type="checkbox"] {
  width: 16px;
  height: 16px;
}

.strategy-params {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--border-color);
}

.strategy-params h4 {
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 12px;
  color: var(--text-primary);
}

.btn-block {
  width: 100%;
  margin-top: 16px;
}

.error-message {
  margin-top: 12px;
  padding: 8px 12px;
  background-color: rgba(255, 77, 79, 0.1);
  border: 1px solid rgba(255, 77, 79, 0.3);
  border-radius: 4px;
  color: #ff4d4f;
  font-size: 13px;
}

.result-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto;
  padding-right: 8px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-top: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-color);
}

.overview-card {
  padding: 16px;
}

.overview-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.overview-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.overview-item .label {
  font-size: 12px;
  color: var(--text-secondary);
}

.overview-item .value {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  font-family: var(--font-mono);
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.stat-card {
  padding: 14px;
  background-color: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  text-align: center;
}

.stat-label {
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 6px;
}

.stat-value {
  font-size: 18px;
  font-weight: 600;
  font-family: var(--font-mono);
}

.chart-card {
  flex-shrink: 0;
}

.equity-chart {
  height: 280px;
}

.trades-card {
  flex-shrink: 0;
}

.trades-table-wrapper {
  max-height: 300px;
  overflow-y: auto;
}

.trades-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.trades-table th,
.trades-table td {
  padding: 8px 10px;
  text-align: left;
  border-bottom: 1px solid var(--border-color);
}

.trades-table th {
  background-color: var(--bg-tertiary);
  font-weight: 500;
  color: var(--text-secondary);
  position: sticky;
  top: 0;
}

.trades-table td {
  font-family: var(--font-mono);
}

.price-up {
  color: #00d4aa;
}

.price-down {
  color: #ff4d4f;
}

.empty-result {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  min-height: 300px;
}

.empty-result .empty-icon {
  font-size: 48px;
  margin-bottom: 12px;
  opacity: 0.5;
}

.empty-result .empty-text {
  font-size: 14px;
}

.result-panel::-webkit-scrollbar,
.trades-table-wrapper::-webkit-scrollbar {
  width: 6px;
}

.result-panel::-webkit-scrollbar-track,
.trades-table-wrapper::-webkit-scrollbar-track {
  background: var(--bg-secondary);
}

.result-panel::-webkit-scrollbar-thumb,
.trades-table-wrapper::-webkit-scrollbar-thumb {
  background: var(--border-color);
  border-radius: 3px;
}

.result-panel::-webkit-scrollbar-thumb:hover,
.trades-table-wrapper::-webkit-scrollbar-thumb:hover {
  background: #555;
}

/* 回测历史样式 */
.history-section {
  margin-top: 16px;
}

.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  user-select: none;
}

.history-header .card-title {
  margin-bottom: 0;
}

.toggle-icon {
  font-size: 18px;
  font-weight: bold;
  color: var(--text-secondary);
  width: 24px;
  text-align: center;
}

.history-content {
  margin-top: 12px;
  border-top: 1px solid var(--border-color);
  padding-top: 12px;
}

.history-loading,
.history-empty {
  text-align: center;
  color: var(--text-secondary);
  padding: 20px 0;
  font-size: 13px;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 300px;
  overflow-y: auto;
}

.history-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background-color: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  transition: border-color 0.2s;
}

.history-item:hover {
  border-color: var(--primary-color);
}

.history-info {
  flex: 1;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.history-main {
  display: flex;
  gap: 12px;
  font-size: 13px;
}

.history-strategy {
  font-weight: 500;
  color: var(--text-primary);
}

.history-symbol {
  color: var(--primary-color);
  font-family: var(--font-mono);
}

.history-timeframe {
  color: var(--text-secondary);
}

.history-stats {
  display: flex;
  gap: 16px;
  font-size: 12px;
  font-family: var(--font-mono);
}

.history-trades {
  color: var(--text-secondary);
}

.history-time {
  color: var(--text-tertiary);
}

.btn-delete {
  width: 24px;
  height: 24px;
  border: none;
  background-color: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  border-radius: 4px;
  font-size: 14px;
  line-height: 1;
  transition: background-color 0.2s ease, color 0.2s ease;
}

.btn-delete:hover {
  background-color: rgba(255, 77, 79, 0.1);
  color: #ff4d4f;
}
</style>
