import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';

test('websocket exposes research_platform channel helpers and event dispatch', async () => {
  const source = await fs.readFile(new URL('../src/renderer/services/websocket.js', import.meta.url), 'utf8');
  assert.match(source, /subscribeResearchPlatform/);
  assert.match(source, /unsubscribeResearchPlatform/);
  assert.match(source, /research_platform/);
  assert.match(source, /session_updated/);
  assert.match(source, /session_running/);
  assert.match(source, /session_failed/);
  assert.match(source, /second_flushed/);
  assert.match(source, /session_quality_updated/);
  assert.match(source, /training_run_updated/);
});

test('ResearchSessionList renders status and coverage fields for collection history', async () => {
  const source = await fs.readFile(new URL('../src/renderer/components/analytics/ResearchSessionList.vue', import.meta.url), 'utf8');
  assert.match(source, /coverage_ratio|coverageRatio/);
  assert.match(source, /status/);
  assert.match(source, /stop_reason|stopReason/);
});

test('ResearchSessionDetail exposes error metadata fields', async () => {
  const source = await fs.readFile(new URL('../src/renderer/components/analytics/ResearchSessionDetail.vue', import.meta.url), 'utf8');
  assert.match(source, /last_error_code|lastErrorCode/);
  assert.match(source, /last_error_message|lastErrorMessage/);
});
