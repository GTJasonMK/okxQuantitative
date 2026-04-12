import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const source = fs.readFileSync(
  new URL('../src/renderer/components/analytics/TrendResearchFactorSummary.vue', import.meta.url),
  'utf8',
);
const cssSource = fs.readFileSync(
  new URL('../src/renderer/components/analytics/trendResearchFactorSummary.css', import.meta.url),
  'utf8',
);

test('TrendResearchFactorSummary renders a compact primary strip with expandable full list', () => {
  assert.match(source, /trend-factor-strip/);
  assert.match(source, /trend-factor-primary-row/);
  assert.match(source, /trend-factor-expand-button/);
  assert.match(source, /trend-factor-all-row/);
  assert.match(source, /trend-factor-pill/);
  assert.match(source, /defineEmits/);
  assert.match(source, /select-factor/);
  assert.match(source, /is-selected/);
  assert.doesNotMatch(source, /trend-factor-strength-track/);
  assert.doesNotMatch(source, /trend-factor-card/);
});

test('TrendResearchFactorSummary styles use a compact collapsible strip layout', () => {
  assert.match(cssSource, /\.trend-factor-strip/);
  assert.match(cssSource, /\.trend-factor-primary-row/);
  assert.match(cssSource, /\.trend-factor-expand-button/);
  assert.match(cssSource, /\.trend-factor-all-row/);
  assert.match(cssSource, /\.trend-factor-pill/);
  assert.match(cssSource, /\.trend-factor-pill\.is-selected/);
  assert.doesNotMatch(cssSource, /\.trend-factor-strength-track/);
  assert.doesNotMatch(cssSource, /\.trend-factor-card/);
});
