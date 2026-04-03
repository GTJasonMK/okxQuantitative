export const toFiniteNumber = (value, fallback = 0) => {
  const num = Number(value);
  return Number.isFinite(num) ? num : fallback;
};

export const clamp = (value, min, max) => Math.min(Math.max(value, min), max);

export const normalizeTickerData = (ticker) => {
  if (!ticker) return null;

  const instId = ticker.inst_id || ticker.instId;
  if (!instId) return null;

  return {
    inst_id: instId,
    last: toFiniteNumber(ticker.last),
    last_sz: toFiniteNumber(ticker.last_sz ?? ticker.lastSz),
    ask_px: toFiniteNumber(ticker.ask_px ?? ticker.askPx),
    bid_px: toFiniteNumber(ticker.bid_px ?? ticker.bidPx),
    open_24h: toFiniteNumber(ticker.open_24h ?? ticker.open24h),
    high_24h: toFiniteNumber(ticker.high_24h ?? ticker.high24h),
    low_24h: toFiniteNumber(ticker.low_24h ?? ticker.low24h),
    vol_24h: toFiniteNumber(ticker.vol_24h ?? ticker.vol24h),
    change_24h: toFiniteNumber(ticker.change_24h ?? ticker.change24h),
    timestamp: toFiniteNumber(ticker.timestamp ?? ticker.ts),
  };
};

export const getLatestCandle = (candlesData, symbol) => {
  const candles = candlesData[symbol];
  if (!Array.isArray(candles) || candles.length === 0) return null;
  return candles[candles.length - 1];
};

export const getTickerMetrics = (getTicker, symbol) => {
  const ticker = getTicker(symbol);
  if (!ticker) return null;

  const spread = ticker.ask_px > 0 && ticker.bid_px > 0
    ? Math.max(ticker.ask_px - ticker.bid_px, 0)
    : null;
  const spreadRate = spread !== null && ticker.bid_px > 0
    ? (spread / ticker.bid_px) * 100
    : null;
  const amplitude = ticker.open_24h > 0 && ticker.high_24h > 0 && ticker.low_24h > 0
    ? ((ticker.high_24h - ticker.low_24h) / ticker.open_24h) * 100
    : null;

  return {
    spread,
    spreadRate,
    amplitude,
  };
};

export const getTickerClass = (getTicker, symbol) => {
  const ticker = getTicker(symbol);
  if (!ticker) return '';
  return ticker.change_24h >= 0 ? 'price-up' : 'price-down';
};

export const getPriceFlashClass = (displayPriceMoves, symbol) => {
  const move = displayPriceMoves[symbol];
  if (!move?.flashing || !move.direction) return '';
  return move.direction === 'up' ? 'price-flash-up' : 'price-flash-down';
};

export const formatPrice = (price) => {
  if (!price) return '-';
  if (price >= 1000) return price.toFixed(2);
  if (price >= 1) return price.toFixed(4);
  return price.toFixed(6);
};

export const formatChange = (change) => {
  if (change === null || change === undefined) return '-';
  const sign = change >= 0 ? '+' : '';
  return `${sign}${change.toFixed(2)}%`;
};

export const formatPercentValue = (value, digits = 2) => {
  const num = Number(value);
  if (!Number.isFinite(num)) return '--';
  return `${num.toFixed(digits)}%`;
};

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

export const getRecentTradeKey = (trade, index, suffix = '') => (
  `${trade.trade_id || trade.timestamp}-${trade.side}-${trade.price}-${index}${suffix ? `-${suffix}` : ''}`
);
