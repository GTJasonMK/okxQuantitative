import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const source = fs.readFileSync(
  new URL('../src/renderer/components/analytics/TrendResearchOverviewPage.vue', import.meta.url),
  'utf8',
);

test('overview page renders only summary-oriented widgets', () => {
  assert.match(source, /TrendResearchPredictionSummary/);
  assert.match(source, /TrendResearchTimeDistributions/);
  assert.match(source, /TrendResearchModelStatus/);
  assert.doesNotMatch(source, /api\.getTrendResearchFactorSeries/);
  assert.doesNotMatch(source, /TrendResearchTrainingRunPanel/);
});
