import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const panelSource = fs.readFileSync(
  new URL('../src/renderer/components/analytics/TrendResearchPanel.vue', import.meta.url),
  'utf8',
);
const apiSource = fs.readFileSync(
  new URL('../src/renderer/services/api.js', import.meta.url),
  'utf8',
);
const wsSource = fs.readFileSync(
  new URL('../src/renderer/services/websocket.js', import.meta.url),
  'utf8',
);

test('TrendResearchPanel becomes a workspace shell with internal subnav', () => {
  assert.match(panelSource, /useTrendResearchWorkspace/);
  assert.match(panelSource, /TrendResearchSubnav/);
  assert.match(panelSource, /activeTrendPage/);
  assert.match(panelSource, /trend-subpage-host/);
  assert.doesNotMatch(panelSource, /TrendResearchFactorCharts/);
  assert.doesNotMatch(panelSource, /TrendResearchTrainingRunPanel/);
  assert.doesNotMatch(panelSource, /TrendResearchProcessDiagnostics/);
});

test('TrendResearchPanel keeps lookback selection and shared loading in the shell', () => {
  assert.match(panelSource, /TREND_LOOKBACK_OPTIONS/);
  assert.match(panelSource, /selectedLookbackSeconds/);
  assert.match(panelSource, /loadSharedData/);
  assert.doesNotMatch(panelSource, /api\.getTrendResearchFactorSeries/);
  assert.doesNotMatch(panelSource, /api\.getTrendResearchTrainingRun/);
});

test('TrendResearchPanel forwards realtime refresh state into the factors page', () => {
  assert.match(panelSource, /refreshVersion/);
  assert.match(panelSource, /:refresh-token="refreshVersion"/);
  assert.match(panelSource, /:key="`training-\$\{refreshVersion\}`"/);
});

test('TrendResearchPanel keeps diagnostics workspace mounted across shared realtime refreshes', () => {
  const diagnosticsBlock = panelSource.match(/<TrendResearchDiagnosticsPage[\s\S]*?\/>/)?.[0] || '';
  assert.doesNotMatch(diagnosticsBlock, /:key="`diagnostics-\$\{refreshVersion\}`"/);
});

test('TrendResearchPanel isolates diagnostics into an independent page workspace', () => {
  const diagnosticsBlock = panelSource.match(/<TrendResearchDiagnosticsPage[\s\S]*?\/>/)?.[0] || '';
  assert.match(panelSource, /activeTrendPage === 'diagnostics'/);
  assert.doesNotMatch(panelSource, /activeTrendPage !== 'diagnostics'/);
  assert.match(diagnosticsBlock, /:inst-id="selectedInstId"/);
  assert.match(diagnosticsBlock, /@select-inst="selectInstrument"/);
  assert.doesNotMatch(diagnosticsBlock, /:recent-process="recentProcess"/);
  assert.doesNotMatch(diagnosticsBlock, /:selected-process-instrument="selectedProcessInstrument"/);
  assert.doesNotMatch(diagnosticsBlock, /:selected-trend-row="selectedTrendRow"/);
});

test('TrendResearchPanel keeps existing workspace visible when a shared request errors', () => {
  assert.match(panelSource, /<div v-if="error" class="error-message">{{ error }}<\/div>/);
  assert.match(panelSource, /v-else-if="hasRenderableWorkspace"/);
});

test('api service still exposes trend research process, factor, feature and training endpoints', () => {
  assert.match(apiSource, /getTrendResearchProcess/);
  assert.match(apiSource, /\/api\/trend-research\/process/);
  assert.match(apiSource, /getTrendResearchFactorSeries/);
  assert.match(apiSource, /\/api\/trend-research\/factor-series\//);
  assert.match(apiSource, /getTrendResearchFeatureBars/);
  assert.match(apiSource, /\/api\/trend-research\/feature-bars\//);
  assert.match(apiSource, /getTrendResearchTrainingRun/);
});

test('market websocket service exposes trend research subscription channel', () => {
  assert.match(wsSource, /subscribeTrendResearch/);
  assert.match(wsSource, /unsubscribeTrendResearch/);
  assert.match(wsSource, /trend_research/);
});
