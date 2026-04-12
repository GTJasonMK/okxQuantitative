import { createKlineChartManager } from '@/composables/market/charting/lwc-kline';
import { createChart, disposeChart } from '@/utils/chart';
import {
  buildTimeSeriesPoints,
  createTimeSeriesChartManager,
  toLwcTime,
} from '@/utils/lwcTimeSeriesChart.mjs';

const EQUITY_LINE_COLOR = '#F7931A';
const EQUITY_TOP_COLOR = 'rgba(247, 147, 26, 0.28)';
const EQUITY_BOTTOM_COLOR = 'rgba(247, 147, 26, 0.02)';
const AXIS_TEXT_COLOR = '#8B949E';
const TOOLTIP_TEXT_COLOR = '#C9D1D9';
const GRID_LINE_COLOR = 'rgba(255, 255, 255, 0.08)';

const formatChartTime = (time, formatDateTime) => {
  if (typeof time === 'string') {
    return time;
  }
  return formatDateTime(Number(time) * 1000);
};

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
  } = deps;

  let klineManager = null;
  let equityChart = null;
  let scanHeatmapChart = null;
  let compareChart = null;

  const ensureKlineChart = () => {
    if (!klineChartRef.value) {
      return null;
    }
    if (!klineManager) {
      klineManager = createKlineChartManager({ mode: 'backtest' });
      klineManager.init(klineChartRef.value);
    }
    return klineManager;
  };

  const ensureEquityChart = () => {
    if (!equityChartRef.value) {
      return null;
    }
    if (!equityChart) {
      equityChart = createTimeSeriesChartManager();
      equityChart.init(equityChartRef.value, {
        scaleMargins: { top: 0.08, bottom: 0.18 },
      });
    }
    return equityChart;
  };

  const ensureHeatmapChart = () => {
    if (!scanHeatmapRef.value) {
      return null;
    }
    if (!scanHeatmapChart) {
      scanHeatmapChart = createChart(scanHeatmapRef.value);
    }
    return scanHeatmapChart;
  };

  const ensureCompareChart = () => {
    if (!compareChartRef.value) {
      return null;
    }
    if (!compareChart) {
      compareChart = createTimeSeriesChartManager();
      compareChart.init(compareChartRef.value, {
        scaleMargins: { top: 0.08, bottom: 0.18 },
      });
    }
    return compareChart;
  };

  function renderKlineChart() {
    const chartManager = ensureKlineChart();
    if (!chartManager) {
      return;
    }

    if (candles.value.length === 0) {
      chartManager.setData([], {
        symbol: config?.symbol || '',
        indicators: {},
        fitContent: false,
      });
      chartManager.setMarkers([]);
      return;
    }

    const indicatorFlags = {};
    for (const option of overlayIndicatorOptions.value) {
      if (activeOverlayIndicators.value.includes(option.key)) {
        indicatorFlags[option.key] = true;
      }
    }

    chartManager.setData(candles.value, {
      symbol: config?.symbol || '',
      indicators: indicatorFlags,
      fitContent: true,
    });

    chartManager.setMarkers(
      trades.value.map((trade) => ({
        timestamp: trade.timestamp,
        side: trade.side === 'buy' ? 'buy' : 'sell',
      })),
    );
  }

  function renderEquityChart() {
    const chartManager = ensureEquityChart();
    if (!chartManager) {
      return;
    }

    const points = buildTimeSeriesPoints(equityCurve.value, (item) => ({
      time: item.timestamp,
      value: item.equity,
    }));
    if (points.length === 0) {
      chartManager.clear();
      return;
    }

    const detailsByTime = new Map(
      equityCurve.value
        .map((item) => [toLwcTime(item.timestamp), item])
        .filter(([time]) => time !== null),
    );

    chartManager.setSeries([
      {
        key: 'equity',
        label: '总权益',
        type: 'area',
        color: EQUITY_LINE_COLOR,
        topColor: EQUITY_TOP_COLOR,
        bottomColor: EQUITY_BOTTOM_COLOR,
        data: points,
        valueFormatter: (value) => formatMoney(value),
      },
    ], {
      priceFormatter: (value) => formatMoney(value),
      timeFormatter: (time) => formatChartTime(time, formatDateTime),
      extraTooltipRows: (time) => {
        const detail = detailsByTime.get(time);
        if (!detail) {
          return [];
        }
        return [
          `现金: ${formatMoney(detail.cash)}`,
          `持仓市值: ${formatMoney(detail.positionValue)}`,
        ];
      },
    });
  }

  function renderScanHeatmap() {
    const chart = ensureHeatmapChart();
    if (!chart) {
      return;
    }

    if (!scanResult.heatmap?.points?.length) {
      chart.clear();
      return;
    }

    const points = scanResult.heatmap.points;
    const metricValues = points.map((item) => safeNum(item[2]));
    const minValue = Math.min(...metricValues);
    const maxValue = Math.max(...metricValues);

    chart.setOption({
      animation: false,
      tooltip: {
        position: 'top',
        backgroundColor: 'rgba(15, 17, 21, 0.96)',
        borderColor: 'rgba(247, 147, 26, 0.18)',
        textStyle: { color: TOOLTIP_TEXT_COLOR },
        formatter: (params) => {
          const [xIndex, yIndex, value] = params.value;
          const xValue = scanResult.heatmap.x_values[xIndex];
          const yValue = scanResult.heatmap.y_values[yIndex] ?? '-';
          const axisLabel = scanResult.heatmap.y_key
            ? `${scanResult.heatmap.x_key}=${xValue}<br/>${scanResult.heatmap.y_key}=${yValue}`
            : `${scanResult.heatmap.x_key}=${xValue}`;
          return `${axisLabel}<br/>${scanResult.metricLabel}: ${formatScanMetric(value)}`;
        },
      },
      grid: { left: 80, right: 30, top: 16, bottom: 30 },
      xAxis: {
        type: 'category',
        data: scanResult.heatmap.x_values.map((value) => String(value)),
        name: scanResult.heatmap.x_key,
        nameTextStyle: { color: AXIS_TEXT_COLOR },
        axisLine: { lineStyle: { color: GRID_LINE_COLOR } },
        axisLabel: { color: AXIS_TEXT_COLOR, fontSize: 10 },
      },
      yAxis: {
        type: 'category',
        data: scanResult.heatmap.y_values.length > 0 ? scanResult.heatmap.y_values.map((value) => String(value)) : ['指标'],
        name: scanResult.heatmap.y_key || '',
        nameTextStyle: { color: AXIS_TEXT_COLOR },
        axisLine: { lineStyle: { color: GRID_LINE_COLOR } },
        axisLabel: { color: AXIS_TEXT_COLOR, fontSize: 10 },
      },
      visualMap: {
        min: minValue,
        max: maxValue,
        calculable: true,
        orient: 'horizontal',
        left: 'center',
        bottom: 0,
        textStyle: { color: AXIS_TEXT_COLOR },
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
    const chartManager = ensureCompareChart();
    if (!chartManager) {
      return;
    }

    if (compareResults.value.length < 2) {
      chartManager.clear();
      return;
    }

    const normalizedMode = compareScaleMode.value === 'normalized';
    const series = compareResults.value
      .map((item, index) => {
        const baseline = Number(item.equityCurve?.find((point) => Number.isFinite(safeNum(point?.equity, Number.NaN)))?.equity || 0);
        const points = buildTimeSeriesPoints(item.equityCurve || [], (point) => {
          const equity = safeNum(point?.equity);
          if (normalizedMode) {
            if (baseline <= 0) {
              return null;
            }
            return {
              time: point.timestamp,
              value: ((equity - baseline) / baseline) * 100,
            };
          }
          return {
            time: point.timestamp,
            value: equity,
          };
        });
        if (points.length === 0) {
          return null;
        }
        return {
          key: `compare-${item.id}`,
          label: `${item.strategyName} #${item.id}`,
          type: 'line',
          color: getIndicatorColor(`compare_${index}`, index),
          data: points,
          valueFormatter: (value) => (normalizedMode ? `${safeNum(value).toFixed(2)}%` : formatMoney(value)),
        };
      })
      .filter(Boolean);

    if (series.length < 2) {
      chartManager.clear();
      return;
    }

    chartManager.setSeries(series, {
      priceFormatter: (value) => (normalizedMode ? `${safeNum(value).toFixed(2)}%` : formatMoney(value)),
      timeFormatter: (time) => formatChartTime(time, formatDateTime),
    });
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
    resizeAllCharts() {
      klineManager?.resize();
      equityChart?.resize();
      scanHeatmapChart?.resize();
      compareChart?.resize();
    },
    disposeAllCharts() {
      klineManager?.dispose();
      klineManager = null;
      equityChart?.dispose();
      equityChart = null;
      compareChart?.dispose();
      compareChart = null;
      disposeChart(scanHeatmapChart);
      scanHeatmapChart = null;
    },
  };
}
