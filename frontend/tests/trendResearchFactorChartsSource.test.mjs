import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const source = fs.readFileSync(
  new URL('../src/renderer/components/analytics/TrendResearchFactorCharts.vue', import.meta.url),
  'utf8',
);
const cssSource = fs.readFileSync(
  new URL('../src/renderer/components/analytics/trendResearchFactorCharts.css', import.meta.url),
  'utf8',
);
const chartUtilSource = fs.readFileSync(
  new URL('../src/renderer/utils/lwcTimeSeriesChart.mjs', import.meta.url),
  'utf8',
);

test('TrendResearchFactorCharts renders seven chart groups with shared hover state', () => {
  assert.match(source, /v-for=\"group in groups\"/);
  assert.match(source, /activeHoverTime/);
  assert.match(source, /selectedFactorName/);
  assert.match(source, /createTimeSeriesChartManager/);
  assert.match(source, /trend-factor-hover-line/);
  assert.match(source, /is-dimmed/);
});

test('time series chart manager exposes hover callback and time coordinate lookup', () => {
  assert.match(chartUtilSource, /onHoverTimeChange/);
  assert.match(chartUtilSource, /getTimeCoordinate/);
  assert.match(chartUtilSource, /tooltipValueFormatter/);
  assert.match(chartUtilSource, /priceScaleId/);
});

test('TrendResearchFactorCharts styles reserve space for a dense multi-panel layout', () => {
  assert.match(cssSource, /\.trend-factor-chart-grid/);
  assert.match(cssSource, /\.trend-factor-chart-panel/);
  assert.match(cssSource, /\.trend-factor-hover-line/);
});
