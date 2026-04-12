import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const read = (path) => fs.readFileSync(new URL(path, import.meta.url), 'utf8');

const analyticsView = read('../src/renderer/views/AnalyticsView.vue');
const backtestCharts = read('../src/renderer/composables/backtest/useBacktestViewCharts.js');
const marketCharting = read('../src/renderer/composables/market/useMarketViewCharting.js');
const monacoEditor = read('../src/renderer/components/MonacoEditor.vue');
const strategyCenter = read('../src/renderer/views/StrategyCenterView.vue');
const chartUtils = read('../src/renderer/utils/chart.js');

test('analytics and backtest time-series charts no longer import echarts directly', () => {
  assert.doesNotMatch(analyticsView, /import\s+\*\s+as\s+echarts\s+from\s+'echarts'/);
  assert.doesNotMatch(backtestCharts, /import\s+\*\s+as\s+echarts\s+from\s+'echarts'/);
  assert.match(backtestCharts, /createTimeSeriesChartManager/);
});

test('market charting no longer pulls echarts into the default market route', () => {
  assert.doesNotMatch(marketCharting, /import\s+\*\s+as\s+echarts\s+from\s+'echarts'/);
});

test('strategy center defers heavy child views until the tab is opened', () => {
  assert.match(strategyCenter, /defineAsyncComponent/);
  assert.match(strategyCenter, /import\('\.\/BacktestView\.vue'\)/);
  assert.match(strategyCenter, /import\('\.\/StrategyView\.vue'\)/);
  assert.doesNotMatch(strategyCenter, /import\s+BacktestView\s+from/);
  assert.doesNotMatch(strategyCenter, /import\s+StrategyView\s+from/);
});

test('monaco editor loads its runtime lazily instead of bundling it at module eval time', () => {
  assert.doesNotMatch(monacoEditor, /import\s+\*\s+as\s+monaco\s+from\s+'monaco-editor/);
  assert.match(monacoEditor, /import\('monaco-editor\/esm\/vs\/editor\/editor\.api'\)/);
  assert.match(monacoEditor, /import\('monaco-editor\/esm\/vs\/editor\/editor\.worker\?worker'\)/);
});

test('shared chart utils use the local echarts runtime wrapper', () => {
  assert.match(chartUtils, /from '\.\/echarts'/);
});
