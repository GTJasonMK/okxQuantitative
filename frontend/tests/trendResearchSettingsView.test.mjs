import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const source = fs.readFileSync(new URL('../src/renderer/views/SettingsView.vue', import.meta.url), 'utf8');
const apiSource = fs.readFileSync(new URL('../src/renderer/services/api.js', import.meta.url), 'utf8');

test('SettingsView uses market instruments as trend research candidates', () => {
  assert.match(source, /loadTrendResearchInstruments/);
  assert.match(source, /api\.getInstruments\('SWAP'\)/);
  assert.match(source, /trendResearchInstrumentState/);
  assert.match(source, /saveTrendResearchConfig/);
  assert.match(source, /selectedInstIds/);
});

test('SettingsView no longer exposes manual whitelist textarea binding', () => {
  assert.doesNotMatch(source, /whitelistText/);
  assert.match(source, /trendResearchInstrumentState\.search/);
  assert.match(source, /刷新合约列表/);
  assert.match(source, /当前不在 OKX 返回列表中/);
});

test('api service still exposes trend research config endpoints', () => {
  assert.match(apiSource, /getTrendResearchConfig/);
  assert.match(apiSource, /updateTrendResearchConfig/);
  assert.match(apiSource, /\/api\/trend-research\/config/);
});
