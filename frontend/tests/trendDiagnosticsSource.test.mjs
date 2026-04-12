import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const apiSource = fs.readFileSync(
  new URL('../src/renderer/services/api.js', import.meta.url),
  'utf8',
);
const wsSource = fs.readFileSync(
  new URL('../src/renderer/services/websocket.js', import.meta.url),
  'utf8',
);
const legacyDiagnosticsComponent = new URL(
  '../src/renderer/components/analytics/TrendResearchProcessDiagnostics.vue',
  import.meta.url,
);


test('api service exposes dedicated diagnostics snapshot endpoint', () => {
  assert.match(apiSource, /getTrendDiagnostics/);
  assert.match(apiSource, /\/api\/trend-research\/diagnostics/);
});


test('market websocket service exposes dedicated diagnostics subscription channel', () => {
  assert.match(wsSource, /subscribeTrendDiagnostics/);
  assert.match(wsSource, /unsubscribeTrendDiagnostics/);
  assert.match(wsSource, /trend_diagnostics/);
});


test('legacy process diagnostics component is removed from the analytics tree', () => {
  assert.equal(fs.existsSync(legacyDiagnosticsComponent), false);
});
