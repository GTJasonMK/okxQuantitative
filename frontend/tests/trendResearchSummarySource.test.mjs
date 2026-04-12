import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const SUMMARY_PATH = path.resolve(
  process.cwd(),
  'src/renderer/components/analytics/TrendResearchFactorSummary.vue',
);

const PANEL_PATH = path.resolve(
  process.cwd(),
  'src/renderer/components/analytics/TrendResearchPanel.vue',
);

const TRAINING_PAGE_PATH = path.resolve(
  process.cwd(),
  'src/renderer/components/analytics/TrendResearchTrainingPage.vue',
);

test('TrendResearchFactorSummary keeps a compact factor strip with selected-factor meta', () => {
  const source = fs.readFileSync(SUMMARY_PATH, 'utf8');

  assert.match(source, /因子筛选/);
  assert.match(source, /trend-factor-strip-lookback/);
  assert.match(source, /稳/);
  assert.match(source, /IC/);
  assert.match(source, /展开全部/);
});

test('TrendResearchPanel wires a selectable lookback preset module', () => {
  const source = fs.readFileSync(PANEL_PATH, 'utf8');

  assert.match(source, /TREND_LOOKBACK_OPTIONS/);
  assert.match(source, /selectedLookbackSeconds/);
  assert.match(source, /useTrendResearchWorkspace/);
  assert.match(source, /lookbackLabel/);
});

test('TrendResearchTrainingPage keeps training snapshot synced with model status', () => {
  const source = fs.readFileSync(TRAINING_PAGE_PATH, 'utf8');

  assert.match(source, /buildTrendTrainingRunPanelModel/);
  assert.match(source, /props\.modelStatus/);
  assert.match(source, /props\.trainingRunPayload/);
  assert.match(source, /resolvedTrainingRun/);
});
