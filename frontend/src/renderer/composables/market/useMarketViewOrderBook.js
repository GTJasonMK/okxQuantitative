import { computed, reactive, watch } from 'vue';

const ORDERBOOK_WALL_MARKER_LIMIT = 2;
const DEPTH_CHART_VIEWBOX_WIDTH = 960;
const DEPTH_CHART_VIEWBOX_HEIGHT = 280;
const DEPTH_CHART_PADDING_LEFT = 18;
const DEPTH_CHART_PADDING_RIGHT = 18;
const DEPTH_CHART_PADDING_TOP = 16;
const DEPTH_CHART_PADDING_BOTTOM = 34;

const formatSignatureNumber = (value, digits = 4) => {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return 'na';
  }
  return numeric.toFixed(digits);
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
  let step = 1;

  if (normalized <= 1.5) {
    step = 1;
  } else if (normalized <= 3) {
    step = 2;
  } else if (normalized <= 7) {
    step = 5;
  } else {
    step = 10;
  }

  return step * magnitude;
};

const canScrollElement = (element, deltaY) => {
  if (!element || !(element instanceof HTMLElement)) {
    return false;
  }
  if (element.scrollHeight <= element.clientHeight + 1) {
    return false;
  }
  if (deltaY < 0) {
    return element.scrollTop > 0;
  }
  if (deltaY > 0) {
    return element.scrollTop + element.clientHeight < element.scrollHeight - 1;
  }
  return false;
};

