import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const mainSource = fs.readFileSync(
  new URL('../src/main/index.js', import.meta.url),
  'utf8',
);

test('electron main process does not force unstable gpu acceleration switches', () => {
  assert.doesNotMatch(mainSource, /appendSwitch\('enable-gpu-rasterization'\)/);
  assert.doesNotMatch(mainSource, /appendSwitch\('enable-zero-copy'\)/);
});
