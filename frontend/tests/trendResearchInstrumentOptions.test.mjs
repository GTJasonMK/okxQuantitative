import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildTrendResearchInstrumentOptions,
  filterTrendResearchInstrumentOptions,
} from '../src/renderer/components/settings/trendResearchInstrumentOptions.mjs';

test('buildTrendResearchInstrumentOptions keeps only live USDT swaps and preserves missing selections', () => {
  const result = buildTrendResearchInstrumentOptions({
    instruments: [
      { inst_id: 'BTC-USDT-SWAP', base_ccy: 'BTC', quote_ccy: 'USDT', state: 'live' },
      { inst_id: 'DOGE-USDT-SWAP', base_ccy: 'DOGE', quote_ccy: '', state: 'live' },
      { inst_id: 'ETH-USDC-SWAP', base_ccy: 'ETH', quote_ccy: 'USDC', state: 'live' },
      { inst_id: 'SOL-USDT-SWAP', base_ccy: 'SOL', quote_ccy: 'USDT', state: 'suspend' },
      { inst_id: 'XRP-USDT-SWAP', base_ccy: 'XRP', quote_ccy: 'USDT', state: 'live' },
    ],
    selectedInstIds: ['BTC-USDT-SWAP', 'PEPE-USDT-SWAP'],
  });

  assert.deepEqual(
    result.options.map((item) => item.instId),
    ['BTC-USDT-SWAP', 'DOGE-USDT-SWAP', 'XRP-USDT-SWAP'],
  );
  assert.deepEqual(
    result.missingSelected.map((item) => item.instId),
    ['PEPE-USDT-SWAP'],
  );
});

test('filterTrendResearchInstrumentOptions matches instId and base currency', () => {
  const options = [
    { instId: 'BTC-USDT-SWAP', baseCcy: 'BTC', label: 'BTC-USDT-SWAP' },
    { instId: 'XRP-USDT-SWAP', baseCcy: 'XRP', label: 'XRP-USDT-SWAP' },
  ];

  assert.deepEqual(
    filterTrendResearchInstrumentOptions(options, 'btc').map((item) => item.instId),
    ['BTC-USDT-SWAP'],
  );
  assert.deepEqual(
    filterTrendResearchInstrumentOptions(options, 'xrp-usdt').map((item) => item.instId),
    ['XRP-USDT-SWAP'],
  );
});
