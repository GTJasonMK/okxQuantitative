import test from 'node:test';
import assert from 'node:assert/strict';

import { deriveOrderBookSnapshot } from '../src/renderer/composables/market/orderBookDerived.mjs';

test('deriveOrderBookSnapshot groups levels once and builds shared derived state', () => {
  const derived = deriveOrderBookSnapshot({
    asks: [
      { price: 101, size: 1, order_count: 1 },
      { price: 101.5, size: 2, order_count: 2 },
      { price: 102, size: 1, order_count: 1 },
    ],
    bids: [
      { price: 100, size: 3, order_count: 1 },
      { price: 99.5, size: 2, order_count: 2 },
      { price: 99, size: 1, order_count: 1 },
    ],
    bestAsk: 101,
    bestBid: 100,
    midPrice: 100.5,
    groupingMultiplier: 2,
    wallMarkerLimit: 2,
    chartSize: {
      width: 960,
      height: 280,
      paddingLeft: 18,
      paddingRight: 18,
      paddingTop: 16,
      paddingBottom: 34,
    },
  });

  assert.equal(derived.baseTickSize, 0.5);
  assert.equal(derived.groupingStep, 1);
  assert.deepEqual(
    derived.asksGrouped.map(({ price, size, total }) => ({ price, size, total })),
    [
      { price: 101, size: 1, total: 1 },
      { price: 102, size: 3, total: 4 },
    ],
  );
  assert.deepEqual(
    derived.bidsGrouped.map(({ price, size, total }) => ({ price, size, total })),
    [
      { price: 100, size: 3, total: 3 },
      { price: 99, size: 3, total: 6 },
    ],
  );
  assert.equal(derived.maxSize, 3);
  assert.equal(derived.maxTotal, 6);
  assert.equal(derived.levelCount, 4);
  assert.equal(derived.ladderRows.length, 2);
  assert.deepEqual(derived.bidWalls.map((level) => level.price), [99, 100]);
  assert.deepEqual(derived.askWalls.map((level) => level.price), [101, 102]);
  assert.equal(derived.depthChart.hoverPoints.length, 4);
  assert.ok(derived.depthChart.bidLinePath.startsWith('M '));
  assert.ok(derived.depthChart.askAreaPath.endsWith('Z'));
  assert.ok(derived.depthChart.yTicks.length > 0);
});

test('deriveOrderBookSnapshot falls back to spread-based tick size when diff is unavailable', () => {
  const derived = deriveOrderBookSnapshot({
    asks: [{ price: 10.2, size: 4, order_count: 1 }],
    bids: [{ price: 10, size: 5, order_count: 1 }],
    bestAsk: 10.2,
    bestBid: 10,
    midPrice: 10.1,
    groupingMultiplier: 1,
    wallMarkerLimit: 2,
    chartSize: {
      width: 960,
      height: 280,
      paddingLeft: 18,
      paddingRight: 18,
      paddingTop: 16,
      paddingBottom: 34,
    },
  });

  assert.equal(derived.baseTickSize, 0.2);
  assert.equal(derived.groupingStep, 0.2);
  assert.equal(derived.asksGrouped.length, 1);
  assert.equal(derived.bidsGrouped.length, 1);
});
