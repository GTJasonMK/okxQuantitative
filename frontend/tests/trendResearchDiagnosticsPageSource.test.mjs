import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const source = fs.readFileSync(
  new URL('../src/renderer/components/analytics/TrendResearchDiagnosticsPage.vue', import.meta.url),
  'utf8',
);
const shellSource = fs.readFileSync(
  new URL('../src/renderer/components/analytics/TrendDiagnosticsShell.vue', import.meta.url),
  'utf8',
);

test('diagnostics page mounts dedicated diagnostics workspace shell with explicit empty state', () => {
  assert.match(source, /useTrendDiagnosticsWorkspace/);
  assert.match(source, /TrendDiagnosticsShell/);
  assert.match(source, /instId/);
  assert.match(source, /processSummary/);
  assert.match(source, /selectedProcessInstrument/);
  assert.match(source, /defineEmits\(\['select-inst'\]\)/);
  assert.match(source, /emit\('select-inst'/);
  assert.doesNotMatch(source, /TrendResearchProcessDiagnostics/);
  assert.match(source, /empty-state/);
  assert.match(source, /暂无运行进度数据/);
});

test('diagnostics shell reuses the shared parent switcher instead of rendering an internal picker', () => {
  assert.doesNotMatch(shellSource, /TrendDiagnosticsInstrumentPicker/);
});
