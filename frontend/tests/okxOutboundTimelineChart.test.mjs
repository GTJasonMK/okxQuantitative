import test from 'node:test';
import assert from 'node:assert/strict';

import { buildOkxOutboundTimelineOption } from '../src/renderer/components/settings/okxOutboundTimelineChart.mjs';

test('buildOkxOutboundTimelineOption groups events into swimlanes', () => {
  const option = buildOkxOutboundTimelineOption({
    windowSeconds: 600,
    generatedAt: 1200,
    events: [
      { ts: 1000, channel: 'rest', target_group: 'public', op_key: 'market.ticker', result: 'ok', latency_ms: 9 },
      { ts: 1010, channel: 'rest', target_group: 'trade', op_key: 'trade.place_order', result: 'error', latency_ms: 80 },
    ],
  });

  assert.equal(option.yAxis.data.length, 4);
  assert.equal(option.series[0].data.length, 2);
  assert.equal(option.series[0].data[0].name, 'market.ticker');
  assert.equal(option.series[0].data[1].value[1], 2);
});
