import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const source = fs.readFileSync(
  new URL('../src/renderer/utils/lwc.js', import.meta.url),
  'utf8',
);

test('createLwcChart disables Lightweight Charts attribution logo in the shared theme', () => {
  assert.match(source, /attributionLogo:\s*false/);
});

test('createLwcChart deep-merges nested chart options so layout overrides keep shared defaults', () => {
  assert.match(source, /const\s*\{\s*layout,\s*grid,\s*crosshair,\s*rightPriceScale,\s*timeScale,/);
  assert.match(source, /layout:\s*\{[\s\S]*\.\.\.LWC_THEME\.layout[\s\S]*\.\.\.\(layout \|\| \{\}\)/);
  assert.match(source, /grid:\s*\{[\s\S]*\.\.\.LWC_THEME\.grid[\s\S]*\.\.\.\(grid \|\| \{\}\)/);
  assert.match(source, /crosshair:\s*\{[\s\S]*\.\.\.LWC_THEME\.crosshair[\s\S]*\.\.\.\(crosshair \|\| \{\}\)/);
  assert.doesNotMatch(source, /\.\.\.LWC_THEME,\s*\.\.\.overrides/);
});
