import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';

test('TrendResearchPanel mounts the new research platform workspace shell', async () => {
  const source = await fs.readFile(new URL('../src/renderer/components/analytics/TrendResearchPanel.vue', import.meta.url), 'utf8');
  assert.match(source, /ResearchPlatformPanel/);
  assert.doesNotMatch(source, /TrendResearchOverviewPage/);
});

test('ResearchPlatformPanel exposes dataset-building and model-training subnav only', async () => {
  const source = await fs.readFile(new URL('../src/renderer/components/analytics/ResearchPlatformPanel.vue', import.meta.url), 'utf8');
  assert.match(source, /数据集平台/);
  assert.match(source, /dataset-building/);
  assert.match(source, /model-training/);
  assert.doesNotMatch(source, /data-collection/);
  assert.match(source, /DatasetBuildingPage/);
  assert.match(source, /ModelTrainingPage/);
});
