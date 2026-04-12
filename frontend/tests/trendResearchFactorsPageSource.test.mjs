import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const source = fs.readFileSync(
  new URL('../src/renderer/components/analytics/TrendResearchFactorsPage.vue', import.meta.url),
  'utf8',
);

test('factors page owns factor-series loading and local factor selection', () => {
  assert.match(source, /api\.getTrendResearchFactorSeries/);
  assert.match(source, /TrendResearchFactorSummary/);
  assert.match(source, /TrendResearchFactorCharts/);
  assert.match(source, /refreshToken/);
  assert.match(source, /selectedFactorName/);
  assert.match(source, /watch\(/);
});
