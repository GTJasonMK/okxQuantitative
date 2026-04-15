import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const source = fs.readFileSync(
  new URL('../src/renderer/components/analytics/TrendResearchSubnav.vue', import.meta.url),
  'utf8',
);

test('TrendResearchSubnav exposes the four approved task pages', () => {
  assert.match(source, /结论总览/);
  assert.match(source, /因子分析/);
  assert.match(source, /训练模型/);
  assert.match(source, /运行进度/);
  assert.match(source, /defineEmits/);
  assert.match(source, /update:modelValue/);
});
