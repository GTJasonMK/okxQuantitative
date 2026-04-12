import test from 'node:test';
import assert from 'node:assert/strict';

import {
  createSeriesMarkerAdapter,
  toTradeMarkers,
} from '../src/renderer/utils/lwcMarkers.mjs';

test('toTradeMarkers maps buy/sell trades into sorted lightweight chart markers', () => {
  const markers = toTradeMarkers([
    { timestamp: 2000, side: 'sell' },
    { timestamp: 1000, side: 'buy' },
  ], {
    up: '#00ff00',
    down: '#ff0000',
  });

  assert.deepEqual(markers, [
    {
      time: 1,
      position: 'belowBar',
      color: '#00ff00',
      shape: 'arrowUp',
      text: 'B',
    },
    {
      time: 2,
      position: 'aboveBar',
      color: '#ff0000',
      shape: 'arrowDown',
      text: 'S',
    },
  ]);
});

test('createSeriesMarkerAdapter proxies setMarkers to the plugin api', () => {
  const calls = [];
  const plugin = {
    setMarkers: (markers) => {
      calls.push(markers);
    },
    detach: () => {
      calls.push('detach');
    },
    markers: () => [],
  };

  const adapter = createSeriesMarkerAdapter({
    series: { id: 'series' },
    createSeriesMarkersImpl: (series, initialMarkers) => {
      calls.push({ series, initialMarkers });
      return plugin;
    },
    initialMarkers: [{ time: 1 }],
  });

  adapter.setMarkers([{ time: 2 }]);
  adapter.detach();

  assert.deepEqual(calls, [
    { series: { id: 'series' }, initialMarkers: [{ time: 1 }] },
    [{ time: 2 }],
    'detach',
  ]);
});
