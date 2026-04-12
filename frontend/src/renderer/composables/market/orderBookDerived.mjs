import { buildDepthChartData } from './orderBookDepthChart.mjs';

const DEFAULT_WALL_MARKER_LIMIT = 2;

const toFiniteNumber = (value, fallback = 0) => {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : fallback;
};

const normalizeStepNumber = (value) => {
  const numeric = toFiniteNumber(value, 0);
  if (!Number.isFinite(numeric) || numeric === 0) {
    return 0;
  }
  return Number(numeric.toPrecision(12));
};

const getNumericPrecision = (value) => {
  const normalized = Number(value);
  if (!Number.isFinite(normalized)) {
    return 0;
  }

  const serialized = normalized.toString().toLowerCase();
  if (serialized.includes('e-')) {
    const exponent = Number(serialized.split('e-')[1]);
    return Number.isFinite(exponent) ? exponent : 0;
  }
  if (!serialized.includes('.')) {
    return 0;
  }
  return serialized.split('.')[1].length;
};

const normalizeLevels = (levels) => {
  if (!Array.isArray(levels)) {
    return [];
  }

  const normalized = [];
  for (const level of levels) {
    const price = toFiniteNumber(level?.price, 0);
    const size = toFiniteNumber(level?.size, 0);
    if (price <= 0 || size < 0) {
      continue;
    }
    normalized.push({
      price,
      size,
      total: toFiniteNumber(level?.total, 0),
      order_count: Math.max(0, Math.round(toFiniteNumber(level?.order_count, 0))),
    });
  }
  return normalized;
};

const resolveBaseTickSize = ({ asks, bids, bestAsk, bestBid, midPrice }) => {
  const prices = [];
  for (const level of [...asks, ...bids]) {
    if (level.price > 0) {
      prices.push(level.price);
    }
  }
  prices.sort((left, right) => left - right);

  let minDiff = Number.POSITIVE_INFINITY;
  for (let index = 1; index < prices.length; index += 1) {
    const diff = prices[index] - prices[index - 1];
    if (diff > 0 && diff < minDiff) {
      minDiff = diff;
    }
  }

  if (Number.isFinite(minDiff) && minDiff > 0) {
    return normalizeStepNumber(minDiff);
  }

  const spread = Math.abs(bestAsk - bestBid);
  if (spread > 0) {
    return normalizeStepNumber(spread);
  }
  if (midPrice >= 1000) return 0.1;
  if (midPrice >= 100) return 0.01;
  if (midPrice >= 1) return 0.001;
  return 0.0001;
};

const toBucketPrice = (price, side, step, precision) => {
  if (!Number.isFinite(step) || step <= 0) {
    return price;
  }

  const scaled = side === 'bid'
    ? Math.floor(price / step) * step
    : Math.ceil(price / step) * step;
  return Number(scaled.toFixed(precision));
};

const aggregateOrderBookLevels = ({ levels, side, groupingStep, baseTickSize }) => {
  const step = Number.isFinite(groupingStep) && groupingStep > 0 ? groupingStep : 0;
  const stepPrecision = Math.min(
    10,
    Math.max(getNumericPrecision(step), getNumericPrecision(baseTickSize)),
  );
  const groupedMap = new Map();

  for (const level of levels) {
    const bucketPrice = toBucketPrice(level.price, side, step, stepPrecision);
    const existing = groupedMap.get(bucketPrice) || {
      price: bucketPrice,
      size: 0,
      total: 0,
      order_count: 0,
    };
    existing.size += level.size;
    existing.order_count += level.order_count;
    groupedMap.set(bucketPrice, existing);
  }

  const groupedLevels = [...groupedMap.values()].sort((left, right) => (
    side === 'bid' ? right.price - left.price : left.price - right.price
  ));

  let cumulativeSize = 0;
  return groupedLevels.map((level) => {
    cumulativeSize += level.size;
    return {
      ...level,
      total: cumulativeSize,
    };
  });
};

