// API 通信服务
// 封装与后端的所有HTTP请求

import axios from 'axios';
import { createLatestOnly } from '../utils/async';
import { resolveRuntimeBackendUrl } from '../utils/runtimeConfig.mjs';

const inflightGetRequests = new Map();

const buildRequestKey = (config = {}) => {
  const method = String(config.method || 'get').toUpperCase();
  const baseURL = config.baseURL || '';
  const url = config.url || '';
  const params = config.params || {};
  const payload = config.data || null;
  return JSON.stringify({ method, baseURL, url, params, payload });
};

const shouldDedupeRequest = (config = {}) => {
  if (config.dedupe === false) {
    return false;
  }
  const method = String(config.method || 'get').toLowerCase();
  return method === 'get';
};

// 默认后端地址
const DEFAULT_BACKEND_URL = 'http://127.0.0.1:8000';

// 获取后端地址（优先从localStorage读取用户配置）
const getBackendUrl = () => {
  let savedUrl = '';
  try {
    savedUrl = localStorage.getItem('backend-url') || '';
  } catch (e) {
    console.warn('读取后端地址配置失败，使用默认值');
  }
  return resolveRuntimeBackendUrl({
    defaultUrl: DEFAULT_BACKEND_URL,
    savedUrl,
  });
};

// 创建axios实例
const instance = axios.create({
  baseURL: getBackendUrl(),
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 提供更新baseURL的方法（供设置页面调用）
export const updateBaseURL = (url) => {
  if (url) {
    instance.defaults.baseURL = url;
    console.log(`[API] 后端地址已更新: ${url}`);
  }
};

// 获取当前baseURL
export const getBaseURL = () => {
  return instance.defaults.baseURL;
};

// 请求拦截器（生产环境不打日志，避免高频请求拖慢主线程）
instance.interceptors.request.use(
  (config) => config,
  (error) => Promise.reject(error)
);

const request = async (config) => {
  if (!shouldDedupeRequest(config)) {
    return instance.request(config);
  }

  const requestKey = buildRequestKey(config);
  const existingRequest = inflightGetRequests.get(requestKey);
  if (existingRequest) {
    return existingRequest;
  }

  const nextRequest = instance.request(config)
    .finally(() => {
      if (inflightGetRequests.get(requestKey) === nextRequest) {
        inflightGetRequests.delete(requestKey);
      }
    });

  inflightGetRequests.set(requestKey, nextRequest);
  return nextRequest;
};

/**
 * 支持 AbortSignal 的请求方法。
 * 用于和 createLatestOnly 配合，在参数切换时自动取消旧请求。
 * @param {object} config axios 请求配置
 * @param {AbortSignal} [signal] 可选的 AbortSignal
 * @returns {Promise}
 */
const requestWithSignal = async (config, signal) => {
  const mergedConfig = signal
    ? { ...config, signal }
    : config;
  return request(mergedConfig);
};

// 响应拦截器
instance.interceptors.response.use(
  (response) => response.data,
  (error) => {
    // 只对非 abort 错误打日志，避免 createLatestOnly 取消时刷屏
    if (error?.name !== 'AbortError' && error?.code !== 'ERR_CANCELED') {
      console.error('[API Error]', error.message);
    }
    return Promise.reject(error);
  }
);

// 等待后端服务启动（带重试）
export const waitForBackend = async (maxRetries = 10, intervalMs = 1000) => {
  for (let i = 0; i < maxRetries; i++) {
    try {
      await request({ method: 'get', url: '/health' });
      console.log(`[API] 后端连接成功`);
      return true;
    } catch (error) {
      if (i < maxRetries - 1) {
        console.log(`[API] 等待后端启动... (${i + 1}/${maxRetries})`);
        await new Promise(resolve => setTimeout(resolve, intervalMs));
      }
    }
  }
  console.error(`[API] 后端连接失败，已重试 ${maxRetries} 次`);
  return false;
};

// API方法
export const api = {
  // ==================== 系统 ====================

  // 健康检查
  async healthCheck() {
    return request({ method: 'get', url: '/health' });
  },

  // 获取系统状态
  async getSystemStatus() {
    return instance.get('/status');
  },

  async getOkxOutboundTimeline(params = {}) {
    return instance.get('/api/system/okx-outbound-timeline', { params });
  },

  async getTrendResearchInference(params = {}) {
    return instance.get('/api/trend-research/inference', { params });
  },

  async getTrendResearchProcess(params = {}) {
    return instance.get('/api/trend-research/process', { params });
  },

  async getTrendDiagnostics(params = {}, options = {}) {
    return requestWithSignal({
      dedupe: false,
      method: 'get',
      url: '/api/trend-research/diagnostics',
      params,
    }, options.signal);
  },

  async getTrendResearchFactors(instId, params = {}, options = {}) {
    return requestWithSignal({
      dedupe: false,
      method: 'get',
      url: `/api/trend-research/factors/${instId}`,
      params,
    }, options.signal);
  },

  async getTrendResearchFactorSeries(instId, params = {}, options = {}) {
    return requestWithSignal({
      dedupe: false,
      method: 'get',
      url: `/api/trend-research/factor-series/${instId}`,
      params,
    }, options.signal);
  },

  async getTrendResearchFeatureBars(instId, params = {}, options = {}) {
    return requestWithSignal({
      dedupe: false,
      method: 'get',
      url: `/api/trend-research/feature-bars/${instId}`,
      params,
    }, options.signal);
  },

  async getTrendResearchConfig() {
    return instance.get('/api/trend-research/config');
  },

  async getTrendResearchTrainingRun() {
    return instance.get('/api/trend-research/training-run');
  },

  async retrainTrendResearchModel(params = {}) {
    return instance.post('/api/trend-research/model/retrain', null, { params });
  },

  async updateTrendResearchConfig(data) {
    return instance.put('/api/trend-research/config', data);
  },

  async getAssistantStatus() {
    return instance.get('/api/assistant/status');
  },

  async getAssistantAgentTools() {
    return instance.get('/api/assistant/agent/tools');
  },

  async getAssistantAgentSessions(limit = 30) {
    return instance.get('/api/assistant/agent/sessions', {
      params: { limit },
    });
  },

  async createAssistantAgentSession(payload = {}) {
    return instance.post('/api/assistant/agent/sessions', payload);
  },

  async getAssistantAgentSessionDetail(sessionId) {
    return instance.get(`/api/assistant/agent/sessions/${sessionId}`);
  },

  async getAssistantOrderDrafts(params = {}) {
    return instance.get('/api/assistant/agent/order-drafts', {
      params,
    });
  },

  async getAssistantOrderDraft(draftId) {
    return instance.get(`/api/assistant/agent/order-drafts/${draftId}`);
  },

  async getAssistantLevelSnapshots(params = {}) {
    return instance.get('/api/assistant/agent/level-snapshots', {
      params,
    });
  },

  async createAssistantLevelSnapshot(payload = {}) {
    return instance.post('/api/assistant/agent/level-snapshots', payload);
  },

  async getAssistantLevelSnapshot(snapshotId) {
    return instance.get(`/api/assistant/agent/level-snapshots/${snapshotId}`);
  },

  async getAssistantPatrolStatus() {
    return instance.get('/api/assistant/agent/patrol/status');
  },

  async getAssistantPatrolConfig() {
    return instance.get('/api/assistant/agent/patrol/config');
  },

  async updateAssistantPatrolConfig(payload) {
    return instance.put('/api/assistant/agent/patrol/config', payload);
  },

  async runAssistantPatrolNow() {
    return instance.post('/api/assistant/agent/patrol/run-now');
  },

  async getAssistantPatrolRuns(params = {}) {
    return instance.get('/api/assistant/agent/patrol/runs', {
      params,
    });
  },

  async getAssistantPatrolRun(runId) {
    return instance.get(`/api/assistant/agent/patrol/runs/${runId}`);
  },

  async streamAssistantChat(payload, options = {}) {
    return fetch(`${getBaseURL()}/api/assistant/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
      signal: options.signal,
    });
  },

  async runAssistantAgentChat(payload, options = {}) {
    return fetch(`${getBaseURL()}/api/assistant/agent/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
      signal: options.signal,
    });
  },

  async streamAssistantAgentChat(payload, options = {}) {
    return fetch(`${getBaseURL()}/api/assistant/agent/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
      signal: options.signal,
    });
  },

  // ==================== 行情数据 ====================

  // 获取单个交易对行情（支持 signal 取消）
  async getTicker(instId, options = {}) {
    const params = {};
    if (options.instType) params.inst_type = options.instType;
    if (options.fresh === true) params.fresh = true;
    return requestWithSignal({ method: 'get', url: `/api/market/ticker/${instId}`, params }, options.signal);
  },

  // 获取所有行情
  async getTickers(instType = 'SPOT') {
    return instance.get('/api/market/tickers', { params: { inst_type: instType } });
  },

  // 获取最新逐笔成交（支持 signal 取消）
  async getRecentTrades(instId, options = {}) {
    const params = {
      limit: options.limit || 20,
    };
    if (options.instType) params.inst_type = options.instType;
    return requestWithSignal({ method: 'get', url: `/api/market/trades/${instId}`, params }, options.signal);
  },

  // 获取盘口深度（支持 signal 取消）
  async getOrderBook(instId, options = {}) {
    const params = {
      size: options.size || 20,
    };
    if (options.instType) params.inst_type = options.instType;
    return requestWithSignal({ method: 'get', url: `/api/market/orderbook/${instId}`, params }, options.signal);
  },

  // 获取K线数据（支持 signal 取消）
  async getCandles(instId, options = {}) {
    const params = {
      timeframe: options.timeframe || '1H',
      limit: options.limit || 100,
    };
    if (options.startTime) params.start_time = options.startTime;
    if (options.endTime) params.end_time = options.endTime;
    if (options.instType) params.inst_type = options.instType;

    return requestWithSignal({ method: 'get', url: `/api/market/candles/${instId}`, params }, options.signal);
  },

  // ==================== 技术指标 ====================

  // 计算技术指标
  async getIndicators(instId, options = {}) {
    return instance.post('/api/market/indicators', {
      inst_id: instId,
      inst_type: options.instType || 'SPOT',
      timeframe: options.timeframe || '1H',
      indicators: options.indicators || ['ma5', 'ma20', 'macd'],
      limit: options.limit || 100,
    });
  },

  // ==================== 数据同步 ====================

  // 同步K线数据
  async syncCandles(instId, options = {}) {
    return instance.post('/api/market/sync', {
      inst_id: instId,
      timeframe: options.timeframe || '1H',
      days: options.days || 30,
      inst_type: options.instType || 'SPOT',
      mode: options.mode || 'window',
    });
  },

  // 获取同步状态
  async getSyncStatus() {
    return instance.get('/api/market/sync/status');
  },

  async getDataGuardianStatus() {
    return instance.get('/api/market/data-guardian/status');
  },

  async getDataGuardianConfig() {
    return instance.get('/api/market/data-guardian/config');
  },

  async updateDataGuardianConfig(data) {
    return instance.put('/api/market/data-guardian/config', data);
  },

  async runDataGuardianNow() {
    return instance.post('/api/market/data-guardian/run-now');
  },

  async startSyncJob(instId, options = {}) {
    return instance.post('/api/market/sync/jobs', {
      inst_id: instId,
      timeframe: options.timeframe || '1H',
      days: options.days || 30,
      inst_type: options.instType || 'SPOT',
      mode: options.mode || 'window',
    });
  },

  async getSyncJobs(params = {}) {
    return request({
      method: 'get',
      url: '/api/market/sync/jobs',
      params: {
        active_only: !!params.activeOnly,
        limit: params.limit || 20,
        task_ids: params.taskIds || '',
      },
    });
  },

  async getSyncJob(taskId) {
    return instance.get(`/api/market/sync/jobs/${taskId}`);
  },

  // ==================== 交易产品 ====================

  // 获取交易产品列表
  async getInstruments(instType = 'SPOT') {
    return instance.get('/api/market/instruments', { params: { inst_type: instType } });
  },

  // 获取本地已有数据的交易对
  async getAvailableSymbols() {
    return instance.get('/api/market/symbols');
  },

  // 获取关注币种列表
  async getWatchedSymbols() {
    return instance.get('/api/market/watched-symbols');
  },

  // 添加关注币种，并触发全量同步
  async addWatchedSymbol(symbol, options = {}) {
    return instance.post('/api/market/watched-symbols', {
      symbol,
      sync_spot: options.syncSpot ?? true,
      sync_swap: options.syncSwap ?? true,
      archive_all_history: options.archiveAllHistory ?? false,
    });
  },

  // 删除关注币种及其本地数据
  async deleteWatchedSymbol(symbol) {
    return instance.delete(`/api/market/watched-symbols/${encodeURIComponent(symbol)}`);
  },

  // 重新为关注币种发起后台回补
  async repairWatchedSymbol(symbol, options = {}) {
    return instance.post(`/api/market/watched-symbols/${encodeURIComponent(symbol)}/repair`, null, {
      params: {
        sync_spot: options.syncSpot ?? true,
        sync_swap: options.syncSwap ?? true,
      },
    });
  },

  // 获取本地数据库库存目录
  async getDataInventory() {
    return instance.get('/api/market/inventory');
  },

  // 获取单币或全量本地数据健康状态
  async getMarketDataHealth(params = {}) {
    return instance.get('/api/market/data-health', {
      params: {
        symbol: params.symbol || '',
        include_orphans: params.includeOrphans ?? true,
      },
    });
  },

  // 删除单币本地库存；若仍在关注列表中，可一并移除关注
  async deleteInventorySymbol(symbol, options = {}) {
    return instance.delete(`/api/market/inventory/symbols/${encodeURIComponent(symbol)}`, {
      params: {
        remove_watch: !!options.removeWatch,
      },
    });
  },

  // 清理所有未关注孤儿数据
  async deleteOrphanInventory() {
    return instance.delete('/api/market/inventory/orphans');
  },

  // 获取价格提醒列表
  async getPriceAlerts(params = {}) {
    return instance.get('/api/market/alerts', { params });
  },

  // 创建价格提醒
  async createPriceAlert(data) {
    return instance.post('/api/market/alerts', data);
  },

  // 更新价格提醒
  async updatePriceAlert(alertId, data) {
    return instance.patch(`/api/market/alerts/${alertId}`, data);
  },

  // 删除价格提醒
  async deletePriceAlert(alertId) {
    return instance.delete(`/api/market/alerts/${alertId}`);
  },

  // 市场相关性分析
  async getMarketCorrelation(data) {
    return instance.post('/api/market/correlation', data);
  },

  // ==================== 回测 ====================

  // 获取可用策略列表
  async getStrategies() {
    return instance.get('/api/backtest/strategies');
  },

  // 获取策略源代码
  async getStrategySource(strategyId) {
    return instance.get(`/api/backtest/strategies/${strategyId}/source`);
  },

  // 热加载策略
  async reloadStrategies() {
    return instance.post('/api/backtest/strategies/reload');
  },

  // 获取外部策略文件列表
  async listExternalStrategyFiles() {
    return instance.get('/api/backtest/external/files');
  },

  // 读取外部策略文件
  async getExternalStrategyFile(filename) {
    return instance.get(`/api/backtest/external/files/${encodeURIComponent(filename)}`);
  },

  // 保存外部策略文件
  async saveExternalStrategyFile(data) {
    return instance.post('/api/backtest/external/files', {
      filename: data.filename,
      source: data.source || '',
    });
  },

  // 删除外部策略文件
  async deleteExternalStrategyFile(filename) {
    return instance.delete(`/api/backtest/external/files/${encodeURIComponent(filename)}`);
  },

  // 通用策略回测
  async runBacktest(strategyId, params) {
    return instance.post(`/api/backtest/run/${strategyId}`, {
      symbol: params.symbol,
      inst_type: params.instType || 'SPOT',
      timeframe: params.timeframe,
      days: params.days,
      initial_capital: params.initialCapital,
      position_size: params.positionSize || 0.5,
      stop_loss: params.stopLoss || 0.05,
      take_profit: params.takeProfit || 0.10,
      params: params.strategyParams || {},
    });
  },

  // 策略参数扫描
  async scanBacktest(strategyId, params) {
    return instance.post(`/api/backtest/scan/${strategyId}`, {
      symbol: params.symbol,
      inst_type: params.instType || 'SPOT',
      timeframe: params.timeframe,
      days: params.days,
      initial_capital: params.initialCapital,
      position_size: params.positionSize || 0.5,
      stop_loss: params.stopLoss || 0.05,
      take_profit: params.takeProfit || 0.10,
      metric: params.metric || 'total_return',
      base_params: params.baseParams || {},
      scan_params: params.scanParams || {},
      persist_results: params.persistResults || false,
    });
  },

  // 运行双均线策略回测
  async backtestDualMA(params) {
    return instance.post('/api/backtest/dual_ma', {
      symbol: params.symbol,
      timeframe: params.timeframe,
      days: params.days,
      initial_capital: params.initialCapital,
      short_period: params.shortPeriod,
      long_period: params.longPeriod,
      use_ema: params.useEma || false,
      stop_loss: params.stopLoss || 0.05,
      take_profit: params.takeProfit || 0.10,
      position_size: params.positionSize || 0.5,
    });
  },

  // 运行网格策略回测
  async backtestGrid(params) {
    return instance.post('/api/backtest/grid', {
      symbol: params.symbol,
      timeframe: params.timeframe,
      days: params.days,
      initial_capital: params.initialCapital,
      upper_price: params.upperPrice,
      lower_price: params.lowerPrice,
      grid_count: params.gridCount || 10,
      position_size: params.positionSize || 0.8,
      grid_type: params.gridType || 'arithmetic',
    });
  },

  // 获取回测历史
  async getBacktestHistory(params = {}) {
    return instance.get('/api/backtest/history', { params });
  },

  // 获取回测详情（含资金曲线和交易记录）
  async getBacktestDetail(resultId) {
    return instance.get(`/api/backtest/history/${resultId}`);
  },

  // 删除回测记录
  async deleteBacktestResult(resultId) {
    return instance.delete(`/api/backtest/history/${resultId}`);
  },

  // ==================== 配置 ====================

  // 获取OKX配置
  async getOKXConfig() {
    return instance.get('/config/okx');
  },

  // 保存OKX配置（模拟盘 + 实盘两组密钥）
  async saveOKXConfig(config) {
    return instance.post('/config/okx', {
      demo: {
        api_key: config.demo?.apiKey || '',
        secret_key: config.demo?.secretKey || '',
        passphrase: config.demo?.passphrase || '',
      },
      live: {
        api_key: config.live?.apiKey || '',
        secret_key: config.live?.secretKey || '',
        passphrase: config.live?.passphrase || '',
      },
      use_simulated: config.useSimulated,
    });
  },

  // 测试OKX API连接
  async testOKXConnection() {
    return instance.post('/config/okx/test');
  },

  // 获取 AI 助手配置
  async getAssistantConfig() {
    return instance.get('/config/assistant');
  },

  // 保存 AI 助手配置
  async saveAssistantConfig(config) {
    return instance.post('/config/assistant', {
      enabled: !!config.enabled,
      base_url: config.baseUrl || '',
      api_key: config.apiKey || '',
      model: config.model || '',
      provider_name: config.providerName || '',
    });
  },

  // ==================== 交易 ====================

  // 获取交易模块状态
  async getTradingStatus(mode = 'simulated') {
    return instance.get('/api/trading/status', { params: { mode } });
  },

  // 获取风控配置
  async getRiskControlConfig(mode = 'simulated') {
    return instance.get('/api/trading/risk-control', { params: { mode } });
  },

  // 更新风控配置
  async updateRiskControlConfig(data) {
    return instance.put('/api/trading/risk-control', data);
  },

  // 获取风险摘要
  async getRiskSummary(mode = 'simulated') {
    return instance.get('/api/trading/risk-summary', { params: { mode } });
  },

  // 获取账户余额
  async getAccount(mode = 'simulated') {
    return instance.get('/api/trading/account', { params: { mode } });
  },

  // 获取持仓列表
  async getPositions(instType = '', instId = '', mode = 'simulated') {
    const params = { mode };
    if (instType) params.inst_type = instType;
    if (instId) params.inst_id = instId;
    return instance.get('/api/trading/positions', { params });
  },

  // 获取现货持仓（账户中各币种的持仓情况）
  async getSpotHoldings(mode = 'simulated') {
    return instance.get('/api/trading/spot-holdings', { params: { mode } });
  },

  // 获取持仓基础数据（轻量版，不查行情，供前端用WebSocket价格计算）
  async getHoldingsBase(mode = 'simulated') {
    return instance.get('/api/trading/holdings-base', { params: { mode } });
  },

  // 下单
  async placeOrder(data) {
    return instance.post('/api/trading/order', {
      inst_id: data.inst_id,
      side: data.side,
      order_type: data.order_type,
      size: String(data.size),
      price: data.price ? String(data.price) : '',
      td_mode: data.td_mode || 'cash',
      client_order_id: data.client_order_id || '',
      mode: data.mode || 'simulated',
    });
  },

  // 撤单 (DELETE 方式)
  async cancelOrder(orderId, instId, mode = 'simulated') {
    return instance.delete(`/api/trading/order/${orderId}`, {
      params: { inst_id: instId, mode }
    });
  },

  // 撤单 (POST 方式)
  async cancelOrderPost(data) {
    return instance.post('/api/trading/order/cancel', {
      inst_id: data.inst_id,
      order_id: data.order_id || '',
      client_order_id: data.client_order_id || '',
      mode: data.mode || 'simulated',
    });
  },

  // 获取当前委托
  async getOrders(instType = 'SPOT', instId = '', mode = 'simulated') {
    const params = { inst_type: instType, mode };
    if (instId) params.inst_id = instId;
    return instance.get('/api/trading/orders', { params });
  },

  // 获取历史订单
  async getOrderHistory(instType = 'SPOT', instId = '', limit = 50, mode = 'simulated') {
    const params = { inst_type: instType, limit: String(limit), mode };
    if (instId) params.inst_id = instId;
    return instance.get('/api/trading/orders/history', { params });
  },

  // 获取成交记录
  async getFills(instType = 'SPOT', instId = '', limit = 50, mode = 'simulated') {
    const params = { inst_type: instType, limit: String(limit), mode };
    if (instId) params.inst_id = instId;
    return instance.get('/api/trading/fills', { params });
  },

  // 获取最大可交易数量
  async getMaxSize(instId, tdMode = 'cash', mode = 'simulated') {
    return instance.get(`/api/trading/max-size/${instId}`, {
      params: { td_mode: tdMode, mode }
    });
  },

  // ==================== 成本基础 ====================

  // 同步成交记录到本地
  async syncFillsToLocal(mode = 'simulated') {
    return instance.post('/api/trading/fills/sync', null, {
      params: { mode }
    });
  },

  // 获取成本基础
  async getCostBasis(mode = 'simulated', ccy = '') {
    const params = { mode };
    if (ccy) params.ccy = ccy;
    return instance.get('/api/trading/cost-basis', { params });
  },

  // 更新成本基础（手动录入）
  async updateCostBasis(data) {
    return instance.post('/api/trading/cost-basis', {
      ccy: data.ccy,
      avg_cost: data.avgCost,
      mode: data.mode || 'simulated',
    });
  },

  // 获取本地成交记录
  async getLocalFills(mode = 'simulated', ccy = '', instId = '', limit = 100) {
    const params = { mode, limit };
    if (ccy) params.ccy = ccy;
    if (instId) params.inst_id = instId;
    return instance.get('/api/trading/local-fills', { params });
  },

  // 获取成交绩效统计
  async getTradePerformance(mode = 'simulated', instId = '') {
    const params = { mode };
    if (instId) params.inst_id = instId;
    return instance.get('/api/trading/performance', { params });
  },

  // 导出成交绩效 CSV
  async exportTradePerformance(mode = 'simulated', instId = '') {
    const params = { mode };
    if (instId) params.inst_id = instId;
    return instance.get('/api/trading/performance/export', {
      params,
      responseType: 'blob',
      transformResponse: [(data) => data],
    });
  },

  // 重建成交记录表（修复精度问题后需要重新同步）
  async rebuildFillsTable() {
    return instance.post('/api/trading/fills/rebuild');
  },

  // ==================== 实时策略执行 ====================

  // 获取可用于自动执行的策略
  async getLiveAvailableStrategies() {
    return instance.get('/api/live/available-strategies');
  },

  // 启动实时策略
  async startLiveStrategy(data) {
    return instance.post('/api/live/start', {
      strategy_id: data.strategyId,
      symbol: data.symbol,
      timeframe: data.timeframe,
      inst_type: data.instType || 'SPOT',
      initial_capital: data.initialCapital,
      position_size: data.positionSize,
      stop_loss: data.stopLoss,
      take_profit: data.takeProfit,
      check_interval: data.checkInterval,
      params: data.params || {},
    });
  },

  // 停止实时策略
  async stopLiveStrategy() {
    return instance.post('/api/live/stop');
  },

  // 获取实时策略状态
  async getLiveStrategyStatus() {
    return instance.get('/api/live/status');
  },

  // 获取实时策略订单历史
  async getLiveOrders(limit = 20, mode = '') {
    return instance.get('/api/live/orders', {
      params: { limit, mode }
    });
  },

  // ==================== 合约交易 ====================

  // 设置杠杆倍数
  async setContractLeverage(instId, lever, mgnMode = 'cross', posSide = '', mode = 'simulated') {
    return instance.post('/api/trading/contract/leverage', {
      inst_id: instId,
      lever: lever,
      mgn_mode: mgnMode,
      pos_side: posSide,
      mode: mode
    });
  },

  // 获取杠杆倍数
  async getContractLeverage(instId, mgnMode = 'cross', mode = 'simulated') {
    return instance.get(`/api/trading/contract/leverage/${instId}`, {
      params: { mgn_mode: mgnMode, mode }
    });
  },

  // 合约下单
  async placeContractOrder(orderData) {
    return instance.post('/api/trading/contract/order', {
      inst_id: orderData.instId,
      side: orderData.side,
      pos_side: orderData.posSide,
      order_type: orderData.orderType,
      size: orderData.size,
      price: orderData.price || '',
      td_mode: orderData.tdMode || 'cross',
      reduce_only: orderData.reduceOnly || false,
      client_order_id: orderData.clientOrderId || '',
      mode: orderData.mode || 'simulated'
    });
  },

  // 获取合约持仓
  async getContractPositions(instType = 'SWAP', instId = '', mode = 'simulated') {
    return instance.get('/api/trading/contract/positions', {
      params: { inst_type: instType, inst_id: instId, mode }
    });
  },

  // 获取合约最大可开仓数量
  async getContractMaxSize(instId, tdMode = 'cross', mode = 'simulated') {
    return instance.get(`/api/trading/contract/max-size/${instId}`, {
      params: { td_mode: tdMode, mode }
    });
  },

  // 设置持仓模式
  async setPositionMode(posMode, mode = 'simulated') {
    return instance.post('/api/trading/contract/position-mode', null, {
      params: { pos_mode: posMode, mode }
    });
  },

  // 获取账户配置（含持仓模式）
  async getContractAccountConfig(mode = 'simulated') {
    return instance.get('/api/trading/contract/account-config', {
      params: { mode }
    });
  },

  // ==================== 用户偏好设置 ====================

  // 获取所有偏好设置
  async getPreferences() {
    return instance.get('/api/preferences');
  },

  // 获取指定键的偏好设置
  async getPreference(key) {
    return instance.get(`/api/preferences/${key}`);
  },

  // 更新偏好设置（合并更新）
  async updatePreferences(data) {
    return instance.patch('/api/preferences', data);
  },

  // 保存所有偏好设置（完全覆盖）
  async savePreferences(data) {
    return instance.post('/api/preferences', data);
  },

  // ==================== 交易日志 ====================

  // 创建日志条目
  async createJournalEntry(data) {
    return instance.post('/api/journal/entries', data);
  },

  // 查询日志列表
  async getJournalEntries(params = {}) {
    return instance.get('/api/journal/entries', { params });
  },

  // 获取单条日志
  async getJournalEntry(entryId) {
    return instance.get(`/api/journal/entries/${entryId}`);
  },

  // 更新日志
  async updateJournalEntry(entryId, data) {
    return instance.put(`/api/journal/entries/${entryId}`, data);
  },

  // 删除日志
  async deleteJournalEntry(entryId) {
    return instance.delete(`/api/journal/entries/${entryId}`);
  },

  // 获取标签列表
  async getJournalTags() {
    return instance.get('/api/journal/tags');
  },

  // 获取日志统计
  async getJournalStats(params = {}) {
    return instance.get('/api/journal/stats', { params });
  },

  // ==================== 风险指标 ====================

  // 综合风险仪表盘
  async getRiskMetrics(params = {}) {
    return instance.get('/api/risk/metrics', { params });
  },

  // VaR 计算
  async getRiskVar(params = {}) {
    return instance.get('/api/risk/var', { params });
  },

  // 回撤分析
  async getRiskDrawdown(params = {}) {
    return instance.get('/api/risk/drawdown', { params });
  },

  // 滚动指标
  async getRiskRolling(params = {}) {
    return instance.get('/api/risk/rolling', { params });
  },

  // 权益快照
  async getRiskSnapshots(params = {}) {
    return instance.get('/api/risk/snapshots', { params });
  },

  // ==================== 市场扫描 ====================

  // 创建扫描方案
  async createScannerProfile(data) {
    return instance.post('/api/scanner/profiles', data);
  },

  // 获取扫描方案列表
  async getScannerProfiles() {
    return instance.get('/api/scanner/profiles');
  },

  // 更新扫描方案
  async updateScannerProfile(profileId, data) {
    return instance.put(`/api/scanner/profiles/${profileId}`, data);
  },

  // 删除扫描方案
  async deleteScannerProfile(profileId) {
    return instance.delete(`/api/scanner/profiles/${profileId}`);
  },

  // 即时扫描
  async runScan(data) {
    return instance.post('/api/scanner/scan', data);
  },

  // 执行已保存方案
  async runProfileScan(profileId) {
    return instance.post(`/api/scanner/scan/${profileId}`);
  },

  // 获取扫描结果
  async getScannerResults(params = {}) {
    return instance.get('/api/scanner/results', { params });
  },

  // 获取可用条件类型
  async getScannerConditions() {
    return instance.get('/api/scanner/conditions');
  },
};

export { createLatestOnly };

export default api;
