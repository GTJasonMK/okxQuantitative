import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';

test('ResearchSessionDetail keeps session content and empty-state in separate branches', async () => {
  const source = await fs.readFile(new URL('../src/renderer/components/analytics/ResearchSessionDetail.vue', import.meta.url), 'utf8');
  assert.match(source, /<template v-if="session">/);
  assert.match(source, /删除会话/);
  assert.match(source, /deleteCollectionSession/);
});
