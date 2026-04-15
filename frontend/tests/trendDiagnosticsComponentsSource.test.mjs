import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const shellSource = fs.readFileSync(
  new URL('../src/renderer/components/analytics/TrendDiagnosticsShell.vue', import.meta.url),
  'utf8',
);
const timelineSource = fs.readFileSync(
  new URL('../src/renderer/components/analytics/TrendDiagnosticsTimeline.vue', import.meta.url),
  'utf8',
);
const detailsSource = fs.readFileSync(
  new URL('../src/renderer/components/analytics/TrendDiagnosticsDetails.vue', import.meta.url),
  'utf8',
);

test('diagnostics shell is reorganized into a progress dashboard before the timeline and details', () => {
  assert.match(shellSource, /TrendProgressOverviewStrip/);
  assert.match(shellSource, /TrendProgressConclusionCard/);
  assert.match(shellSource, /TrendProgressPipeline/);
  assert.match(shellSource, /TrendProgressEvidenceCards/);
  assert.match(shellSource, /TrendDiagnosticsTimeline/);
  assert.match(shellSource, /TrendDiagnosticsDetails/);
  assert.doesNotMatch(shellSource, /TrendDiagnosticsHealthSummary/);
  assert.match(shellSource, /buildTrendProgressDashboardModel/);
});

test('timeline is reframed as recent key events instead of a primary diagnostics headline', () => {
  assert.match(timelineSource, /最近关键事件/);
  assert.match(timelineSource, /证据回放/);
});

test('details panel is explicitly presented as advanced diagnostics', () => {
  assert.match(detailsSource, /高级诊断明细/);
  assert.match(detailsSource, /当前合约最近事件/);
  assert.match(detailsSource, /全局最近事件/);
  assert.match(detailsSource, /最近诊断快照/);
  assert.match(detailsSource, /props\.instrumentHealth\.last_event_at/);
  assert.match(detailsSource, /props\.globalHealth\.last_event_at/);
  assert.match(detailsSource, /props\.emittedAt/);
});
