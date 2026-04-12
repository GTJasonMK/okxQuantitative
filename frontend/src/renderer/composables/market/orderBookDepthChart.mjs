const formatSvgNumber = (value) => (
  Number.isFinite(value) ? value.toFixed(2) : '0.00'
);

const buildSvgStepLinePath = (points) => {
  if (!Array.isArray(points) || points.length === 0) {
    return '';
  }

  const commands = [`M ${formatSvgNumber(points[0].x)} ${formatSvgNumber(points[0].y)}`];
  for (let index = 1; index < points.length; index += 1) {
    const previousPoint = points[index - 1];
    const point = points[index];
    commands.push(`L ${formatSvgNumber(point.x)} ${formatSvgNumber(previousPoint.y)}`);
    commands.push(`L ${formatSvgNumber(point.x)} ${formatSvgNumber(point.y)}`);
  }
  return commands.join(' ');
};

const buildSvgStepAreaPath = (points, baselineY) => {
  if (!Array.isArray(points) || points.length === 0) {
    return '';
  }

  const firstPoint = points[0];
  const lastPoint = points[points.length - 1];
  const commands = [
    `M ${formatSvgNumber(firstPoint.x)} ${formatSvgNumber(baselineY)}`,
    `L ${formatSvgNumber(firstPoint.x)} ${formatSvgNumber(firstPoint.y)}`,
  ];

  for (let index = 1; index < points.length; index += 1) {
    const previousPoint = points[index - 1];
    const point = points[index];
    commands.push(`L ${formatSvgNumber(point.x)} ${formatSvgNumber(previousPoint.y)}`);
    commands.push(`L ${formatSvgNumber(point.x)} ${formatSvgNumber(point.y)}`);
  }

  commands.push(`L ${formatSvgNumber(lastPoint.x)} ${formatSvgNumber(baselineY)}`);
  commands.push('Z');
  return commands.join(' ');
};

const getNiceDepthTickInterval = (maxDepth) => {
  if (!Number.isFinite(maxDepth) || maxDepth <= 0) {
    return 1;
  }

  const roughInterval = maxDepth / 3;
  const magnitude = 10 ** Math.floor(Math.log10(roughInterval));
  const normalized = roughInterval / magnitude;

  if (normalized <= 1.5) {
    return magnitude;
  }
  if (normalized <= 3) {
    return 2 * magnitude;
  }
  if (normalized <= 7) {
    return 5 * magnitude;
  }
  return 10 * magnitude;
};

export const buildDepthChartData = ({
  bids,
  asks,
  bidWallSet,
  askWallSet,
  bestBid,
  bestAsk,
  midPrice,
  groupingStep,
  baseTickSize,
  chartSize,
  formatPrice,
  formatTradeSize,
}) => {
  if (bids.length === 0 && asks.length === 0) {
    return null;
  }

  const latestPrice = midPrice > 0 ? midPrice : 0;
  const priceCandidates = [...bids.map((level) => level.price), ...asks.map((level) => level.price)];
  if (latestPrice > 0) {
    priceCandidates.push(latestPrice);
  }

  const rawMinPrice = Math.min(...priceCandidates);
  const rawMaxPrice = Math.max(...priceCandidates);
  const centerPrice = latestPrice > 0
    ? latestPrice
    : (bestBid > 0 && bestAsk > 0 ? (bestBid + bestAsk) / 2 : (rawMinPrice + rawMaxPrice) / 2);
  const bestSpread = Math.abs(bestAsk - bestBid);
  const basePriceStep = Math.max(groupingStep || 0, baseTickSize || 0, bestSpread, centerPrice > 0 ? centerPrice * 0.000001 : 0, 0.00000001);
  const visibleLevelCount = Math.max(bids.length, asks.length, 6);
  const fallbackSpan = Math.max(basePriceStep * visibleLevelCount * 2, bestSpread * 24, centerPrice > 0 ? centerPrice * 0.00008 : 1, 0.000001);
  const radius = Math.max(rawMaxPrice - centerPrice, centerPrice - rawMinPrice, fallbackSpan / 2, 0.000001);
  const minPrice = centerPrice - radius;
  const maxPrice = centerPrice + radius;
  const priceSpan = Math.max(maxPrice - minPrice, 0.000001);
  const maxDepth = Math.max(bids.at(-1)?.total || 0, asks.at(-1)?.total || 0, 1);

  const chartLeft = chartSize.paddingLeft;
  const chartTop = chartSize.paddingTop;
  const chartWidth = chartSize.width - chartSize.paddingLeft - chartSize.paddingRight;
  const chartHeight = chartSize.height - chartSize.paddingTop - chartSize.paddingBottom;
  const baselineY = chartTop + chartHeight;
  const toX = (price) => chartLeft + ((price - minPrice) / priceSpan) * chartWidth;
  const toY = (total) => chartTop + chartHeight - (Math.max(total, 0) / maxDepth) * chartHeight;
  const bidPoints = bids.map((level) => ({ x: toX(level.price), y: toY(level.total), side: 'bid', ...level }));
  const askPoints = asks.map((level) => ({ x: toX(level.price), y: toY(level.total), side: 'ask', ...level }));
  const centerX = toX(Number.isFinite(centerPrice) && centerPrice > 0 ? centerPrice : minPrice);
  const tickInterval = getNiceDepthTickInterval(maxDepth);
  const yTicks = [];

  for (let value = tickInterval; value <= maxDepth + 1e-9; value += tickInterval) {
    yTicks.push({ value, y: toY(value), label: formatTradeSize(value) });
  }

  return {
    viewBox: `0 0 ${chartSize.width} ${chartSize.height}`,
    bidLinePath: buildSvgStepLinePath(bidPoints),
    bidAreaPath: buildSvgStepAreaPath(bidPoints, baselineY),
    askLinePath: buildSvgStepLinePath(askPoints),
    askAreaPath: buildSvgStepAreaPath(askPoints, baselineY),
    centerX,
    baselineY,
    topY: chartTop,
    maxDepthLabel: formatTradeSize(maxDepth),
    leftPriceLabel: formatPrice(minPrice),
    centerPriceLabel: formatPrice(centerPrice),
    rightPriceLabel: formatPrice(maxPrice),
    bidDepthLabel: formatTradeSize(bids.at(-1)?.total || 0),
    askDepthLabel: formatTradeSize(asks.at(-1)?.total || 0),
    bestBidX: bestBid > 0 ? toX(bestBid) : centerX,
    bestAskX: bestAsk > 0 ? toX(bestAsk) : centerX,
    hoverPoints: [...bidPoints, ...askPoints],
    bidWallPoints: bidPoints.filter((point) => bidWallSet.has(String(point.price))),
    askWallPoints: askPoints.filter((point) => askWallSet.has(String(point.price))),
    yTicks,
  };
};
