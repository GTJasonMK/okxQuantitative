import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';

test('ResearchCollectionControlCard exposes the collection form contract and actions', async () => {
  const source = await fs.readFile(new URL('../src/renderer/components/analytics/ResearchCollectionControlCard.vue', import.meta.url), 'utf8');
  assert.match(source, /startCollectionSession/);
  assert.match(source, /stopCollectionSession/);
  assert.match(source, /deleteCollectionSession/);
  assert.match(source, /删除当前会话/);
  assert.match(source, /actionError/);
  assert.match(source, /planned_duration_sec/);
  assert.match(source, /sampling_policy_id/);
  assert.match(source, /integrity_policy_version/);
  assert.match(source, /collector_version/);
  assert.match(source, /feature_recipe_version/);
  assert.match(source, /book_channel/);
  assert.match(source, /last_error_message/);
});
