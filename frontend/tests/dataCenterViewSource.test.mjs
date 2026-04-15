import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';

test('DataCenterView exposes watchlist, collection and inventory tabs', async () => {
  const source = await fs.readFile(new URL('../src/renderer/views/DataCenterView.vue', import.meta.url), 'utf8');
  assert.match(source, /watchlist/);
  assert.match(source, /collection/);
  assert.match(source, /inventory/);
  assert.match(source, /DataCollectionView/);
  assert.match(source, /秒级采集/);
});

test('DataCollectionView renders collection workspace cards', async () => {
  const source = await fs.readFile(new URL('../src/renderer/views/DataCollectionView.vue', import.meta.url), 'utf8');
  assert.match(source, /ResearchCollectionControlCard/);
  assert.match(source, /ResearchCollectionProgressBoard/);
  assert.match(source, /ResearchSessionList/);
  assert.match(source, /ResearchSessionDetail/);
  assert.match(source, /deleteCollectionSession/);
  assert.match(source, /ResearchSessionQualityCards/);
  assert.match(source, /ResearchSessionCharts/);
  assert.match(source, /ResearchSessionCoveragePanel/);
  assert.match(source, /useDataCollectionWorkspace/);
});
