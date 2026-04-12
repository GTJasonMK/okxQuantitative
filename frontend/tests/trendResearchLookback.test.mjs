import test from 'node:test';
import assert from 'node:assert/strict';

import {
  DEFAULT_TREND_LOOKBACK_SECONDS,
  TREND_LOOKBACK_OPTIONS,
  formatTrendLookbackLabel,
} from '../src/renderer/components/analytics/trendResearchLookback.mjs';

test('trend research lookback exposes the supported 30-120 minute presets', () => {
  assert.equal(DEFAULT_TREND_LOOKBACK_SECONDS, 3600);
  assert.deepEqual(
    TREND_LOOKBACK_OPTIONS.map((item) => item.seconds),
    [1800, 3600, 5400, 7200],
  );
});

test('formatTrendLookbackLabel renders minute-based captions for the factor summary', () => {
  assert.equal(formatTrendLookbackLabel(1800), '最近 30 分钟');
  assert.equal(formatTrendLookbackLabel(7200), '最近 120 分钟');
});
