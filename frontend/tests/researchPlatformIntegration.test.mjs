import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';

test('AnalyticsView keeps TrendResearchPanel mounted under 数据集平台 tab', async () => {
  const source = await fs.readFile(new URL('../src/renderer/views/AnalyticsView.vue', import.meta.url), 'utf8');
  assert.match(source, /activeAnalyticsTab === 'trendResearch'/);
  assert.match(source, /数据集平台/);
  assert.match(source, /<TrendResearchPanel \/>/);
});

test('ResearchPlatformPanel switches between dataset building and training pages', async () => {
  const source = await fs.readFile(new URL('../src/renderer/components/analytics/ResearchPlatformPanel.vue', import.meta.url), 'utf8');
  assert.match(source, /DatasetBuildingPage/);
  assert.match(source, /ModelTrainingPage/);
  assert.doesNotMatch(source, /ResearchCollectionPage/);
});
