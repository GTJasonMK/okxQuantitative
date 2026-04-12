import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const css = readFileSync(
  new URL('../src/renderer/assets/styles/views/backtest-view.css', import.meta.url),
  'utf8',
);
const template = readFileSync(
  new URL('../src/renderer/views/BacktestView.vue', import.meta.url),
  'utf8',
);

const getRule = (selector) => {
  const escapedSelector = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return css.match(new RegExp(`${escapedSelector}\\s*\\{([\\s\\S]*?)\\}`));
};

test('backtest page uses vertical-only shell scrolling with an adaptive desktop grid', () => {
  const shellRule = getRule('.backtest-view');
  const mainAreaRule = getRule('.main-area');

  assert.ok(shellRule, 'missing .backtest-view rule');
  assert.ok(mainAreaRule, 'missing .main-area rule');
  assert.match(shellRule[1], /overflow-x:\s*hidden\s*;/);
  assert.match(shellRule[1], /overflow-y:\s*auto\s*;/);
  assert.match(mainAreaRule[1], /display:\s*grid\s*;/);
  assert.match(mainAreaRule[1], /grid-template-columns:\s*minmax\(0,\s*1fr\)\s*minmax\(280px,\s*360px\)\s*;/);
});

test('backtest chart and bottom panels reserve stable usable height', () => {
  const klineCardRule = getRule('.kline-card');
  const bottomCardRule = getRule('.bottom-card');
  const bottomBodyRule = getRule('.bottom-card-body');

  assert.ok(klineCardRule, 'missing .kline-card rule');
  assert.ok(bottomCardRule, 'missing .bottom-card rule');
  assert.ok(bottomBodyRule, 'missing .bottom-card-body rule');
  assert.match(klineCardRule[1], /height:\s*clamp\(620px,\s*72vh,\s*860px\)\s*;/);
  assert.match(bottomCardRule[1], /max-height:\s*min\(56vh,\s*640px\)\s*;/);
  assert.match(bottomBodyRule[1], /overflow:\s*auto\s*;/);
});

test('backtest stats panel remains sticky and template exposes bottom-card-body wrapper', () => {
  const statsPanelRule = getRule('.stats-panel');

  assert.ok(statsPanelRule, 'missing .stats-panel rule');
  assert.match(statsPanelRule[1], /width:\s*100%\s*;/);
  assert.match(statsPanelRule[1], /min-width:\s*0\s*;/);
  assert.match(statsPanelRule[1], /position:\s*sticky\s*;/);
  assert.match(statsPanelRule[1], /top:\s*0\s*;/);
  assert.match(statsPanelRule[1], /max-height:\s*calc\(100vh\s*-\s*4px\)\s*;/);
  assert.doesNotMatch(statsPanelRule[1], /width:\s*360px\s*;/);
  assert.doesNotMatch(statsPanelRule[1], /flex:\s*0\s+0\s+360px\s*;/);
  assert.match(template, /<div class="bottom-card-body">/);
});

test('backtest stats area exposes overview tiles and metric grids', () => {
  const statsOverviewGridRule = getRule('.stats-overview-grid');
  const statMetricGridRule = getRule('.stat-metric-grid');

  assert.ok(statsOverviewGridRule, 'missing .stats-overview-grid rule');
  assert.ok(statMetricGridRule, 'missing .stat-metric-grid rule');
  assert.match(statsOverviewGridRule[1], /display:\s*grid\s*;/);
  assert.match(statsOverviewGridRule[1], /grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)\s*;/);
  assert.match(statMetricGridRule[1], /display:\s*grid\s*;/);
  assert.match(template, /class="stats-overview card"/);
  assert.match(template, /class="metric-tile"/);
});

test('backtest stats grids collapse before the full layout stacks', () => {
  assert.match(
    css,
    /@media \(max-width: 1440px\)\s*\{[\s\S]*?\.stats-overview-grid,\s*[\s\S]*?\.stat-metric-grid\s*\{[\s\S]*?grid-template-columns:\s*1fr\s*;/,
  );
});
