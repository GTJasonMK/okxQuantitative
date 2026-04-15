import test from 'node:test';
import assert from 'node:assert/strict';

import {
  applyTrendDiagnosticsEvent,
  buildTrendDiagnosticsState,
} from '../src/renderer/components/analytics/trendDiagnosticsState.mjs';


test('diagnostics reducer replaces snapshot and appends timeline incrementally', () => {
  const state = buildTrendDiagnosticsState({
    selected_inst_id: 'BTC-USDT-SWAP',
    timeline: [{ sequence: 1, kind: 'trade', label: 'Trade 到达' }],
  });

  const next = applyTrendDiagnosticsEvent(state, {
    event_type: 'timeline_appended',
    inst_id: 'BTC-USDT-SWAP',
    payload: {
      timeline_entry: { sequence: 2, kind: 'book', label: 'Book 到达' },
    },
  });

  assert.equal(next.timeline.length, 2);
  assert.equal(next.timeline[1].kind, 'book');
});


test('diagnostics reducer updates health and details for feature events', () => {
  const state = buildTrendDiagnosticsState({
    selected_inst_id: 'BTC-USDT-SWAP',
    instrument_health: { inst_id: 'BTC-USDT-SWAP', pipeline_stage: 'collecting' },
    details: { subscription_state: 'subscribed' },
    timeline: [],
  });

  const next = applyTrendDiagnosticsEvent(state, {
    event_type: 'feature_emitted',
    inst_id: 'BTC-USDT-SWAP',
    payload: {
      instrument_health: { inst_id: 'BTC-USDT-SWAP', pipeline_stage: 'feature_ready' },
      details: { subscription_state: 'subscribed', last_feature_bucket: 1712365200 },
      timeline_entry: { sequence: 3, kind: 'feature', label: '特征已生成' },
    },
  });

  assert.equal(next.instrumentHealth.pipeline_stage, 'feature_ready');
  assert.equal(next.details.last_feature_bucket, 1712365200);
  assert.equal(next.timeline[0].kind, 'feature');
});


test('diagnostics reducer updates health summary for incremental trade events', () => {
  const state = buildTrendDiagnosticsState({
    selected_inst_id: 'BTC-USDT-SWAP',
    global_health: { whitelist_count: 2, active_count: 0, stale_count: 2, error_count: 0 },
    instrument_health: { inst_id: 'BTC-USDT-SWAP', trade_age_seconds: 645.2, book_age_seconds: 645.2 },
    details: { subscription_state: 'subscribed' },
    timeline: [],
  });

  const next = applyTrendDiagnosticsEvent(state, {
    event_type: 'timeline_appended',
    inst_id: 'BTC-USDT-SWAP',
    payload: {
      instrument_health: {
        inst_id: 'BTC-USDT-SWAP',
        trade_age_seconds: 0,
        book_age_seconds: 4.5,
      },
      global_health: {
        whitelist_count: 2,
        active_count: 1,
        stale_count: 1,
        error_count: 0,
      },
      details: { subscription_state: 'subscribed', pending_trade_count: 1 },
      timeline_entry: { sequence: 5, kind: 'trade', label: 'Trade 到达' },
    },
  });

  assert.equal(next.instrumentHealth.trade_age_seconds, 0);
  assert.equal(next.globalHealth.active_count, 1);
  assert.equal(next.details.pending_trade_count, 1);
  assert.equal(next.timeline[0].kind, 'trade');
});

test('diagnostics reducer dedupes repeated timeline entries from snapshots and incremental updates', () => {
  const repeatedEntry = {
    sequence: 1398,
    kind: 'book',
    label: '收到新的盘口快照',
    emitted_at: 1712365300,
  };
  const state = buildTrendDiagnosticsState({
    selected_inst_id: 'BTC-USDT-SWAP',
    timeline: [repeatedEntry, repeatedEntry],
  });

  const next = applyTrendDiagnosticsEvent(state, {
    event_type: 'timeline_appended',
    inst_id: 'BTC-USDT-SWAP',
    payload: {
      timeline_entry: repeatedEntry,
    },
  });

  assert.equal(state.timeline.length, 1);
  assert.equal(next.timeline.length, 1);
  assert.equal(next.timeline[0].sequence, 1398);
});
