import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

test('TrendResearchTrainingRunPanel wires timeline, curves, and retrain action', () => {
  const source = fs.readFileSync(
    new URL('../src/renderer/components/analytics/TrendResearchTrainingRunPanel.vue', import.meta.url),
    'utf8',
  );

  assert.match(source, /TrendResearchTrainingTimeline/);
  assert.match(source, /TrendResearchTrainingCurves/);
  assert.match(source, /当前阶段/);
  assert.match(source, /summaryCards/);
  assert.match(source, /currentStageCard/);
  assert.match(source, /defineEmits/);
  assert.match(source, /start-retrain/);
});
