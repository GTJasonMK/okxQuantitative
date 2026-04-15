import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';

test('api exposes full research platform methods', async () => {
  const source = await fs.readFile(new URL('../src/renderer/services/api.js', import.meta.url), 'utf8');
  assert.match(source, /getResearchPlatformSessions/);
  assert.match(source, /getResearchPlatformSessionDetail/);
  assert.match(source, /createResearchPlatformSession/);
  assert.match(source, /stopResearchPlatformSession/);
  assert.match(source, /getResearchPlatformCensusStatus/);
  assert.match(source, /getResearchPlatformDatasets/);
  assert.match(source, /getResearchPlatformDatasetDetail/);
  assert.match(source, /getResearchPlatformDatasetPreview/);
  assert.match(source, /createResearchPlatformDataset/);
  assert.match(source, /deleteResearchPlatformDataset/);
  assert.match(source, /getResearchPlatformTrainingRuns/);
  assert.match(source, /getResearchPlatformTrainingRun/);
  assert.match(source, /createResearchPlatformTrainingRun/);
});
