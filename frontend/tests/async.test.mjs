import test from 'node:test';
import assert from 'node:assert/strict';

import { createTrailingThrottle } from '../src/renderer/utils/async.js';

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

test('createTrailingThrottle emits immediate and trailing calls during a burst', async () => {
  const calls = [];
  const scheduler = createTrailingThrottle((value) => {
    calls.push({ value, at: Date.now() });
  }, 40);

  scheduler.run('first');
  await sleep(10);
  scheduler.run('second');
  await sleep(10);
  scheduler.run('latest');
  await sleep(70);

  assert.equal(calls.length, 2);
  assert.deepEqual(calls.map((entry) => entry.value), ['first', 'latest']);
  assert.ok(calls[1].at - calls[0].at >= 30);
});

test('createTrailingThrottle cancels pending trailing calls', async () => {
  const calls = [];
  const scheduler = createTrailingThrottle((value) => {
    calls.push(value);
  }, 40);

  scheduler.run('first');
  await sleep(10);
  scheduler.run('pending');
  scheduler.cancel();
  await sleep(70);

  assert.deepEqual(calls, ['first']);
});
