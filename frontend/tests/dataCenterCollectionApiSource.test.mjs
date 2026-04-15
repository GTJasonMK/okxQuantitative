import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';

test('api exposes data center collection methods', async () => {
  const source = await fs.readFile(new URL('../src/renderer/services/api.js', import.meta.url), 'utf8');
  assert.match(source, /getDataCenterCollectionSessions/);
  assert.match(source, /getDataCenterCollectionSessionDetail/);
  assert.match(source, /createDataCenterCollectionSession/);
  assert.match(source, /stopDataCenterCollectionSession/);
  assert.match(source, /deleteDataCenterCollectionSession/);
  assert.match(source, /getDataCenterCollectionCensusStatus/);
});

test('websocket exposes data center collection subscription aliases', async () => {
  const source = await fs.readFile(new URL('../src/renderer/services/websocket.js', import.meta.url), 'utf8');
  assert.match(source, /subscribeDataCenterCollection/);
  assert.match(source, /unsubscribeDataCenterCollection/);
  assert.match(source, /subscribeResearchPlatform/);
});
