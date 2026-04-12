<template>
  <div class="backtest-view">
    <!-- 顶部配置栏 -->
    <div class="config-bar card">
      <div class="config-row">
        <div class="config-item">
          <label>交易对</label>
          <select v-model="config.symbol" class="select select-sm" :disabled="loadingSymbols">
            <option v-if="loadingSymbols" value="">加载中...</option>
            <option v-else-if="symbols.length === 0" value="">无可用</option>
            <option v-for="s in symbols" :key="s" :value="s">{{ s }}</option>
          </select>
        </div>
        <div class="config-item">
          <label>时间周期</label>
          <select v-model="config.timeframe" class="select select-sm">
            <option value="15m">15m</option>
            <option value="30m">30m</option>
            <option value="1H">1H</option>
            <option value="2H">2H</option>
            <option value="4H">4H</option>
            <option value="1D">1D</option>
          </select>
        </div>
        <div class="config-item">
          <label>策略</label>
          <select v-model="config.strategy" class="select select-sm" :disabled="loadingStrategies">
            <option v-if="loadingStrategies" value="">加载中...</option>
            <option v-for="s in strategies" :key="s.id" :value="s.id">{{ s.name }}</option>
          </select>
        </div>
        <div class="config-item">
          <label>天数</label>
          <input v-model.number="config.days" class="input input-sm" type="number" min="1" max="365" />
        </div>
        <div class="config-item">
          <label>资金($)</label>
          <input v-model.number="config.capital" class="input input-sm" type="number" min="100" />
        </div>
        <div class="config-item">
          <label>仓位</label>
          <input v-model.number="config.positionSize" class="input input-sm" type="number" min="0.1" max="1" step="0.1" />
        </div>
        <div class="config-item">
          <label>止损</label>
          <input v-model.number="config.stopLoss" class="input input-sm" type="number" min="0" max="0.5" step="0.01" />
        </div>
        <div class="config-item">
          <label>止盈</label>
          <input v-model.number="config.takeProfit" class="input input-sm" type="number" min="0" max="1" step="0.01" />
        </div>
      </div>
      <!-- 策略参数行 -->
      <div v-if="currentStrategyParams.length > 0" class="config-row config-row-params">
        <div v-for="param in currentStrategyParams" :key="param.name" class="config-item">
          <label>{{ param.label || param.name }}</label>
          <input v-if="param.type === 'int' || param.type === 'float'" v-model.number="strategyParams[param.name]" class="input input-sm" type="number" :min="param.min" :max="param.max" :step="param.type === 'float' ? 0.01 : 1" />
          <select v-else-if="param.options" v-model="strategyParams[param.name]" class="select select-sm">
            <option v-for="opt in param.options" :key="opt" :value="opt">{{ opt }}</option>
          </select>
          <input v-else type="checkbox" v-model="strategyParams[param.name]" />
        </div>
      </div>
      <div class="config-actions">
        <div v-if="error" class="config-error">{{ error }}</div>
        <button class="btn btn-primary" @click="runBacktest" :disabled="running || !config.strategy">
          {{ running ? '回测中...' : '开始回测' }}
        </button>
      </div>
    </div>

    <div v-if="config.symbol" class="backtest-data-health" :class="`status-${backtestHealthStatus}`">
      <span class="backtest-data-health-badge">{{ backtestHealthBadgeText }}</span>
      <span class="backtest-data-health-text">{{ backtestHealthSummaryText }}</span>
    </div>

    <!-- 主体区域 -->
    <div class="main-area">
      <!-- 左侧：K线图主区 -->
      <div class="chart-area">
        <!-- K线图 + 买卖标注 -->
        <div class="kline-card card">
          <div class="kline-header">
            <div class="kline-heading">
              <div class="kline-title">
                <span v-if="result.strategyName">{{ result.strategyName }} · {{ result.symbol }} · {{ result.timeframe }}</span>
                <span v-else class="kline-placeholder">运行回测后显示 K 线图</span>
              </div>
              <div v-if="result.strategyName" class="kline-meta">
                <span class="kline-meta-chip" :class="result.totalReturn >= 0 ? 'price-up' : 'price-down'">{{ formatPercent(result.totalReturn) }}</span>
                <span class="kline-meta-chip">{{ result.totalTrades }} 笔交易</span>
                <span class="kline-meta-chip">{{ result.durationDays }} 天区间</span>
              </div>
            </div>
            <div class="kline-legend" v-if="result.strategyName">
              <span class="legend-item buy">▲ 买入</span>
              <span class="legend-item sell">▼ 卖出</span>
            </div>
          </div>
          <div v-if="result.strategyName" class="kline-toolbar">
            <div v-if="overlayIndicatorOptions.length > 0" class="toolbar-group">
              <span class="toolbar-label">主图指标</span>
              <button
                v-for="indicator in overlayIndicatorOptions"
                :key="indicator.key"
                class="toolbar-chip"
                :class="{ active: activeOverlayIndicators.includes(indicator.key) }"
                @click="toggleOverlayIndicator(indicator.key)"
              >
                <span class="chip-dot" :style="{ backgroundColor: indicator.color }"></span>
                {{ indicator.label }}
              </button>
            </div>
            <div v-if="secondaryIndicatorOptions.length > 0" class="toolbar-group">
              <span class="toolbar-label">副图指标</span>
              <button
                v-for="panel in secondaryIndicatorOptions"
                :key="panel.key"
                class="toolbar-chip"
                :class="{ active: activeSecondaryIndicator === panel.key }"
                @click="activeSecondaryIndicator = panel.key"
              >
                {{ panel.label }}
              </button>
            </div>
          </div>
          <div v-if="chartNotice" class="chart-notice">
            {{ chartNotice }}
          </div>
          <div ref="klineChartRef" class="kline-chart"></div>
          <div v-if="!result.strategyName" class="kline-empty">
            <div class="empty-icon">📈</div>
            <div>配置参数后点击「开始回测」</div>
          </div>
          <div v-else-if="showSnapshotEmpty" class="kline-empty kline-empty-legacy">
            <div class="empty-icon">🗂️</div>
            <div>该历史记录未保存图表快照</div>
            <div class="empty-subtext">
              当前只保留了绩效和成交明细。重新运行一次回测后，会自动生成 K 线、指标和买卖点标注。
            </div>
          </div>
        </div>

        <!-- 收益曲线 -->
        <div class="equity-card card" v-if="equityCurve.length > 0">
          <div class="card-title-row">
            <h4>净值曲线</h4>
            <span :class="result.totalReturn >= 0 ? 'price-up' : 'price-down'">{{ formatPercent(result.totalReturn) }}</span>
          </div>
          <div ref="equityChartRef" class="equity-chart"></div>
        </div>

        <!-- 底部 tab：交易记录 / 参数扫描 -->
        <div class="bottom-card card">
          <div class="bottom-tab-bar">
            <button class="bottom-tab" :class="{ active: bottomTab === 'trades' }" @click="bottomTab = 'trades'">
              交易记录 <span v-if="trades.length" class="tab-count">{{ trades.length }}</span>
            </button>
            <button class="bottom-tab" :class="{ active: bottomTab === 'scan' }" @click="bottomTab = 'scan'">
              参数扫描
            </button>
            <button class="bottom-tab" :class="{ active: bottomTab === 'history' }" @click="bottomTab = 'history'">
              回测历史
            </button>
          </div>
          <div class="bottom-card-body">

            <!-- 交易记录 -->
            <div v-if="bottomTab === 'trades'">
              <div v-if="trades.length === 0" class="tab-empty">暂无交易记录</div>
              <div v-else class="trades-wrapper">
                <table class="data-table">
                  <thead>
                    <tr>
                      <th>时间</th><th>方向</th><th>价格</th><th>数量</th><th>金额</th><th>手续费</th><th>盈亏</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(trade, i) in trades.slice(-30)" :key="i">
                      <td>{{ formatTime(trade.timestamp) }}</td>
                      <td :class="trade.side === 'buy' ? 'price-up' : 'price-down'">{{ trade.side === 'buy' ? '▲ 买入' : '▼ 卖出' }}</td>
                      <td>{{ formatPrice(trade.price) }}</td>
                      <td>{{ safeNum(trade.quantity).toFixed(6) }}</td>
                      <td>{{ formatMoney(trade.value) }}</td>
                      <td>{{ formatMoney(trade.commission) }}</td>
                      <td :class="(trade.pnl || 0) >= 0 ? 'price-up' : 'price-down'">{{ trade.pnl ? formatMoney(trade.pnl) : '-' }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <!-- 参数扫描 -->
            <div v-if="bottomTab === 'scan'">
              <div v-if="numericStrategyParams.length === 0" class="tab-empty">当前策略无可扫描的数值参数</div>
              <div v-else class="scan-area">
                <div class="scan-config">
                  <div class="config-item"><label>优化指标</label>
                    <select v-model="scanConfig.metric" class="select select-sm">
                      <option value="total_return">总收益率</option>
                      <option value="sharpe_ratio">夏普比率</option>
                      <option value="win_rate">胜率</option>
                      <option value="max_drawdown">最大回撤</option>
                    </select>
                  </div>
                  <div class="config-item"><label>X轴参数</label>
                    <select v-model="scanConfig.xParam" class="select select-sm" @change="initScanParams">
                      <option v-for="p in numericStrategyParams" :key="p.name" :value="p.name">{{ p.label || p.name }}</option>
                    </select>
                  </div>
                  <div class="config-item"><label>X起</label><input v-model.number="scanConfig.xStart" class="input input-sm" type="number" /></div>
                  <div class="config-item"><label>X止</label><input v-model.number="scanConfig.xEnd" class="input input-sm" type="number" /></div>
                  <div class="config-item"><label>X步长</label><input v-model.number="scanConfig.xStep" class="input input-sm" type="number" /></div>
                  <template v-if="secondaryScanParams.length > 0">
                    <div class="config-item"><label>Y轴参数</label>
                      <select v-model="scanConfig.yParam" class="select select-sm">
                        <option value="">不使用</option>
                        <option v-for="p in secondaryScanParams" :key="p.name" :value="p.name">{{ p.label || p.name }}</option>
                      </select>
                    </div>
                    <template v-if="scanConfig.yParam">
                      <div class="config-item"><label>Y起</label><input v-model.number="scanConfig.yStart" class="input input-sm" type="number" /></div>
                      <div class="config-item"><label>Y止</label><input v-model.number="scanConfig.yEnd" class="input input-sm" type="number" /></div>
                      <div class="config-item"><label>Y步长</label><input v-model.number="scanConfig.yStep" class="input input-sm" type="number" /></div>
                    </template>
                  </template>
                  <button class="btn btn-primary btn-sm" @click="runScan" :disabled="scanning || !config.strategy">{{ scanning ? '扫描中...' : '开始扫描' }}</button>
                </div>
                <div v-if="scanResult.results.length > 0">
                  <div ref="scanHeatmapRef" class="scan-heatmap"></div>
                  <table class="data-table" style="margin-top:12px">
                    <thead><tr><th>排名</th><th>参数</th><th>{{ scanResult.metricLabel }}</th><th>收益率</th><th>夏普</th><th>回撤</th></tr></thead>
                    <tbody>
                      <tr v-for="(item, i) in scanResult.results.slice(0, 8)" :key="i">
                        <td>#{{ i+1 }}</td>
                        <td>{{ formatParams(item.params) }}</td>
                        <td>{{ formatScanMetric(item.metrics?.[scanResult.metric]) }}</td>
                        <td :class="item.metrics?.total_return >= 0 ? 'price-up' : 'price-down'">{{ formatPercent(item.metrics?.total_return) }}</td>
                        <td>{{ formatRatio(item.metrics?.sharpe_ratio) }}</td>
                        <td class="price-down">{{ formatPercent(item.metrics?.max_drawdown) }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>

            <!-- 回测历史 -->
            <div v-if="bottomTab === 'history'">
              <div v-if="loadingHistory" class="tab-empty">加载中...</div>
              <div v-else-if="backtestHistory.length === 0" class="tab-empty">暂无历史记录</div>
              <div v-else class="history-list">
                <div
                  v-for="item in backtestHistory"
                  :key="item.id"
                  class="history-item"
                  :class="{ active: selectedHistoryId === item.id, compared: compareIds.includes(item.id) }"
                  @click="viewHistoryDetail(item)"
                >
                  <div class="history-info">
                    <div class="history-name-group">
                      <span class="history-name">{{ item.strategy_name }}</span>
                      <span v-if="selectedHistoryId === item.id" class="history-flag">当前查看</span>
                      <span v-if="compareIds.includes(item.id)" class="history-flag history-flag-compare">对比中</span>
                    </div>
                    <span class="history-symbol">{{ item.symbol }}</span>
                    <span class="history-time">{{ formatDateTime(item.created_at) }}</span>
                  </div>
                  <div class="history-stats">
                    <span :class="item.total_return >= 0 ? 'price-up' : 'price-down'">{{ formatPercent(item.total_return) }}</span>
                    <span class="history-trades">{{ item.total_trades }}笔</span>
                    <label class="compare-toggle" @click.stop>
                      <input type="checkbox" :checked="compareIds.includes(item.id)" @change="toggleCompareItem(item)" />
                      对比
                    </label>
                    <button class="btn-delete" @click.stop="deleteHistoryItem(item.id)">×</button>
                  </div>
                </div>
                <div v-if="compareResults.length > 1" class="compare-section">
                  <h4>对比曲线</h4>
                  <div class="compare-toolbar">
                    <span class="toolbar-label">曲线模式</span>
                    <button
                      class="toolbar-chip"
                      :class="{ active: compareScaleMode === 'normalized' }"
                      @click="compareScaleMode = 'normalized'"
                    >
                      归一化收益
                    </button>
                    <button
                      class="toolbar-chip"
                      :class="{ active: compareScaleMode === 'equity' }"
                      @click="compareScaleMode = 'equity'"
                    >
                      原始权益
                    </button>
                  </div>
                  <div class="compare-summary-table">
                    <table class="data-table compare-table">
                      <thead>
                        <tr>
                          <th>结果</th>
                          <th>参数</th>
                          <th>收益率</th>
                          <th>夏普</th>
                          <th>回撤</th>
                          <th>胜率</th>
                          <th>交易数</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr v-for="item in compareResults" :key="`compare-${item.id}`">
                          <td>
                            <div class="compare-name">{{ item.strategyName }}</div>
                            <div class="compare-subline">{{ item.symbol }} · {{ item.timeframe }}</div>
                          </td>
                          <td>{{ formatParams(item.params) }}</td>
                          <td :class="item.totalReturn >= 0 ? 'price-up' : 'price-down'">{{ formatPercent(item.totalReturn) }}</td>
                          <td>{{ formatRatio(item.sharpeRatio) }}</td>
                          <td class="price-down">{{ formatPercent(item.maxDrawdown) }}</td>
                          <td :class="item.winRate >= 50 ? 'price-up' : 'price-down'">{{ formatPercent(item.winRate) }}</td>
                          <td>{{ item.totalTrades }}</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                  <div ref="compareChartRef" class="compare-chart"></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧：统计面板 -->
      <div class="stats-panel" v-if="result.strategyName">
        <div class="stats-overview card">
          <div class="stat-section-title">回测概览</div>
          <div class="stats-overview-grid">
            <div class="metric-tile">
              <span class="metric-tile-label">总收益率</span>
              <strong class="metric-tile-value" :class="result.totalReturn >= 0 ? 'price-up' : 'price-down'">{{ formatPercent(result.totalReturn) }}</strong>
            </div>
            <div class="metric-tile">
              <span class="metric-tile-label">最大回撤</span>
              <strong class="metric-tile-value price-down">{{ formatPercent(result.maxDrawdown) }}</strong>
            </div>
            <div class="metric-tile">
              <span class="metric-tile-label">夏普比率</span>
              <strong class="metric-tile-value">{{ formatRatio(result.sharpeRatio) }}</strong>
            </div>
            <div class="metric-tile">
              <span class="metric-tile-label">胜率</span>
              <strong class="metric-tile-value" :class="result.winRate >= 50 ? 'price-up' : 'price-down'">{{ formatPercent(result.winRate) }}</strong>
            </div>
          </div>
        </div>
        <div class="stat-section card">
          <h4 class="stat-section-title">收益</h4>
          <div class="stat-metric-grid">
            <div class="stat-metric">
              <span>年化收益</span>
              <strong :class="result.annualReturn >= 0 ? 'price-up' : 'price-down'">{{ formatPercent(result.annualReturn) }}</strong>
            </div>
            <div class="stat-metric">
              <span>初始资金</span>
              <strong>{{ formatMoney(result.initialCapital) }}</strong>
            </div>
            <div class="stat-metric">
              <span>最终资金</span>
              <strong :class="result.finalCapital >= result.initialCapital ? 'price-up' : 'price-down'">{{ formatMoney(result.finalCapital) }}</strong>
            </div>
            <div class="stat-metric">
              <span>手续费</span>
              <strong>{{ formatMoney(result.totalCommission) }}</strong>
            </div>
          </div>
        </div>
        <div class="stat-section card">
          <h4 class="stat-section-title">风险</h4>
          <div class="stat-metric-grid">
            <div class="stat-metric">
              <span>索提诺</span>
              <strong>{{ formatRatio(result.sortinoRatio) }}</strong>
            </div>
            <div class="stat-metric">
              <span>卡玛比率</span>
              <strong>{{ formatRatio(result.calmarRatio) }}</strong>
            </div>
          </div>
        </div>
        <div class="stat-section card">
          <h4 class="stat-section-title">交易</h4>
          <div class="stat-metric-grid">
            <div class="stat-metric">
              <span>总交易</span>
              <strong>{{ result.totalTrades }}</strong>
            </div>
            <div class="stat-metric">
              <span>盈利</span>
              <strong class="price-up">{{ result.winningTrades }}</strong>
            </div>
            <div class="stat-metric">
              <span>亏损</span>
              <strong class="price-down">{{ result.losingTrades }}</strong>
            </div>
            <div class="stat-metric">
              <span>盈亏比</span>
              <strong>{{ formatRatio(result.profitFactor) }}</strong>
            </div>
            <div class="stat-metric">
              <span>平均盈利</span>
              <strong class="price-up">{{ formatMoney(result.avgProfit) }}</strong>
            </div>
            <div class="stat-metric">
              <span>平均亏损</span>
              <strong class="price-down">{{ formatMoney(result.avgLoss) }}</strong>
            </div>
          </div>
        </div>
        <div class="stat-section card">
          <h4 class="stat-section-title">周期</h4>
          <div class="stat-metric-grid stat-metric-grid-compact">
            <div class="stat-metric">
              <span>开始</span>
              <strong>{{ result.startTime ? result.startTime.slice(0,10) : '-' }}</strong>
            </div>
            <div class="stat-metric">
              <span>结束</span>
              <strong>{{ result.endTime ? result.endTime.slice(0,10) : '-' }}</strong>
            </div>
            <div class="stat-metric">
              <span>天数</span>
              <strong>{{ result.durationDays }}</strong>
            </div>
          </div>
        </div>
        <div class="stat-section card" v-if="overlayIndicatorOptions.length > 0 || secondaryIndicatorOptions.length > 0">
          <h4 class="stat-section-title">图表指标</h4>
          <div class="indicator-group" v-if="overlayIndicatorOptions.length > 0">
            <div class="indicator-group-title">主图</div>
            <div class="indicator-badges">
              <span
                v-for="indicator in overlayIndicatorOptions"
                :key="indicator.key"
                class="indicator-badge"
                :class="{ active: activeOverlayIndicators.includes(indicator.key) }"
              >
                <span class="chip-dot" :style="{ backgroundColor: indicator.color }"></span>
                {{ indicator.label }}
              </span>
            </div>
          </div>
          <div class="indicator-group" v-if="secondaryIndicatorOptions.length > 0">
            <div class="indicator-group-title">副图</div>
            <div class="indicator-badges">
              <span
                v-for="panel in secondaryIndicatorOptions"
                :key="panel.key"
                class="indicator-badge"
                :class="{ active: activeSecondaryIndicator === panel.key }"
              >
                {{ panel.label }}
              </span>
            </div>
          </div>
        </div>
        <div class="stat-section card" v-if="recentTrades.length > 0">
          <h4 class="stat-section-title">最近成交</h4>
          <div class="recent-trade-list">
            <div v-for="trade in recentTrades" :key="`${trade.timestamp}-${trade.side}-${trade.price}`" class="recent-trade-item">
              <div class="recent-trade-top">
                <span :class="trade.side === 'buy' ? 'price-up' : 'price-down'">{{ trade.side === 'buy' ? '▲ 买入' : '▼ 卖出' }}</span>
                <span>{{ formatTime(trade.timestamp) }}</span>
              </div>
              <div class="recent-trade-bottom">
                <span>{{ formatPrice(trade.price) }}</span>
                <span>{{ safeNum(trade.quantity).toFixed(6) }}</span>
                <span :class="(trade.pnl || 0) >= 0 ? 'price-up' : 'price-down'">{{ trade.pnl ? formatMoney(trade.pnl) : '-' }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧空状态 -->
      <div class="stats-panel stats-empty" v-else>
        <div class="empty-hint-box">
          <div class="empty-icon">⚙️</div>
          <div>选择策略和参数<br/>点击「开始回测」</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue';
import { api } from '../services/api';
import { useBacktestViewUtils } from '../composables/backtest/useBacktestViewUtils';
import { useBacktestViewCharts } from '../composables/backtest/useBacktestViewCharts';
import { useSymbolDataHealth } from '../composables/useSymbolDataHealth';

defineOptions({
  name: 'BacktestView',
});

const METRIC_LABELS = {
  total_return: '总收益率',
  annual_return: '年化收益率',
  sharpe_ratio: '夏普比率',
  sortino_ratio: '索提诺比率',
  calmar_ratio: '卡玛比率',
  win_rate: '胜率',
  profit_factor: '盈亏比',
  max_drawdown: '最大回撤',
  total_trades: '交易次数',
};

const INDICATOR_LABELS = {
  ma_short: '短均线',
  ma_long: '长均线',
  ma_trend: '趋势均线',
  trend_ma: '趋势均线',
  bb_upper: '布林上轨',
  bb_middle: '布林中轨',
  bb_lower: '布林下轨',
  dif: 'DIF',
  dea: 'DEA',
  histogram: 'MACD 柱',
  rsi: 'RSI',
  k: 'K',
  d: 'D',
  j: 'J',
  bandwidth: '带宽',
  close: '收盘价',
  volume: '成交量',
  volume_ma: '成交量均线',
};

const INDICATOR_COLORS = {
  ma_short: 'var(--gold-color)',
  ma_long: 'var(--color-info)',
  ma_trend: 'var(--accent-color)',
  trend_ma: 'var(--accent-color)',
  bb_upper: 'var(--secondary-color)',
  bb_middle: 'var(--color-success)',
  bb_lower: '#6366F1',
  dif: 'var(--gold-color)',
  dea: 'var(--color-info)',
  histogram: 'var(--color-success)',
  rsi: 'var(--gold-color)',
  k: '#14B8A6',
  d: '#60A5FA',
  j: 'var(--accent-color)',
  bandwidth: '#A855F7',
  volume_ma: '#2DD4BF',
};

const PRIMARY_OVERLAY_ORDER = [
  'ma_short',
  'ma_long',
  'ma_trend',
  'trend_ma',
  'bb_upper',
  'bb_middle',
  'bb_lower',
];

const SECONDARY_PANEL_ORDER = ['macd', 'rsi', 'kdj', 'bandwidth'];


const klineChartRef = ref(null);
const equityChartRef = ref(null);
const scanHeatmapRef = ref(null);
const compareChartRef = ref(null);

const loadingSymbols = ref(false);
const loadingStrategies = ref(false);
const loadingHistory = ref(false);
const running = ref(false);
const scanning = ref(false);
const error = ref('');
const chartNotice = ref('');
const bottomTab = ref('trades');
const selectedHistoryId = ref(null);
const activeSecondaryIndicator = ref('');

const availableSymbolRows = ref([]);
const strategies = ref([]);
const backtestHistory = ref([]);
const compareIds = ref([]);
const compareResults = ref([]);
const compareScaleMode = ref('normalized');

const config = reactive({
  symbol: '',
  instType: 'SPOT',
  timeframe: '1H',
  strategy: '',
  days: 90,
  capital: 10000,
  positionSize: 0.5,
  stopLoss: 0.05,
  takeProfit: 0.10,
});

const strategyParams = reactive({});

const scanConfig = reactive({
  metric: 'total_return',
  xParam: '',
  xStart: 0,
  xEnd: 0,
  xStep: 1,
  yParam: '',
  yStart: 0,
  yEnd: 0,
  yStep: 1,
});

const scanResult = reactive({
  results: [],
  metric: 'total_return',
  metricLabel: METRIC_LABELS.total_return,
  heatmap: {
    x_key: '',
    x_values: [],
    y_key: '',
    y_values: [],
    points: [],
  },
});

const result = reactive(createEmptyResult());
const candles = ref([]);
const equityCurve = ref([]);
const trades = ref([]);
const activeOverlayIndicators = ref([]);
const indicatorMap = reactive({});
const historyDetailCache = new Map();
const {
  symbols,
  currentStrategyParams,
  numericStrategyParams,
  secondaryScanParams,
  overlayIndicatorOptions,
  secondaryIndicatorOptions,
  showSnapshotEmpty,
  recentTrades,
  safeNum,
  parseMaybeJSON,
  normalizeCandle,
  normalizeCandles,
  normalizeEquityCurve,
  normalizeTrades,
  normalizeIndicatorMap,
  normalizeBacktestPayload,
  formatIndicatorLabel,
  getIndicatorColor,
  isPrimaryOverlayIndicator,
  buildOverlayOptions,
  buildSecondaryOptions,
  ensureSelectedSymbol,
  initializeStrategyParams,
  buildScanValues,
  syncIndicatorSelections,
  toggleOverlayIndicator,
  formatPrice,
  formatMoney,
  formatPercent,
  formatRatio,
  formatDateTime,
  formatTime,
  formatAxisTime,
  formatParams,
  formatScanMetric,
  formatMetadataValue,
  getTradeMetadataEntries,
} = useBacktestViewUtils({
  config,
  result,
  availableSymbolRows,
  strategies,
  strategyParams,
  scanConfig,
  scanResult,
  indicatorMap,
  candles,
  trades,
  activeOverlayIndicators,
  activeSecondaryIndicator,
  INDICATOR_LABELS,
  INDICATOR_COLORS,
  PRIMARY_OVERLAY_ORDER,
  SECONDARY_PANEL_ORDER,
});
const {
  healthStatus: backtestHealthStatus,
  healthBadgeText: backtestHealthBadgeText,
  healthSummaryText: backtestHealthSummaryText,
} = useSymbolDataHealth({
  symbolRef: computed(() => config.symbol),
  instTypeRef: computed(() => config.instType),
});
const {
  renderKlineChart,
  renderEquityChart,
  renderScanHeatmap,
  renderCompareChart,
  renderAllCharts,
  resizeAllCharts,
  disposeAllCharts,
} = useBacktestViewCharts({
  klineChartRef,
  equityChartRef,
  scanHeatmapRef,
  compareChartRef,
  candles,
  config,
  activeOverlayIndicators,
  overlayIndicatorOptions,
  trades,
  scanResult,
  compareResults,
  compareScaleMode,
  equityCurve,
  bottomTab,
  formatDateTime,
  formatMoney,
  formatScanMetric,
  safeNum,
  getIndicatorColor,
});

function createEmptyResult() {
  return {
    id: null,
    strategyId: '',
    strategyName: '',
    symbol: '',
    instType: 'SPOT',
    timeframe: '',
    startTime: '',
    endTime: '',
    durationDays: 0,
    days: 0,
    initialCapital: 0,
    finalCapital: 0,
    totalReturn: 0,
    annualReturn: 0,
    maxDrawdown: 0,
    sharpeRatio: 0,
    sortinoRatio: 0,
    calmarRatio: 0,
    winRate: 0,
    profitFactor: 0,
    totalTrades: 0,
    winningTrades: 0,
    losingTrades: 0,
    avgProfit: 0,
    avgLoss: 0,
    largestProfit: 0,
    largestLoss: 0,
    totalCommission: 0,
    params: {},
    sampleStep: 1,
    createdAt: '',
  };
}

function resetIndicatorMap(nextMap = {}) {
  Object.keys(indicatorMap).forEach((key) => {
    delete indicatorMap[key];
  });
  Object.entries(nextMap).forEach(([key, values]) => {
    indicatorMap[key] = values;
  });
}

function resetResultView() {
  Object.assign(result, createEmptyResult());
  candles.value = [];
  equityCurve.value = [];
  trades.value = [];
  resetIndicatorMap();
  activeOverlayIndicators.value = [];
  activeSecondaryIndicator.value = '';
  chartNotice.value = '';
}

async function loadSymbols() {
  loadingSymbols.value = true;
  try {
    const response = await api.getAvailableSymbols();
    const rows = Array.isArray(response.data) ? response.data : [];
    availableSymbolRows.value = rows
      .map((item) => {
        if (typeof item === 'string') {
          return { inst_id: item, inst_type: item.endsWith('-SWAP') ? 'SWAP' : 'SPOT' };
        }
        return {
          inst_id: item.inst_id,
          inst_type: item.inst_type || (String(item.inst_id || '').endsWith('-SWAP') ? 'SWAP' : 'SPOT'),
        };
      })
      .filter((item) => item.inst_id)
      .sort((left, right) => left.inst_id.localeCompare(right.inst_id));

    ensureSelectedSymbol();
  } catch (requestError) {
    error.value = requestError?.response?.data?.detail || requestError?.message || '加载交易对失败';
    availableSymbolRows.value = [{ inst_id: 'BTC-USDT', inst_type: 'SPOT' }];
    ensureSelectedSymbol();
  } finally {
    loadingSymbols.value = false;
  }
}

async function loadStrategies() {
  loadingStrategies.value = true;
  try {
    const response = await api.getStrategies();
    strategies.value = Array.isArray(response.data) ? response.data : [];
    if (!config.strategy && strategies.value.length > 0) {
      config.strategy = strategies.value[0].id;
    } else if (config.strategy && !strategies.value.some((item) => item.id === config.strategy)) {
      config.strategy = strategies.value[0]?.id || '';
    }
    initializeStrategyParams(result.params || {});
  } catch (requestError) {
    error.value = requestError?.response?.data?.detail || requestError?.message || '加载策略列表失败';
  } finally {
    loadingStrategies.value = false;
  }
}

async function loadBacktestHistory() {
  loadingHistory.value = true;
  try {
    const response = await api.getBacktestHistory({ limit: 40 });
    backtestHistory.value = (Array.isArray(response.data) ? response.data : []).map((item) => ({
      ...item,
      params: parseMaybeJSON(item.params_json, {}),
    }));
  } catch (requestError) {
    console.warn('加载回测历史失败:', requestError);
  } finally {
    loadingHistory.value = false;
  }
}

async function applyBacktestPayload(payload, syncConfig = false) {
  const normalized = normalizeBacktestPayload(payload);

  Object.assign(result, {
    id: normalized.id,
    strategyId: normalized.strategyId,
    strategyName: normalized.strategyName,
    symbol: normalized.symbol,
    instType: normalized.instType,
    timeframe: normalized.timeframe,
    startTime: normalized.startTime,
    endTime: normalized.endTime,
    durationDays: normalized.durationDays,
    days: normalized.days,
    initialCapital: normalized.initialCapital,
    finalCapital: normalized.finalCapital,
    totalReturn: normalized.totalReturn,
    annualReturn: normalized.annualReturn,
    maxDrawdown: normalized.maxDrawdown,
    sharpeRatio: normalized.sharpeRatio,
    sortinoRatio: normalized.sortinoRatio,
    calmarRatio: normalized.calmarRatio,
    winRate: normalized.winRate,
    profitFactor: normalized.profitFactor,
    totalTrades: normalized.totalTrades,
    winningTrades: normalized.winningTrades,
    losingTrades: normalized.losingTrades,
    avgProfit: normalized.avgProfit,
    avgLoss: normalized.avgLoss,
    largestProfit: normalized.largestProfit,
    largestLoss: normalized.largestLoss,
    totalCommission: normalized.totalCommission,
    params: normalized.params,
    sampleStep: normalized.sampleStep,
    createdAt: normalized.createdAt,
  });

  candles.value = normalized.candles;
  equityCurve.value = normalized.equityCurve;
  trades.value = normalized.trades;
  resetIndicatorMap(normalized.indicators);
  syncIndicatorSelections(false);

  if (syncConfig) {
    if (normalized.instType) config.instType = normalized.instType;
    if (normalized.symbol) config.symbol = normalized.symbol;
    if (normalized.timeframe) config.timeframe = normalized.timeframe;
    if (normalized.strategyId) config.strategy = normalized.strategyId;
    if (normalized.days) config.days = normalized.days;
    if (normalized.initialCapital) config.capital = normalized.initialCapital;
    initializeStrategyParams(normalized.params || {});
  }

  chartNotice.value = normalized.candles.length === 0 && normalized.strategyName
    ? '该记录未携带 K 线与指标快照，当前只展示绩效和交易明细。'
    : '';

  await nextTick();
  renderAllCharts();
}

async function runBacktest() {
  if (!config.strategy) {
    error.value = '请选择策略';
    return;
  }
  if (!config.symbol) {
    error.value = '请选择交易对';
    return;
  }

  error.value = '';
  running.value = true;
  try {
    const response = await api.runBacktest(config.strategy, {
      symbol: config.symbol,
      instType: config.instType,
      timeframe: config.timeframe,
      days: config.days,
      initialCapital: config.capital,
      positionSize: config.positionSize,
      stopLoss: config.stopLoss,
      takeProfit: config.takeProfit,
      strategyParams: { ...strategyParams },
    });
    if (response.code !== 0 || !response.data) {
      throw new Error(response.message || '回测失败');
    }
    await applyBacktestPayload(response.data, false);
    await loadBacktestHistory();
  } catch (requestError) {
    error.value = requestError?.response?.data?.detail || requestError?.message || '回测失败';
  } finally {
    running.value = false;
  }
}

async function runScan() {
  if (!config.strategy || !scanConfig.xParam) {
    return;
  }

  const xParamMeta = numericStrategyParams.value.find((item) => item.name === scanConfig.xParam);
  const yParamMeta = numericStrategyParams.value.find((item) => item.name === scanConfig.yParam);
  const xValues = buildScanValues(scanConfig.xStart, scanConfig.xEnd, scanConfig.xStep, xParamMeta?.type || 'int');
  const yValues = scanConfig.yParam ? buildScanValues(scanConfig.yStart, scanConfig.yEnd, scanConfig.yStep, yParamMeta?.type || 'int') : [];

  if (xValues.length < 2) {
    error.value = 'X 轴参数至少需要 2 个候选值';
    return;
  }
  if (scanConfig.yParam && yValues.length < 2) {
    error.value = 'Y 轴参数至少需要 2 个候选值';
    return;
  }

  const baseParams = { ...strategyParams };
  delete baseParams[scanConfig.xParam];
  if (scanConfig.yParam) {
    delete baseParams[scanConfig.yParam];
  }

  const scanParams = {
    [scanConfig.xParam]: xValues,
  };
  if (scanConfig.yParam) {
    scanParams[scanConfig.yParam] = yValues;
  }

  scanning.value = true;
  error.value = '';
  try {
    const response = await api.scanBacktest(config.strategy, {
      symbol: config.symbol,
      instType: config.instType,
      timeframe: config.timeframe,
      days: config.days,
      initialCapital: config.capital,
      positionSize: config.positionSize,
      stopLoss: config.stopLoss,
      takeProfit: config.takeProfit,
      metric: scanConfig.metric,
      baseParams,
      scanParams,
      persistResults: false,
    });

    if (response.code !== 0 || !response.data) {
      throw new Error(response.message || '参数扫描失败');
    }

    scanResult.results = Array.isArray(response.data.results) ? response.data.results : [];
    scanResult.metric = response.data.metric || scanConfig.metric;
    scanResult.metricLabel = METRIC_LABELS[scanResult.metric] || scanResult.metric;
    scanResult.heatmap = response.data.heatmap || {
      x_key: '',
      x_values: [],
      y_key: '',
      y_values: [],
      points: [],
    };

    await nextTick();
    renderScanHeatmap();
  } catch (requestError) {
    error.value = requestError?.response?.data?.detail || requestError?.message || '参数扫描失败';
  } finally {
    scanning.value = false;
  }
}

async function fetchHistoryDetail(resultId) {
  if (historyDetailCache.has(resultId)) {
    return historyDetailCache.get(resultId);
  }

  const response = await api.getBacktestDetail(resultId);
  const normalized = normalizeBacktestPayload(response.data || {});
  historyDetailCache.set(resultId, normalized);
  return normalized;
}

async function viewHistoryDetail(item) {
  selectedHistoryId.value = item.id;
  error.value = '';
  try {
    const detail = await fetchHistoryDetail(item.id);
    await applyBacktestPayload(detail, true);
  } catch (requestError) {
    error.value = requestError?.response?.data?.detail || requestError?.message || '加载回测详情失败';
  }
}

async function toggleCompareItem(item) {
  if (compareIds.value.includes(item.id)) {
    compareIds.value = compareIds.value.filter((id) => id !== item.id);
    compareResults.value = compareResults.value.filter((detail) => detail.id !== item.id);
    await nextTick();
    renderCompareChart();
    return;
  }

  if (compareIds.value.length >= 4) {
    error.value = '最多同时对比 4 组回测结果';
    return;
  }

  try {
    const detail = await fetchHistoryDetail(item.id);
    compareIds.value = [...compareIds.value, item.id];
    compareResults.value = [...compareResults.value, detail];
    await nextTick();
    renderCompareChart();
  } catch (requestError) {
    error.value = requestError?.response?.data?.detail || requestError?.message || '加载对比详情失败';
  }
}

async function deleteHistoryItem(resultId) {
  try {
    await api.deleteBacktestResult(resultId);
    historyDetailCache.delete(resultId);
    compareIds.value = compareIds.value.filter((id) => id !== resultId);
    compareResults.value = compareResults.value.filter((detail) => detail.id !== resultId);
    if (selectedHistoryId.value === resultId) {
      selectedHistoryId.value = null;
    }
    await loadBacktestHistory();
    await nextTick();
    renderCompareChart();
  } catch (requestError) {
    error.value = requestError?.response?.data?.detail || requestError?.message || '删除回测记录失败';
  }
}

watch(() => config.instType, () => {
  ensureSelectedSymbol();
});

watch(() => config.strategy, () => {
  initializeStrategyParams();
});

watch(() => scanConfig.metric, () => {
  scanResult.metricLabel = METRIC_LABELS[scanConfig.metric] || scanConfig.metric;
});

watch(() => scanConfig.xParam, () => {
  if (scanConfig.yParam === scanConfig.xParam) {
    scanConfig.yParam = secondaryScanParams.value[0]?.name || '';
  }
});

watch(activeOverlayIndicators, async () => {
  await nextTick();
  renderKlineChart();
}, { deep: true });

watch(activeSecondaryIndicator, async () => {
  await nextTick();
  renderKlineChart();
});

watch(compareScaleMode, async () => {
  await nextTick();
  renderCompareChart();
});

watch(bottomTab, async () => {
  await nextTick();
  if (bottomTab.value === 'scan') {
    renderScanHeatmap();
  }
  if (bottomTab.value === 'history') {
    renderCompareChart();
  }
});

onMounted(async () => {
  await Promise.all([
    loadSymbols(),
    loadStrategies(),
    loadBacktestHistory(),
  ]);

  syncIndicatorSelections(false);

  window.addEventListener('resize', resizeAllCharts);
});

onUnmounted(() => {
  window.removeEventListener('resize', resizeAllCharts);
  disposeAllCharts();
});
</script>
<style scoped src="../assets/styles/views/backtest-view.css"></style>
