// 共享格式化工具：数字、价格、时间、符号归一化
// 统一全应用的格式化逻辑，消除各视图/组合式函数中的重复定义

export const toFiniteNumber = (value, fallback = 0) => {
  const num = Number(value);
  return Number.isFinite(num) ? num : fallback;
};

export const clamp = (value, min, max) => Math.min(Math.max(value, min), max);

// 自适应精度价格格式化（>=1000: 2dp, >=1: 4dp, else 6dp）
export const formatPrice = (price) => {
  if (!price) return '-';
  if (price >= 1000) return price.toFixed(2);
  if (price >= 1) return price.toFixed(4);
  return price.toFixed(6);
};

// 带正负号百分比格式化
export const formatChange = (change) => {
  if (change === null || change === undefined) return '-';
  const sign = change >= 0 ? '+' : '';
  return `${sign}${change.toFixed(2)}%`;
};

// 百分比格式化（不带正负号）
export const formatPercentValue = (value, digits = 2) => {
  const num = Number(value);
  if (!Number.isFinite(num)) return '--';
  return `${num.toFixed(digits)}%`;
};

// 带 B/M/K 单位的数量格式化
export const formatTradeSize = (value) => {
  const num = Number(value);
  if (!Number.isFinite(num)) return '--';
  if (num >= 1e9) return `${(num / 1e9).toFixed(2)}B`;
  if (num >= 1e6) return `${(num / 1e6).toFixed(2)}M`;
  if (num >= 1e3) return `${(num / 1e3).toFixed(2)}K`;
  if (num >= 1) return num.toFixed(4);
  if (num === 0) return '0.0000';
  return num.toFixed(6);
};

// 美元金额格式化
export const formatMoney = (value) => `$${toFiniteNumber(value).toFixed(2)}`;

// 简短时间（月/日 时:分）
export const formatTimestamp = (ts) => {
  if (!ts) return '-';
  return new Date(ts).toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
};

// 完整时间（年/月/日 时:分:秒）
export const formatDateTime = (value) => {
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

// 交易对符号归一化（去除 -SWAP 后缀，大写）
export const normalizeMonitorSymbol = (symbol) => {
  if (typeof symbol !== 'string') return '';
  const normalized = symbol.trim().toUpperCase();
  if (!normalized) return '';
  if (normalized.endsWith('-SWAP')) {
    return normalized.slice(0, -5);
  }
  return normalized;
};

// 交易对列表去重归一化
export const normalizeSymbolList = (symbols = []) => (
  [...new Set((symbols || []).map(normalizeMonitorSymbol).filter(Boolean))]
);
