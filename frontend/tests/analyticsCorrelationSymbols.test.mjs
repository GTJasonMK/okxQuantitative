import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildCorrelationAvailabilityMessage,
  extractAvailableBaseSymbols,
  filterCorrelationSymbols,
  reconcileCorrelationSelection,
} from '../src/renderer/views/analyticsCorrelationSymbols.mjs';

test('filterCorrelationSymbols keeps only symbols with matching inst type and timeframe', () => {
  const rows = [
    { inst_id: 'BTC-USDT', inst_type: 'SPOT', timeframes: ['1H', '4H'] },
    { inst_id: 'BTC-USDT-SWAP', inst_type: 'SWAP', timeframes: ['1H'] },
    { inst_id: 'ETH-USDT-SWAP', inst_type: 'SWAP', timeframes: ['5m'] },
    { inst_id: 'SOL-USDT-SWAP', inst_type: 'SWAP', timeframes: ['1H', '15m'] },
  ];

  assert.deepEqual(
    filterCorrelationSymbols(rows, { instType: 'SWAP', timeframe: '1H' }),
    ['BTC-USDT', 'SOL-USDT'],
  );
  assert.deepEqual(
    filterCorrelationSymbols(rows, { instType: 'SPOT', timeframe: '1H' }),
    ['BTC-USDT'],
  );
});

test('extractAvailableBaseSymbols deduplicates spot and swap variants into base symbols', () => {
  const rows = [
    { inst_id: 'BTC-USDT', inst_type: 'SPOT', timeframes: ['1H'] },
    { inst_id: 'BTC-USDT-SWAP', inst_type: 'SWAP', timeframes: ['1H'] },
    { inst_id: 'ETH-USDT-SWAP', inst_type: 'SWAP', timeframes: ['1H'] },
  ];

  assert.deepEqual(extractAvailableBaseSymbols(rows), ['BTC-USDT', 'ETH-USDT']);
});

test('reconcileCorrelationSelection preserves valid picks and falls back to first candidates when insufficient', () => {
  assert.deepEqual(
    reconcileCorrelationSelection(['BTC-USDT', 'ETH-USDT'], ['BTC-USDT', 'ETH-USDT', 'SOL-USDT']),
    ['BTC-USDT', 'ETH-USDT'],
  );
  assert.deepEqual(
    reconcileCorrelationSelection(['BTC-USDT'], ['BTC-USDT', 'ETH-USDT', 'SOL-USDT']),
    ['BTC-USDT', 'ETH-USDT', 'SOL-USDT'],
  );
  assert.deepEqual(
    reconcileCorrelationSelection(['BTC-USDT'], ['BTC-USDT']),
    ['BTC-USDT'],
  );
});

test('buildCorrelationAvailabilityMessage describes missing local dataset clearly', () => {
  assert.equal(
    buildCorrelationAvailabilityMessage({ instType: 'SWAP', timeframe: '1H' }),
    '当前 SWAP / 1H 本地数据不足，至少需要 2 个币种',
  );
});
