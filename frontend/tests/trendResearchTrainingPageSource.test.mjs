import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const trainingPageSource = fs.readFileSync(
  new URL('../src/renderer/components/analytics/TrendResearchTrainingPage.vue', import.meta.url),
  'utf8',
);
const panelSource = fs.readFileSync(
  new URL('../src/renderer/components/analytics/TrendResearchPanel.vue', import.meta.url),
  'utf8',
);

test('training page owns retrain bootstrap and training snapshot fetch', () => {
  assert.match(trainingPageSource, /api\.getTrendResearchTrainingRun/);
  assert.match(trainingPageSource, /api\.retrainTrendResearchModel/);
  assert.match(trainingPageSource, /TrendResearchTrainingRunPanel/);
  assert.doesNotMatch(panelSource, /api\.getTrendResearchTrainingRun/);
  assert.doesNotMatch(panelSource, /api\.retrainTrendResearchModel/);
});
