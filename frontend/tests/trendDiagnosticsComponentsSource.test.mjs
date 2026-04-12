import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const summarySource = fs.readFileSync(
  new URL('../src/renderer/components/analytics/TrendDiagnosticsHealthSummary.vue', import.meta.url),
  'utf8',
);
const detailsSource = fs.readFileSync(
  new URL('../src/renderer/components/analytics/TrendDiagnosticsDetails.vue', import.meta.url),
  'utf8',
);

test('health summary distinguishes selected instrument events from snapshot heartbeat', () => {
  assert.match(summarySource, /全局停滞/);
  assert.match(summarySource, /当前合约最近事件/);
  assert.match(summarySource, /最近快照/);
  assert.match(summarySource, /当前只有诊断快照在刷新/);
  assert.match(summarySource, /props\.instrumentHealth\.last_event_at/);
  assert.match(summarySource, /props\.emittedAt/);
});

test('details panel exposes instrument event, global event and snapshot timestamps separately', () => {
  assert.match(detailsSource, /当前合约最近事件/);
  assert.match(detailsSource, /全局最近事件/);
  assert.match(detailsSource, /最近诊断快照/);
  assert.match(detailsSource, /props\.instrumentHealth\.last_event_at/);
  assert.match(detailsSource, /props\.globalHealth\.last_event_at/);
  assert.match(detailsSource, /props\.emittedAt/);
});
