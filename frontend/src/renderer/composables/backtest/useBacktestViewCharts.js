import * as echarts from 'echarts';

export function useBacktestViewCharts(deps) {
  const {
    klineChartRef,
    equityChartRef,
    scanHeatmapRef,
    compareChartRef,
    candles,
    config,
    activeOverlayIndicators,
    overlayIndicatorOptions,
    activeSecondaryIndicator,
    secondaryIndicatorOptions,
    trades,
    indicatorMap,
    scanResult,
    compareResults,
    compareScaleMode,
    result,
    equityCurve,
    bottomTab,
    formatAxisTime,
    formatDateTime,
    formatPrice,
    formatMoney,
    safeNum,
    getIndicatorColor,
    ensureChartInstance,
    buildTradeTooltipHtml,
    getTradeIndexByTimestamp,
    buildTradeScatterSeries,
    getActiveSecondaryMeta,
    buildSecondarySeries,
    PRICE_UP_COLOR,
    PRICE_DOWN_COLOR,
    DEFAULT_TEXT,
    MUTED_TEXT,
    GRID_COLOR,
    SURFACE_BG,
    VOLUME_UP,
    VOLUME_DOWN,
  } = deps;
  let klineChart = null;
  let equityChart = null;
  let scanHeatmapChart = null;
  let compareChart = null;

  function renderKlineChart() {
    if (!klineChartRef.value) return;

    klineChart = ensureChartInstance(klineChartRef, klineChart);
    if (!klineChart) return;

    if (candles.value.length === 0) {
      klineChart.clear();
      return;
    }

    const categoryData = candles.value.map((item) => formatAxisTime(item.timestamp));
    const priceData = candles.value.map((item) => [item.open, item.close, item.low, item.high]);
    const volumeData = candles.value.map((item) => ({
      value: item.volume,
      itemStyle: {
        color: item.close >= item.open ? VOLUME_UP : VOLUME_DOWN,
      },
    }));

    const overlaySeries = overlayIndicatorOptions.value
      .filter((item) => activeOverlayIndicators.value.includes(item.key))
      .map((item, index) => ({
        name: item.label,
        type: 'line',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: indicatorMap[item.key] || [],
        showSymbol: false,
        connectNulls: true,
        lineStyle: {
          width: 1.4,
          color: getIndicatorColor(item.key, index),
        },
      }));

    const buySeries = buildTradeScatterSeries('buy');
    const sellSeries = buildTradeScatterSeries('sell');
    const secondaryMeta = getActiveSecondaryMeta();
    const secondarySeries = buildSecondarySeries(secondaryMeta);
    const volumeMaSeries = Array.isArray(indicatorMap.volume_ma)
      ? {
          name: '成交量均线',
          type: 'line',
          xAxisIndex: 1,
          yAxisIndex: 1,
          data: indicatorMap.volume_ma,
          showSymbol: false,
          connectNulls: true,
          lineStyle: { width: 1.2, color: getIndicatorColor('volume_ma') },
        }
      : null;

    const option = {
      backgroundColor: 'transparent',
      animation: false,
      legend: {
        top: 8,
        right: 12,
        textStyle: { color: DEFAULT_TEXT, fontSize: 11 },
        itemWidth: 10,
        itemHeight: 6,
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' },
        backgroundColor: SURFACE_BG,
        borderColor: 'rgba(247, 147, 26, 0.18)',
        textStyle: { color: DEFAULT_TEXT },
        formatter: (params) => {
          const candlePoint = params.find((item) => item.seriesType === 'candlestick');
          const candle = candlePoint ? candles.value[candlePoint.dataIndex] : null;
          if (!candle) return '';

          const lines = [
            `<div style="font-weight:600;margin-bottom:6px">${formatDateTime(candle.timestamp)}</div>`,
            `开: ${formatPrice(candle.open)}`,
            `高: ${formatPrice(candle.high)}`,
            `低: ${formatPrice(candle.low)}`,
            `收: ${formatPrice(candle.close)}`,
            `量: ${formatMoney(candle.volume)}`,
          ];

          params.forEach((item) => {
            if (item.seriesType === 'line' && item.seriesName !== '成交量均线') {
              const value = Array.isArray(item.value) ? item.value[1] : item.value;
              if (value === null || value === undefined || value === '-') return;
              lines.push(`${item.marker}${item.seriesName}: ${safeNum(value).toFixed(4)}`);
            }
            if (item.seriesType === 'bar' && item.seriesName === 'MACD 柱') {
              const value = Array.isArray(item.value) ? item.value[1] : item.value?.value ?? item.value;
              if (value === null || value === undefined) return;
              lines.push(`${item.marker}${item.seriesName}: ${safeNum(value).toFixed(4)}`);
            }
          });

          return lines.join('<br/>');
        },
      },
      axisPointer: {
        link: [{ xAxisIndex: 'all' }],
      },
      grid: [
        { left: 58, right: 22, top: 44, height: '50%' },
        { left: 58, right: 22, top: '63%', height: '10%' },
        { left: 58, right: 22, top: '78%', height: '14%' },
      ],
      xAxis: [
        {
          type: 'category',
          data: categoryData,
          boundaryGap: true,
          axisLine: { lineStyle: { color: GRID_COLOR } },
          axisLabel: { show: false },
          splitLine: { show: false },
        },
        {
          type: 'category',
          gridIndex: 1,
          data: categoryData,
          boundaryGap: true,
          axisLine: { lineStyle: { color: GRID_COLOR } },
          axisLabel: { show: false },
          splitLine: { show: false },
        },
        {
          type: 'category',
          gridIndex: 2,
          data: categoryData,
          boundaryGap: true,
          axisLine: { lineStyle: { color: GRID_COLOR } },
          axisLabel: { color: MUTED_TEXT, fontSize: 10 },
          splitLine: { show: false },
        },
      ],
      yAxis: [
        {
          scale: true,
          axisLine: { lineStyle: { color: GRID_COLOR } },
          axisLabel: { color: MUTED_TEXT, fontSize: 10 },
          splitLine: { lineStyle: { color: 'rgba(38, 51, 65, 0.45)' } },
        },
        {
          scale: true,
          gridIndex: 1,
          axisLine: { show: false },
          axisLabel: { show: false },
          splitLine: { show: false },
        },
        {
          scale: true,
          gridIndex: 2,
          axisLine: { lineStyle: { color: GRID_COLOR } },
          axisLabel: { color: MUTED_TEXT, fontSize: 10 },
          splitLine: { lineStyle: { color: 'rgba(38, 51, 65, 0.35)' } },
          name: secondaryMeta?.label || '副图',
          nameTextStyle: { color: MUTED_TEXT, fontSize: 10, padding: [0, 0, 6, 0] },
        },
      ],
      dataZoom: [
        {
          type: 'inside',
          xAxisIndex: [0, 1, 2],
          start: 60,
          end: 100,
        },
        {
          type: 'slider',
          xAxisIndex: [0, 1, 2],
          bottom: 6,
          height: 16,
          borderColor: 'rgba(255,255,255,0.06)',
          textStyle: { color: MUTED_TEXT },
          fillerColor: 'rgba(247, 147, 26, 0.12)',
          handleStyle: { color: '#F7931A' },
        },
      ],
      series: [
        {
          name: 'K线',
          type: 'candlestick',
          data: priceData,
          itemStyle: {
            color: PRICE_UP_COLOR,
            color0: PRICE_DOWN_COLOR,
            borderColor: PRICE_UP_COLOR,
            borderColor0: PRICE_DOWN_COLOR,
          },
        },
        ...overlaySeries,
        ...(buySeries ? [buySeries] : []),
        ...(sellSeries ? [sellSeries] : []),
        {
          name: '成交量',
          type: 'bar',
          xAxisIndex: 1,
          yAxisIndex: 1,
          data: volumeData,
        },
        ...(volumeMaSeries ? [volumeMaSeries] : []),
        ...secondarySeries,
      ],
    };

    klineChart.setOption(option, true);
  }

  function renderEquityChart() {
    if (!equityChartRef.value) return;

    equityChart = ensureChartInstance(equityChartRef, equityChart);
    if (!equityChart) return;

    if (equityCurve.value.length === 0) {
      equityChart.clear();
      return;
    }

    const option = {
      animation: false,
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'line' },
        backgroundColor: SURFACE_BG,
        borderColor: 'rgba(247, 147, 26, 0.18)',
        textStyle: { color: DEFAULT_TEXT },
        formatter: (params) => {
          const point = params[0];
          if (!point) return '';
          const item = equityCurve.value[point.dataIndex];
          return [
            `<div style="font-weight:600;margin-bottom:6px">${formatDateTime(item.timestamp)}</div>`,
            `总权益: ${formatMoney(item.equity)}`,
            `现金: ${formatMoney(item.cash)}`,
            `持仓市值: ${formatMoney(item.positionValue)}`,
          ].join('<br/>');
        },
      },
      grid: {
        left: 56,
        right: 20,
        top: 24,
        bottom: 28,
      },
      xAxis: {
        type: 'category',
        data: equityCurve.value.map((item) => formatAxisTime(item.timestamp)),
        axisLine: { lineStyle: { color: GRID_COLOR } },
        axisLabel: { color: MUTED_TEXT, fontSize: 10 },
        splitLine: { show: false },
      },
      yAxis: {
        type: 'value',
        scale: true,
        axisLine: { lineStyle: { color: GRID_COLOR } },
        axisLabel: { color: MUTED_TEXT, fontSize: 10 },
        splitLine: { lineStyle: { color: 'rgba(38, 51, 65, 0.35)' } },
      },
      series: [{
        name: '净值',
        type: 'line',
        data: equityCurve.value.map((item) => item.equity),
        showSymbol: false,
        smooth: true,
        lineStyle: { width: 2, color: '#F7931A' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(247, 147, 26, 0.28)' },
            { offset: 1, color: 'rgba(247, 147, 26, 0.02)' },
          ]),
        },
      }],
    };

    equityChart.setOption(option, true);
  }

  function renderScanHeatmap() {
    if (!scanHeatmapRef.value) return;

    scanHeatmapChart = ensureChartInstance(scanHeatmapRef, scanHeatmapChart);
    if (!scanHeatmapChart) return;

    if (!scanResult.heatmap?.points?.length) {
      scanHeatmapChart.clear();
      return;
    }

    const points = scanResult.heatmap.points;
    const metricValues = points.map((item) => safeNum(item[2]));
    const minValue = Math.min(...metricValues);
    const maxValue = Math.max(...metricValues);

    scanHeatmapChart.setOption({
      animation: false,
      tooltip: {
        position: 'top',
        backgroundColor: SURFACE_BG,
        borderColor: 'rgba(247, 147, 26, 0.18)',
        textStyle: { color: DEFAULT_TEXT },
        formatter: (params) => {
          const [xIndex, yIndex, value] = params.value;
          const xValue = scanResult.heatmap.x_values[xIndex];
          const yValue = scanResult.heatmap.y_values[yIndex] ?? '-';
          const axisLabel = scanResult.heatmap.y_key ? `${scanResult.heatmap.x_key}=${xValue}<br/>${scanResult.heatmap.y_key}=${yValue}` : `${scanResult.heatmap.x_key}=${xValue}`;
          return `${axisLabel}<br/>${scanResult.metricLabel}: ${formatScanMetric(value)}`;
        },
      },
      grid: { left: 80, right: 30, top: 16, bottom: 30 },
      xAxis: {
        type: 'category',
        data: scanResult.heatmap.x_values.map((value) => String(value)),
        name: scanResult.heatmap.x_key,
        nameTextStyle: { color: MUTED_TEXT },
        axisLine: { lineStyle: { color: GRID_COLOR } },
        axisLabel: { color: MUTED_TEXT, fontSize: 10 },
      },
      yAxis: {
        type: 'category',
        data: scanResult.heatmap.y_values.length > 0 ? scanResult.heatmap.y_values.map((value) => String(value)) : ['指标'],
        name: scanResult.heatmap.y_key || '',
        nameTextStyle: { color: MUTED_TEXT },
        axisLine: { lineStyle: { color: GRID_COLOR } },
        axisLabel: { color: MUTED_TEXT, fontSize: 10 },
      },
      visualMap: {
        min: minValue,
        max: maxValue,
        calculable: true,
        orient: 'horizontal',
        left: 'center',
        bottom: 0,
        textStyle: { color: MUTED_TEXT },
        inRange: {
          color: ['#233243', '#2f7ed8', '#F7931A', '#f6c85d', '#ef5350'],
        },
      },
      series: [{
        type: 'heatmap',
        data: points,
        label: {
          show: true,
          color: '#ffffff',
          fontSize: 10,
          formatter: (params) => safeNum(params.value[2]).toFixed(1),
        },
        emphasis: {
          itemStyle: {
            borderColor: '#ffffff',
            borderWidth: 1,
          },
        },
      }],
    }, true);
  }

  function renderCompareChart() {
    if (!compareChartRef.value) return;

    compareChart = ensureChartInstance(compareChartRef, compareChart);
    if (!compareChart) return;

    if (compareResults.value.length < 2) {
      compareChart.clear();
      return;
    }

    const timestampSet = new Set();
    compareResults.value.forEach((item) => {
      (item.equityCurve || []).forEach((point) => {
        if (point?.timestamp) {
          timestampSet.add(point.timestamp);
        }
      });
    });

    const axisTimestamps = Array.from(timestampSet).sort((left, right) => left - right);
    if (axisTimestamps.length === 0) {
      compareChart.clear();
      return;
    }

    const normalizedMode = compareScaleMode.value === 'normalized';
    const formatCompareMetric = (value) => (
      normalizedMode ? `${safeNum(value).toFixed(2)}%` : formatMoney(value)
    );

    const compareSeries = compareResults.value.map((item, index) => {
      const firstPoint = (item.equityCurve || []).find((point) => Number.isFinite(safeNum(point?.equity, NaN)));
      const baselineEquity = firstPoint ? safeNum(firstPoint.equity, 0) : 0;
      const equityByTimestamp = new Map(
        (item.equityCurve || [])
          .filter((point) => point?.timestamp)
          .map((point) => [point.timestamp, safeNum(point.equity)])
      );

      return {
        name: `${item.strategyName} #${item.id}`,
        type: 'line',
        showSymbol: false,
        connectNulls: false,
        smooth: true,
        data: axisTimestamps.map((timestamp) => {
          if (!equityByTimestamp.has(timestamp)) {
            return null;
          }
          const equity = equityByTimestamp.get(timestamp);
          if (!normalizedMode) {
            return equity;
          }
          if (baselineEquity <= 0) {
            return null;
          }
          return ((equity - baselineEquity) / baselineEquity) * 100;
        }),
        lineStyle: {
          width: 1.8,
          color: getIndicatorColor(`compare_${index}`, index),
        },
      };
    });

    compareChart.setOption({
      animation: false,
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'line' },
        backgroundColor: SURFACE_BG,
        borderColor: 'rgba(247, 147, 26, 0.18)',
        textStyle: { color: DEFAULT_TEXT },
        formatter: (params) => {
          if (!params?.length) {
            return '';
          }
          const timestamp = axisTimestamps[params[0].dataIndex];
          const lines = [
            `<div style="font-weight:600;margin-bottom:6px">${formatDateTime(timestamp)}</div>`,
          ];
          params.forEach((item) => {
            const value = Array.isArray(item.value) ? item.value[1] : item.value;
            if (value === null || value === undefined || value === '-') {
              return;
            }
            lines.push(`${item.marker}${item.seriesName}: ${formatCompareMetric(value)}`);
          });
          return lines.join('<br/>');
        },
      },
      legend: {
        top: 8,
        textStyle: { color: DEFAULT_TEXT, fontSize: 11 },
      },
      grid: {
        left: 56,
        right: 20,
        top: 40,
        bottom: 30,
      },
      xAxis: {
        type: 'category',
        data: axisTimestamps.map((timestamp) => formatAxisTime(timestamp)),
        axisLine: { lineStyle: { color: GRID_COLOR } },
        axisLabel: { color: MUTED_TEXT, fontSize: 10 },
      },
      yAxis: {
        type: 'value',
        scale: true,
        name: normalizedMode ? '归一化收益' : '权益',
        nameTextStyle: { color: MUTED_TEXT, fontSize: 10, padding: [0, 0, 4, 0] },
        axisLine: { lineStyle: { color: GRID_COLOR } },
        axisLabel: {
          color: MUTED_TEXT,
          fontSize: 10,
          formatter: (value) => (normalizedMode ? `${safeNum(value).toFixed(0)}%` : formatMoney(value)),
        },
        splitLine: { lineStyle: { color: 'rgba(38, 51, 65, 0.35)' } },
      },
      series: compareSeries,
    }, true);
  }

  function renderAllCharts() {
    renderKlineChart();
    renderEquityChart();
    if (bottomTab.value === 'scan') {
      renderScanHeatmap();
    }
    if (bottomTab.value === 'history') {
      renderCompareChart();
    }
  }

  return {
    renderKlineChart,
    renderEquityChart,
    renderScanHeatmap,
    renderCompareChart,
    renderAllCharts,
  };
}
