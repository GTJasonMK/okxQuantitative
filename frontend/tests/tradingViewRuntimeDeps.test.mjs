import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const repoRoot = process.cwd();
const runtimePath = path.join(
  repoRoot,
  'src/renderer/composables/useTradingViewRuntime.js',
);
const tradingViewPath = path.join(
  repoRoot,
  'src/renderer/views/TradingView.vue',
);

test('useTradingViewRuntime declares the settings callbacks it uses', () => {
  const source = fs.readFileSync(runtimePath, 'utf8');

  assert.match(source, /\bloadSettings\b/);
  assert.match(source, /\bdebouncedSave\b/);
  assert.match(
    source,
    /const\s*\{[\s\S]*\bloadSettings\b[\s\S]*\bdebouncedSave\b[\s\S]*\}\s*=\s*deps;/,
  );
});

test('TradingView passes settings callbacks into useTradingViewRuntime', () => {
  const source = fs.readFileSync(tradingViewPath, 'utf8');

  assert.match(
    source,
    /useTradingViewRuntime\(\{[\s\S]*\bsettingsLoaded\b[\s\S]*\bloadSettings\b[\s\S]*\bdebouncedSave\b[\s\S]*\}\)/,
  );
});
