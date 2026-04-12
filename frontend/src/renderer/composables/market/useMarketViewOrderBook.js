import { computed, reactive, watch } from 'vue';

import { deriveOrderBookSnapshot } from './orderBookDerived.mjs';

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

const ORDERBOOK_DEPTH_CHART_SIZE = {
  width: DEPTH_CHART_VIEWBOX_WIDTH,
  height: DEPTH_CHART_VIEWBOX_HEIGHT,
  paddingLeft: DEPTH_CHART_PADDING_LEFT,
  paddingRight: DEPTH_CHART_PADDING_RIGHT,
  paddingTop: DEPTH_CHART_PADDING_TOP,
  paddingBottom: DEPTH_CHART_PADDING_BOTTOM,
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

  const activeOrderBookMidPrice = computed(() => (
    Number(activeOrderBook.value?.mid_price) > 0
      ? Number(activeOrderBook.value.mid_price)
      : Number(activeTicker.value?.last) || 0
  ));

  const activeOrderBookDerived = computed(() => deriveOrderBookSnapshot({
    asks: activeOrderBook.value?.asks,
    bids: activeOrderBook.value?.bids,
    bestAsk: Number(activeOrderBook.value?.best_ask) || 0,
    bestBid: Number(activeOrderBook.value?.best_bid) || 0,
    midPrice: activeOrderBookMidPrice.value,
    groupingMultiplier: orderBookGrouping.value,
    wallMarkerLimit: ORDERBOOK_WALL_MARKER_LIMIT,
    chartSize: ORDERBOOK_DEPTH_CHART_SIZE,
    formatPrice,
    formatTradeSize,
  }));

  const activeOrderBookGroupingStep = computed(() => activeOrderBookDerived.value.groupingStep);
  const activeOrderBookBidsGrouped = computed(() => activeOrderBookDerived.value.bidsGrouped);
  const activeOrderBookAsksGrouped = computed(() => activeOrderBookDerived.value.asksGrouped);
  const activeOrderBookBidsDisplay = computed(() => activeOrderBookDerived.value.bidsGrouped);

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

  const activeOrderBookMaxSize = computed(() => activeOrderBookDerived.value.maxSize);

  const getOrderBookLevelSizeRatio = (level) => {
    const size = Number(level?.size) || 0;
    const maxSize = activeOrderBookMaxSize.value;
    if (maxSize <= 0 || size <= 0) {
      return 0;
    }
    return Math.max(4, Math.min(100, (size / maxSize) * 100));
  };

  const activeOrderBookLadderRows = computed(() => activeOrderBookDerived.value.ladderRows);
  const activeOrderBookBidWalls = computed(() => activeOrderBookDerived.value.bidWalls);
  const activeOrderBookAskWalls = computed(() => activeOrderBookDerived.value.askWalls);
  const activeOrderBookBidWallSet = computed(() => activeOrderBookDerived.value.bidWallSet);
  const activeOrderBookAskWallSet = computed(() => activeOrderBookDerived.value.askWallSet);

  const isOrderBookWall = (level, side = 'bid') => {
    const priceKey = String(level?.price ?? '');
    if (!priceKey) {
      return false;
    }
    return side === 'bid'
      ? activeOrderBookBidWallSet.value.has(priceKey)
      : activeOrderBookAskWallSet.value.has(priceKey);
  };

  const activeOrderBookLevelCount = computed(() => activeOrderBookDerived.value.levelCount);
  const hideDepthChartHover = () => {
    depthChartHover.visible = false;
  };

  const activeOrderBookDepthChart = computed(() => activeOrderBookDerived.value.depthChart);

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