export const useMarketViewOrderBook = ({
  ORDERBOOK_DEPTH_MIN,
  ORDERBOOK_DEPTH_MAX,
  activeSymbol,
  activeOrderBook,
  activeBaseCurrency,
  activeTicker,
  orderBookGrouping,
  orderBookDepthLimit,
  orderBookDepthInput,
  orderBookViewMode,
  orderBookPanelActive,
  settingsLoaded,
  debouncedSave,
  loadOrderBook,
  startOrderBookPolling,
  formatPrice,
  formatTradeSize,
  formatPercentValue,
  normalizeMonitorSymbol,
  depthInspectorScrollRef,
  chartInspectorPanelRef,
  depthChartCanvasRef,
  clampOrderBookDepthLimit,
}) => {
  const depthChartHover = reactive({
    visible: false,
    left: 0,
    top: 0,
    xSvg: 0,
    ySvg: 0,
    side: '',
    price: 0,
    size: 0,
    total: 0,
    distancePercent: 0,
  });

  const orderBookViewTabs = [
    { key: 'table', label: '订单表' },
    { key: 'depth', label: '深度图' },
  ];
  const orderBookGroupingOptions = [
    { value: 1, label: '原始' },
    { value: 2, label: 'x2' },
    { value: 4, label: 'x4' },
    { value: 8, label: 'x8' },
  ];
  const orderBookDepthOptions = [
    { value: 20, label: '20档' },
    { value: 50, label: '50档' },
    { value: 100, label: '100档' },
    { value: 200, label: '200档' },
    { value: 500, label: '500档' },
  ];

  const applyOrderBookDepthLimit = (value) => {
    const nextDepth = clampOrderBookDepthLimit(value);
    orderBookDepthInput.value = String(nextDepth);
    if (nextDepth === orderBookDepthLimit.value) {
      return;
    }
    orderBookDepthLimit.value = nextDepth;
  };

  const commitCustomOrderBookDepthLimit = () => {
    applyOrderBookDepthLimit(orderBookDepthInput.value);
  };

  const customOrderBookDepthActive = computed(() => (
    !orderBookDepthOptions.some(option => option.value === orderBookDepthLimit.value)
  ));

  const activeOrderBookRawAsks = computed(() => (
    Array.isArray(activeOrderBook.value?.asks) ? activeOrderBook.value.asks : []
  ));
  const activeOrderBookRawBids = computed(() => (
    Array.isArray(activeOrderBook.value?.bids) ? activeOrderBook.value.bids : []
  ));

  const activeOrderBookMidPrice = computed(() => (
    Number(activeOrderBook.value?.mid_price) > 0
      ? Number(activeOrderBook.value.mid_price)
      : Number(activeTicker.value?.last) || 0
  ));

  const activeOrderBookBaseTickSize = computed(() => {
    const prices = [
      ...activeOrderBookRawAsks.value.map(level => Number(level?.price) || 0),
      ...activeOrderBookRawBids.value.map(level => Number(level?.price) || 0),
    ].filter(price => price > 0).sort((left, right) => left - right);

    let minDiff = Number.POSITIVE_INFINITY;
    for (let index = 1; index < prices.length; index += 1) {
      const diff = prices[index] - prices[index - 1];
      if (diff > 0 && diff < minDiff) {
        minDiff = diff;
      }
    }

    if (Number.isFinite(minDiff) && minDiff > 0) {
      return minDiff;
    }

    const spread = Math.abs((Number(activeOrderBook.value?.best_ask) || 0) - (Number(activeOrderBook.value?.best_bid) || 0));
    if (spread > 0) {
      return spread;
    }

    const latestPrice = activeOrderBookMidPrice.value;
    if (latestPrice >= 1000) return 0.1;
    if (latestPrice >= 100) return 0.01;
    if (latestPrice >= 1) return 0.001;
    return 0.0001;
  });

  const activeOrderBookGroupingStep = computed(() => (
    activeOrderBookBaseTickSize.value * Math.max(1, Number(orderBookGrouping.value) || 1)
  ));

  const aggregateOrderBookLevels = (levels, side = 'ask') => {
    const normalizedLevels = Array.isArray(levels) ? levels : [];
    const groupingStep = activeOrderBookGroupingStep.value;
    const stepPrecision = Math.min(
      10,
      Math.max(
        getNumericPrecision(groupingStep),
        getNumericPrecision(activeOrderBookBaseTickSize.value),
      ),
    );
    const step = Number.isFinite(groupingStep) && groupingStep > 0 ? groupingStep : 0;

    const toBucketPrice = (price) => {
      if (step <= 0) {
        return price;
      }
      const scaled = side === 'bid'
        ? Math.floor(price / step) * step
        : Math.ceil(price / step) * step;
      return Number(scaled.toFixed(stepPrecision));
    };

    const groupedMap = new Map();
    normalizedLevels.forEach((level) => {
      const price = Number(level?.price) || 0;
      const size = Number(level?.size) || 0;
      const orderCount = Number(level?.order_count) || 0;
      if (price <= 0 || size < 0) {
        return;
      }

      const bucketPrice = toBucketPrice(price);
      const existing = groupedMap.get(bucketPrice) || {
        price: bucketPrice,
        size: 0,
        total: 0,
        order_count: 0,
      };

      existing.size += size;
      existing.order_count += orderCount;
      groupedMap.set(bucketPrice, existing);
    });

    const groupedLevels = [...groupedMap.values()]
      .sort((left, right) => (
        side === 'bid'
          ? right.price - left.price
          : left.price - right.price
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

  const activeOrderBookBidsGrouped = computed(() => (
    aggregateOrderBookLevels(activeOrderBookRawBids.value, 'bid')
  ));
  const activeOrderBookAsksGrouped = computed(() => (
    aggregateOrderBookLevels(activeOrderBookRawAsks.value, 'ask')
  ));
  const activeOrderBookBidsDisplay = computed(() => activeOrderBookBidsGrouped.value);

  const activeOrderBookAssetLabel = computed(() => (
    activeBaseCurrency.value
    || normalizeMonitorSymbol(activeSymbol.value)?.split('-')?.[0]
    || '--'
  ));

  const activeOrderBookPrecisionLabel = computed(() => {
    const step = Number(activeOrderBookGroupingStep.value) || 0;
    if (!Number.isFinite(step) || step <= 0) {
      return '精度 --';
    }
    return `精度 ${formatPrice(step)}`;
  });

  const activeOrderBookGroupingLabel = computed(() => {
    const step = activeOrderBookGroupingStep.value;
    if (!Number.isFinite(step) || step <= 0) {
      return '--';
    }
    return formatPrice(step);
  });

  const activeOrderBookSpreadLabel = computed(() => (
    Number(activeOrderBook.value?.spread) > 0
      ? formatPrice(activeOrderBook.value.spread)
      : '--'
  ));
  const activeOrderBookSpreadPercentLabel = computed(() => (
    Number(activeOrderBook.value?.spread_rate) > 0
      ? formatPercentValue(Number(activeOrderBook.value.spread_rate) * 100, 4)
      : '--'
  ));

  const activeOrderBookMaxSize = computed(() => {
    const sizes = [
      ...activeOrderBookBidsDisplay.value.map(level => Number(level?.size) || 0),
      ...activeOrderBookAsksGrouped.value.map(level => Number(level?.size) || 0),
    ];
    return Math.max(...sizes, 0);
  });

  const getOrderBookLevelSizeRatio = (level) => {
    const size = Number(level?.size) || 0;
    const maxSize = activeOrderBookMaxSize.value;
    if (maxSize <= 0 || size <= 0) {
      return 0;
    }
    return Math.max(4, Math.min(100, (size / maxSize) * 100));
  };

  const activeOrderBookLadderRows = computed(() => {
    const bids = activeOrderBookBidsDisplay.value;
    const asks = activeOrderBookAsksGrouped.value;
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
  });

  const selectOrderBookWallLevels = (levels) => {
    const normalizedLevels = Array.isArray(levels) ? levels : [];
    if (normalizedLevels.length === 0) {
      return [];
    }

    const sortedBySize = [...normalizedLevels].sort((left, right) => (right.size || 0) - (left.size || 0));
    const sizeValues = sortedBySize
      .map(level => Number(level?.size) || 0)
      .filter(size => size > 0)
      .sort((left, right) => left - right);

    if (sizeValues.length === 0) {
      return [];
    }

    const median = sizeValues[Math.floor(sizeValues.length / 2)] || sizeValues[0];
    const average = sizeValues.reduce((sum, value) => sum + value, 0) / sizeValues.length;
    const threshold = Math.max(median * 2, average * 1.75);
    const selected = sortedBySize.filter(level => (Number(level?.size) || 0) >= threshold);
    const fallback = selected.length > 0 ? selected : sortedBySize.slice(0, ORDERBOOK_WALL_MARKER_LIMIT);
    return fallback
      .slice(0, ORDERBOOK_WALL_MARKER_LIMIT)
      .sort((left, right) => left.price - right.price);
  };

  const activeOrderBookBidWalls = computed(() => (
    selectOrderBookWallLevels(activeOrderBookBidsGrouped.value)
  ));
  const activeOrderBookAskWalls = computed(() => (
    selectOrderBookWallLevels(activeOrderBookAsksGrouped.value)
  ));
  const activeOrderBookBidWallSet = computed(() => new Set(
    activeOrderBookBidWalls.value.map(level => String(level.price)),
  ));
  const activeOrderBookAskWallSet = computed(() => new Set(
    activeOrderBookAskWalls.value.map(level => String(level.price)),
  ));

  const isOrderBookWall = (level, side = 'bid') => {
    const priceKey = String(level?.price ?? '');
    if (!priceKey) {
      return false;
    }
    return side === 'bid'
      ? activeOrderBookBidWallSet.value.has(priceKey)
      : activeOrderBookAskWallSet.value.has(priceKey);
  };

  const activeOrderBookLevelCount = computed(() => (
    activeOrderBookAsksGrouped.value.length + activeOrderBookBidsGrouped.value.length
  ));

  const activeOrderBookMaxTotal = computed(() => {
    const askTotal = activeOrderBookAsksGrouped.value[activeOrderBookAsksGrouped.value.length - 1]?.total || 0;
    const bidTotal = activeOrderBookBidsGrouped.value[activeOrderBookBidsGrouped.value.length - 1]?.total || 0;
    const fallbackAsk = activeOrderBookAsksGrouped.value[activeOrderBookAsksGrouped.value.length - 1]?.total || 0;
    const fallbackBid = activeOrderBookBidsDisplay.value[activeOrderBookBidsDisplay.value.length - 1]?.total || 0;
    return Math.max(askTotal, bidTotal, fallbackAsk, fallbackBid, 0);
  });

  const activeDepthChartBids = computed(() => (
    activeOrderBookBidsGrouped.value
      .map(level => ({
        price: Number(level?.price) || 0,
        size: Number(level?.size) || 0,
        total: Number(level?.total) || 0,
      }))
      .filter(level => level.price > 0 && level.total >= 0)
      .sort((left, right) => left.price - right.price)
  ));
  const activeDepthChartAsks = computed(() => (
    activeOrderBookAsksGrouped.value
      .map(level => ({
        price: Number(level?.price) || 0,
        size: Number(level?.size) || 0,
        total: Number(level?.total) || 0,
      }))
      .filter(level => level.price > 0 && level.total >= 0)
      .sort((left, right) => left.price - right.price)
  ));

  const hideDepthChartHover = () => {
    depthChartHover.visible = false;
  };

  const activeOrderBookDepthChart = computed(() => {
    const bids = activeDepthChartBids.value;
    const asks = activeDepthChartAsks.value;
    if (bids.length === 0 && asks.length === 0) {
      return null;
    }

    const latestPrice = activeOrderBookMidPrice.value > 0 ? activeOrderBookMidPrice.value : 0;
    const bestBid = Number(activeOrderBook.value?.best_bid) || 0;
    const bestAsk = Number(activeOrderBook.value?.best_ask) || 0;
    const priceCandidates = [
      ...bids.map(level => level.price),
      ...asks.map(level => level.price),
    ];
    if (latestPrice > 0) {
      priceCandidates.push(latestPrice);
    }

    const rawMinPrice = Math.min(...priceCandidates);
    const rawMaxPrice = Math.max(...priceCandidates);
    const centerPrice = latestPrice > 0
      ? latestPrice
      : (
        bestBid > 0 && bestAsk > 0
          ? (bestBid + bestAsk) / 2
          : (rawMinPrice + rawMaxPrice) / 2
      );
    const bestSpread = Math.abs(bestAsk - bestBid);
    const basePriceStep = Math.max(
      Number(activeOrderBookGroupingStep.value) || 0,
      Number(activeOrderBookBaseTickSize.value) || 0,
      bestSpread,
      centerPrice > 0 ? centerPrice * 0.000001 : 0,
      0.00000001,
    );
    const visibleLevelCount = Math.max(bids.length, asks.length, 6);
    const fallbackSpan = Math.max(
      basePriceStep * visibleLevelCount * 2,
      bestSpread * 24,
      centerPrice > 0 ? centerPrice * 0.00008 : 1,
      1e-6,
    );
    const radius = Math.max(
      rawMaxPrice - centerPrice,
      centerPrice - rawMinPrice,
      fallbackSpan / 2,
      1e-6,
    );
    const minPrice = centerPrice - radius;
    const maxPrice = centerPrice + radius;
    const priceSpan = Math.max(maxPrice - minPrice, 1e-6);
    const maxDepth = Math.max(
      activeOrderBookMaxTotal.value,
      ...bids.map(level => level.total),
      ...asks.map(level => level.total),
      1,
    );

    const chartLeft = DEPTH_CHART_PADDING_LEFT;
    const chartTop = DEPTH_CHART_PADDING_TOP;
    const chartWidth = DEPTH_CHART_VIEWBOX_WIDTH - DEPTH_CHART_PADDING_LEFT - DEPTH_CHART_PADDING_RIGHT;
    const chartHeight = DEPTH_CHART_VIEWBOX_HEIGHT - DEPTH_CHART_PADDING_TOP - DEPTH_CHART_PADDING_BOTTOM;
    const baselineY = chartTop + chartHeight;
    const toX = (price) => chartLeft + ((price - minPrice) / priceSpan) * chartWidth;
    const toY = (total) => chartTop + chartHeight - (Math.max(total, 0) / maxDepth) * chartHeight;
    const bidPoints = bids.map(level => ({
      x: toX(level.price),
      y: toY(level.total),
      side: 'bid',
      price: level.price,
      size: level.size,
      total: level.total,
    }));
    const askPoints = asks.map(level => ({
      x: toX(level.price),
      y: toY(level.total),
      side: 'ask',
      price: level.price,
      size: level.size,
      total: level.total,
    }));
    const centerX = toX(Number.isFinite(centerPrice) && centerPrice > 0 ? centerPrice : minPrice);
    const bidWallPrices = new Set(activeOrderBookBidWalls.value.map(level => String(level.price)));
    const askWallPrices = new Set(activeOrderBookAskWalls.value.map(level => String(level.price)));
    const bidWallPoints = bidPoints.filter(point => bidWallPrices.has(String(point.price)));
    const askWallPoints = askPoints.filter(point => askWallPrices.has(String(point.price)));
    const tickInterval = getNiceDepthTickInterval(maxDepth);
    const yTicks = [];
    for (let value = tickInterval; value <= maxDepth + 1e-9; value += tickInterval) {
      yTicks.push({
        value,
        y: toY(value),
        label: formatTradeSize(value),
      });
    }

    return {
      viewBox: `0 0 ${DEPTH_CHART_VIEWBOX_WIDTH} ${DEPTH_CHART_VIEWBOX_HEIGHT}`,
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
      bidDepthLabel: formatTradeSize(bids[bids.length - 1]?.total || 0),
      askDepthLabel: formatTradeSize(asks[asks.length - 1]?.total || 0),
      bestBidX: bestBid > 0 ? toX(bestBid) : centerX,
      bestAskX: bestAsk > 0 ? toX(bestAsk) : centerX,
      hoverPoints: [...bidPoints, ...askPoints],
      bidWallPoints,
      askWallPoints,
      yTicks,
    };
  });

  const activePrimaryBidWall = computed(() => activeOrderBookBidWalls.value[0] || null);
  const activePrimaryAskWall = computed(() => activeOrderBookAskWalls.value[0] || null);

  const resolveDepthScrollContainer = () => {
    const innerContainer = depthInspectorScrollRef.value;
    if (innerContainer instanceof HTMLElement && innerContainer.scrollHeight > innerContainer.clientHeight + 1) {
      return innerContainer;
    }

    const panelContainer = chartInspectorPanelRef.value;
    if (panelContainer instanceof HTMLElement && panelContainer.scrollHeight > panelContainer.clientHeight + 1) {
      return panelContainer;
    }

    return null;
  };

  const handleDepthPanelWheel = (event) => {
    const container = resolveDepthScrollContainer();
    if (!container) {
      return;
    }

    const target = event.target instanceof Element ? event.target : null;
    const sideScroller = target?.closest('.orderbook-ladder-body');
    if (sideScroller instanceof HTMLElement && canScrollElement(sideScroller, event.deltaY)) {
      return;
    }

    if (!canScrollElement(container, event.deltaY)) {
      return;
    }

    event.preventDefault();
    container.scrollTop += event.deltaY;
  };

  const handleDepthChartPointerMove = (event) => {
    const chart = activeOrderBookDepthChart.value;
    const canvas = depthChartCanvasRef.value;
    if (!chart || !canvas || !Array.isArray(chart.hoverPoints) || chart.hoverPoints.length === 0) {
      hideDepthChartHover();
      return;
    }

    const rect = canvas.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) {
      hideDepthChartHover();
      return;
    }

    const pointerX = event.clientX - rect.left;
    const pointerY = event.clientY - rect.top;
    const ratioX = DEPTH_CHART_VIEWBOX_WIDTH / rect.width;
    const ratioY = DEPTH_CHART_VIEWBOX_HEIGHT / rect.height;
    const svgX = pointerX * ratioX;
    const svgY = pointerY * ratioY;

    let nearestPoint = null;
    let nearestDistance = Number.POSITIVE_INFINITY;
    chart.hoverPoints.forEach((point) => {
      const dx = point.x - svgX;
      const dy = (point.y - svgY) * 0.35;
      const distance = Math.abs(dx) + Math.abs(dy);
      if (distance < nearestDistance) {
        nearestDistance = distance;
        nearestPoint = point;
      }
    });

    if (!nearestPoint) {
      hideDepthChartHover();
      return;
    }

    const pointLeft = (nearestPoint.x / DEPTH_CHART_VIEWBOX_WIDTH) * rect.width;
    const pointTop = (nearestPoint.y / DEPTH_CHART_VIEWBOX_HEIGHT) * rect.height;
    const referencePrice = activeOrderBookMidPrice.value || nearestPoint.price || 0;
    const distancePercent = referencePrice > 0
      ? ((nearestPoint.price - referencePrice) / referencePrice) * 100
      : 0;

    depthChartHover.visible = true;
    depthChartHover.side = nearestPoint.side;
    depthChartHover.price = nearestPoint.price;
    depthChartHover.size = nearestPoint.size;
    depthChartHover.total = nearestPoint.total;
    depthChartHover.distancePercent = distancePercent;
    depthChartHover.xSvg = nearestPoint.x;
    depthChartHover.ySvg = nearestPoint.y;
    depthChartHover.left = Math.max(16, Math.min(rect.width - 116, pointLeft + 12));
    depthChartHover.top = Math.max(16, Math.min(rect.height - 82, pointTop - 54));
  };

  const activeOrderBookSignature = computed(() => {
    const book = activeOrderBook.value;
    if (!book) {
      return 'empty';
    }

    const encodeLevels = (levels) => (
      (Array.isArray(levels) ? levels : [])
        .slice(0, 6)
        .map(level => [
          formatSignatureNumber(level?.price, 8),
          formatSignatureNumber(level?.size, 8),
          formatSignatureNumber(level?.total, 8),
        ].join(':'))
        .join(',')
    );

    return [
      formatSignatureNumber(book.best_ask, 8),
      formatSignatureNumber(book.best_bid, 8),
      formatSignatureNumber(book.spread, 8),
      formatSignatureNumber(book.spread_rate, 10),
      book.timestamp || 0,
      encodeLevels(book.asks),
      encodeLevels(book.bids),
    ].join('|');
  });

  const currentInspectorTabLabel = computed(() => '盘口');
  const currentInspectorTriggerMeta = computed(() => (
    `${orderBookViewMode.value === 'depth' ? '深度图' : '订单表'} / ${activeOrderBookLevelCount.value} 档`
  ));

  watch(orderBookViewMode, () => {
    hideDepthChartHover();
  });

  watch(orderBookGrouping, () => {
    hideDepthChartHover();
  });

  watch(orderBookDepthLimit, async () => {
    orderBookDepthInput.value = String(orderBookDepthLimit.value);
    if (settingsLoaded.value) {
      debouncedSave();
    }
    hideDepthChartHover();
    if (!activeSymbol.value) {
      return;
    }
    await loadOrderBook(activeSymbol.value);
    if (orderBookPanelActive.value) {
      await startOrderBookPolling();
    }
  });

  watch(activeOrderBookSignature, () => {
    hideDepthChartHover();
  });

  return {
    ORDERBOOK_DEPTH_MIN,
    ORDERBOOK_DEPTH_MAX,
    depthChartHover,
    orderBookViewTabs,
    orderBookGroupingOptions,
    orderBookDepthOptions,
    applyOrderBookDepthLimit,
    commitCustomOrderBookDepthLimit,
    customOrderBookDepthActive,
    activeOrderBookAssetLabel,
    activeOrderBookPrecisionLabel,
    activeOrderBookGroupingLabel,
    activeOrderBookSpreadLabel,
    activeOrderBookSpreadPercentLabel,
    activeOrderBookLevelCount,
    activeOrderBookLadderRows,
    activeOrderBookDepthChart,
    activePrimaryBidWall,
    activePrimaryAskWall,
    getOrderBookLevelSizeRatio,
    isOrderBookWall,
    handleDepthPanelWheel,
    handleDepthChartPointerMove,
    hideDepthChartHover,
    currentInspectorTabLabel,
    currentInspectorTriggerMeta,
  };
};