const selectOrderBookWallLevels = (levels, wallMarkerLimit) => {
  if (!Array.isArray(levels) || levels.length === 0) {
    return [];
  }

  const sortedBySize = [...levels].sort((left, right) => (right.size || 0) - (left.size || 0));
  const sizeValues = sortedBySize
    .map((level) => toFiniteNumber(level?.size, 0))
    .filter((size) => size > 0)
    .sort((left, right) => left - right);

  if (sizeValues.length === 0) {
    return [];
  }

  const median = sizeValues[Math.floor(sizeValues.length / 2)] || sizeValues[0];
  const average = sizeValues.reduce((sum, value) => sum + value, 0) / sizeValues.length;
  const threshold = Math.max(median * 2, average * 1.75);
  const selected = sortedBySize.filter((level) => toFiniteNumber(level?.size, 0) >= threshold);
  const fallback = selected.length > 0 ? selected : sortedBySize.slice(0, wallMarkerLimit);

  return fallback
    .slice(0, wallMarkerLimit)
    .sort((left, right) => left.price - right.price);
};

const buildLadderRows = (bids, asks) => {
  const rowCount = Math.max(bids.length, asks.length, 0);
  return Array.from({ length: rowCount }, (_, index) => {
    const bid = bids[index] || null;
    const ask = asks[index] || null;
    return {
      key: `${bid?.price ?? 'na'}-${ask?.price ?? 'na'}-${index}`,
      bid,
      ask,
    };
  });
};

const buildWallSet = (levels) => new Set(levels.map((level) => String(level.price)));

export const deriveOrderBookSnapshot = ({
  asks,
  bids,
  bestAsk = 0,
  bestBid = 0,
  midPrice = 0,
  groupingMultiplier = 1,
  wallMarkerLimit = DEFAULT_WALL_MARKER_LIMIT,
  chartSize,
  formatPrice = (value) => String(value),
  formatTradeSize = (value) => String(value),
}) => {
  const normalizedAsks = normalizeLevels(asks);
  const normalizedBids = normalizeLevels(bids);
  const resolvedBestAsk = toFiniteNumber(bestAsk, 0);
  const resolvedBestBid = toFiniteNumber(bestBid, 0);
  const resolvedMidPrice = toFiniteNumber(midPrice, 0);
  const baseTickSize = resolveBaseTickSize({
    asks: normalizedAsks,
    bids: normalizedBids,
    bestAsk: resolvedBestAsk,
    bestBid: resolvedBestBid,
    midPrice: resolvedMidPrice,
  });
  const multiplier = Math.max(1, Math.round(toFiniteNumber(groupingMultiplier, 1)));
  const groupingStep = baseTickSize * multiplier;
  const asksGrouped = aggregateOrderBookLevels({ levels: normalizedAsks, side: 'ask', groupingStep, baseTickSize });
  const bidsGrouped = aggregateOrderBookLevels({ levels: normalizedBids, side: 'bid', groupingStep, baseTickSize });
  const bidWalls = selectOrderBookWallLevels(bidsGrouped, wallMarkerLimit);
  const askWalls = selectOrderBookWallLevels(asksGrouped, wallMarkerLimit);
  const bidWallSet = buildWallSet(bidWalls);
  const askWallSet = buildWallSet(askWalls);
  const maxSize = Math.max(...bidsGrouped.map((level) => level.size), ...asksGrouped.map((level) => level.size), 0);
  const maxTotal = Math.max(bidsGrouped.at(-1)?.total || 0, asksGrouped.at(-1)?.total || 0, 0);

  return {
    baseTickSize,
    groupingStep,
    asksGrouped,
    bidsGrouped,
    bidWalls,
    askWalls,
    bidWallSet,
    askWallSet,
    maxSize,
    maxTotal,
    levelCount: asksGrouped.length + bidsGrouped.length,
    ladderRows: buildLadderRows(bidsGrouped, asksGrouped),
    depthChart: buildDepthChartData({
      bids: bidsGrouped.slice().reverse(),
      asks: asksGrouped,
      bidWallSet,
      askWallSet,
      bestBid: resolvedBestBid,
      bestAsk: resolvedBestAsk,
      midPrice: resolvedMidPrice,
      groupingStep,
      baseTickSize,
      chartSize,
      formatPrice,
      formatTradeSize,
    }),
  };
};
