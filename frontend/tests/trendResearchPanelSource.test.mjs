import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const panelSource = fs.readFileSync(
  new URL('../src/renderer/components/analytics/TrendResearchPanel.vue', import.meta.url),
  'utf8',
);

test('TrendResearchPanel becomes a thin wrapper around ResearchPlatformPanel', () => {
  assert.match(panelSource, /ResearchPlatformPanel/);
  assert.doesNotMatch(panelSource, /TrendResearchOverviewPage/);
  assert.doesNotMatch(panelSource, /TrendResearchFactorsPage/);
  assert.doesNotMatch(panelSource, /TrendResearchTrainingPage/);
  assert.doesNotMatch(panelSource, /TrendResearchDiagnosticsPage/);
});
