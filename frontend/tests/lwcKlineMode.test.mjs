import test from 'node:test';
import assert from 'node:assert/strict';

import { resolveKlineChartModeConfig } from '../src/renderer/composables/market/charting/lwcKlineMode.mjs';

test('resolveKlineChartModeConfig keeps live viewport behavior for market mode', () => {
  assert.deepEqual(resolveKlineChartModeConfig('market'), {
    constrainVisibleRange: true,
    chartOverrides: {},
  });
});

test('resolveKlineChartModeConfig removes live-only spacing for backtest mode', () => {
  assert.deepEqual(resolveKlineChartModeConfig('backtest'), {
    constrainVisibleRange: false,
    chartOverrides: {
      timeScale: {
        borderColor: 'rgba(255, 255, 255, 0.06)',
        timeVisible: true,
        secondsVisible: false,
        rightOffset: 0,
        barSpacing: 6,
        minBarSpacing: 0.5,
        fixLeftEdge: true,
        fixRightEdge: true,
        shiftVisibleRangeOnNewBar: false,
      },
    },
  });
});

test('resolveKlineChartModeConfig falls back to market mode for unknown values', () => {
  assert.deepEqual(resolveKlineChartModeConfig('unknown'), {
    constrainVisibleRange: true,
    chartOverrides: {},
  });
});
