import test from 'node:test';
import assert from 'node:assert/strict';

import {
  formatCompactMoney,
  formatCompactNumber,
  formatCompactSignedNumber,
} from '../src/renderer/utils/formatting.js';

test('formatCompactNumber keeps standard decimals when the value fits', () => {
  assert.equal(formatCompactNumber(12.3456, { digits: 3, maxChars: 8 }), '12.346');
  assert.equal(formatCompactNumber(0.42, { digits: 3, maxChars: 8 }), '0.420');
});

test('formatCompactNumber falls back to scientific notation for large or tiny constrained values', () => {
  assert.equal(formatCompactNumber(123456789, { digits: 2, maxChars: 8, scientificDigits: 2 }), '1.23e+8');
  assert.equal(formatCompactNumber(-0.0000456, { digits: 3, maxChars: 8, scientificDigits: 2 }), '-4.56e-5');
});

test('formatCompactSignedNumber and formatCompactMoney preserve sign or prefix when compacting', () => {
  assert.equal(formatCompactSignedNumber(987654321, { digits: 1, maxChars: 8, scientificDigits: 2 }), '+9.88e+8');
  assert.equal(formatCompactMoney(123456789.12, { digits: 2, maxChars: 9, scientificDigits: 2 }), '$1.23e+8');
});
