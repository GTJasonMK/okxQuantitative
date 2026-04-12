import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const source = fs.readFileSync(
  new URL('../src/renderer/components/analytics/TrendResearchFeatureWindow.vue', import.meta.url),
  'utf8',
);

test('feature window keeps rendering realtime bars even when request errors are present', () => {
  assert.match(source, /<div v-if="error" class="error-message">{{ error }}<\/div>/);
  assert.doesNotMatch(source, /<div v-else-if="loading" class="empty-state">加载特征窗口\.\.\.<\/div>/);
});

test('feature window drops loading state as soon as realtime bars arrive', () => {
  assert.match(source, /watch\(\(\) => props\.realtimeBars/);
  assert.match(source, /loading\.value = false;/);
  assert.match(source, /error\.value = '';/);
});
