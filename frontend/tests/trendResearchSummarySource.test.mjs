import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const SUMMARY_PATH = new URL('../src/renderer/components/analytics/TrendResearchFactorSummary.vue', import.meta.url);

const PANEL_PATH = new URL('../src/renderer/components/analytics/TrendResearchPanel.vue', import.meta.url);

const TRAINING_PAGE_PATH = new URL('../src/renderer/components/analytics/TrendResearchTrainingPage.vue', import.meta.url);

test('TrendResearchFactorSummary keeps a compact factor strip with selected-factor meta', () => {
  const source = fs.readFileSync(SUMMARY_PATH, 'utf8');

  assert.match(source, /因子筛选/);
  assert.match(source, /trend-factor-strip-lookback/);
  assert.match(source, /稳/);
  assert.match(source, /IC/);
  assert.match(source, /展开全部/);
});

test('TrendResearchPanel remains a thin wrapper around ResearchPlatformPanel', () => {
  const source = fs.readFileSync(PANEL_PATH, 'utf8');

  assert.match(source, /ResearchPlatformPanel/);
  assert.doesNotMatch(source, /TrendResearchOverviewPage/);
  assert.doesNotMatch(source, /TrendResearchFactorsPage/);
  assert.doesNotMatch(source, /TrendResearchTrainingPage/);
  assert.doesNotMatch(source, /TrendResearchDiagnosticsPage/);
});

test('TrendResearchTrainingPage keeps training snapshot synced with model status', () => {
  const source = fs.readFileSync(TRAINING_PAGE_PATH, 'utf8');

  assert.match(source, /buildTrendTrainingRunPanelModel/);
  assert.match(source, /props\.modelStatus/);
  assert.match(source, /props\.trainingRunPayload/);
  assert.match(source, /resolvedTrainingRun/);
});
