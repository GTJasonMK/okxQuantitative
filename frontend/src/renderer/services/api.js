// API 通信服务
// 封装与后端的所有HTTP请求

import axios from 'axios';

// 默认后端地址
const DEFAULT_BACKEND_URL = 'http://127.0.0.1:8000';

// 获取后端地址（优先从localStorage读取用户配置）
const getBackendUrl = () => {
  try {
    // 统一使用 'backend-url' 键（与 SettingsView.vue 保持一致）
    const saved = localStorage.getItem('backend-url');
    if (saved) {
      return saved;
    }
  } catch (e) {
    console.warn('读取后端地址配置失败，使用默认值');
  }
  return DEFAULT_BACKEND_URL;
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

// 请求拦截器
instance.interceptors.request.use(
  (config) => {
    console.log(`[API] ${config.method?.toUpperCase()} ${config.url}`);
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 响应拦截器
instance.interceptors.response.use(
  (response) => {
    return response.data;
  },
  (error) => {
    console.error('[API Error]', error.message);
    return Promise.reject(error);
  }
);

// 等待后端服务启动（带重试）
export const waitForBackend = async (maxRetries = 10, intervalMs = 1000) => {
  for (let i = 0; i < maxRetries; i++) {
    try {
      await instance.get('/health');
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
    return instance.get('/health');
  },

  // 获取系统状态
  async getSystemStatus() {
    return instance.get('/status');
  },

  // ==================== 行情数据 ====================

  // 获取单个交易对行情
  async getTicker(instId) {
    return instance.get(`/api/market/ticker/${instId}`);
  },

  // 获取所有行情
  async getTickers(instType = 'SPOT') {
    return instance.get('/api/market/tickers', { params: { inst_type: instType } });
  },

  // 获取K线数据
  async getCandles(instId, options = {}) {
    const params = {
      timeframe: options.timeframe || '1H',
      limit: options.limit || 100,
      source: options.source || 'local',
    };
    if (options.startTime) params.start_time = options.startTime;
    if (options.endTime) params.end_time = options.endTime;
    if (options.instType) params.inst_type = options.instType;

    return instance.get(`/api/market/candles/${instId}`, { params });
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
    });
  },

  // 获取同步状态
  async getSyncStatus() {
    return instance.get('/api/market/sync/status');
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

  // 通用策略回测
  async runBacktest(strategyId, params) {
    return instance.post(`/api/backtest/run/${strategyId}`, {
      symbol: params.symbol,
      timeframe: params.timeframe,
      days: params.days,
      initial_capital: params.initialCapital,
      position_size: params.positionSize || 0.5,
      stop_loss: params.stopLoss || 0.05,
      take_profit: params.takeProfit || 0.10,
      params: params.strategyParams || {},
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

  // ==================== 交易 ====================

  // 获取交易模块状态
  async getTradingStatus(mode = 'simulated') {
    return instance.get('/api/trading/status', { params: { mode } });
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

  // 重建成交记录表（修复精度问题后需要重新同步）
  async rebuildFillsTable() {
    return instance.post('/api/trading/fills/rebuild');
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
};

export default api;
