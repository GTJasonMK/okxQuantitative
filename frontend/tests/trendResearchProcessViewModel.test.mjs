import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildTrendProcessPanelModel,
  buildTrendTimelineSegments,
} from '../src/renderer/components/analytics/trendResearchProcessViewModel.mjs';

test('buildTrendProcessPanelModel summarizes process readiness and instrument cards', () => {
  const panel = buildTrendProcessPanelModel({
    summary: {
      whitelist_count: 2,
      trade_ready_count: 2,
      book_ready_count: 1,
      state_ready_count: 2,
      feature_ready_count: 1,
      inference_ready_count: 1,
    },
    instruments: [
      {
        inst_id: 'BTC-USDT-SWAP',
        pipeline_state: 'inference_ready',
        runtime: {
          pending_trade_count: 7,
          last_trade_price: 61234.5,
          last_trade_side: 'buy',
          last_trade_age_seconds: 0.2,
          last_book_age_seconds: 0.4,
          last_state_age_seconds: 12.2,
        },
        stages: {
          trade: { ready: true, label: '逐笔成交已到达' },
          book: { ready: true, label: '盘口已到达' },
          state: { ready: true, label: '合约状态已同步' },
          feature: { ready: true, label: '最近 1 秒特征条已生成' },
          inference: { ready: true, label: '最新推断已生成' },
        },
        latest_feature_bar: {
          second_bucket: 1712365200,
          trade_count: 12,
          signed_trade_notional: 62500,
          spread_bps: 1.8,
          oi_delta: 35,
          basis_zscore: 4.2,
          data_quality: 'ok',
        },
        latest_inference: {
          trend_state: 'uptrend_confirmed',
          trend_score: 62.5,
          confidence: 0.88,
          predicted_top_eta_seconds: 900,
          predicted_bottom_eta_seconds: 2100,
          predicted_top_price: 61234.56,
          predicted_bottom_price: 59456.78,
          predicted_top_return: 0.02,
          predicted_bottom_return: -0.01,
        },
        recent_feature_bars: [
          { second_bucket: 1712365199, signed_trade_notional: -20000, data_quality: 'partial' },
          { second_bucket: 1712365200, signed_trade_notional: 62500, data_quality: 'ok' },
        ],
      },
    ],
  });

  assert.equal(panel.summaryCards[0].value, '2');
  assert.equal(panel.summaryCards[5].value, '1');
  assert.equal(panel.summaryStats.inference_ready_count, 1);
  assert.equal(panel.instruments[0].pipelineState, 'inference_ready');
  assert.equal(panel.instruments[0].displayState, '推断完成');
  assert.equal(panel.instruments[0].featureStats[0].value, '12');
  assert.equal(panel.instruments[0].runtimeStats[0].label, '待处理逐笔');
  assert.equal(panel.instruments[0].runtimeStats[0].value, '7');
  assert.equal(panel.instruments[0].runtimeStats[1].value, '61234.5');
  assert.equal(panel.instruments[0].runtimeStats[2].value, 'BUY');
  assert.equal(panel.instruments[0].latestInference.confidencePct, '88.0%');
  assert.equal(panel.instruments[0].latestInference.topEtaLabel, '15 分钟');
  assert.equal(panel.instruments[0].latestInference.bottomEtaLabel, '35 分钟');
  assert.equal(panel.instruments[0].latestInference.topReturnLabel, '+2.0%');
  assert.equal(panel.instruments[0].latestInference.bottomReturnLabel, '-1.0%');
  assert.equal(panel.instruments[0].recentBars.length, 2);
});

test('buildTrendTimelineSegments maps recent bars into directional columns', () => {
  const segments = buildTrendTimelineSegments([
    { second_bucket: 1, signed_trade_notional: -1000, data_quality: 'partial' },
    { second_bucket: 2, signed_trade_notional: 0, data_quality: 'ok' },
    { second_bucket: 3, signed_trade_notional: 2000, data_quality: 'ok' },
  ]);

  assert.equal(segments.length, 3);
  assert.equal(segments[0].tone, 'down');
  assert.equal(segments[1].tone, 'flat');
  assert.equal(segments[2].tone, 'up');
  assert.equal(segments[0].qualityTone, 'partial');
  assert.equal(segments[2].height, 100);
});

test('buildTrendProcessPanelModel compacts large feature values inside process cards', () => {
  const panel = buildTrendProcessPanelModel({
    instruments: [
      {
        inst_id: 'BTC-USDT-SWAP',
        pipeline_state: 'feature_ready',
        latest_feature_bar: {
          trade_count: 12,
          signed_trade_notional: 123456789,
          spread_bps: 1.8,
          oi_delta: -987654321,
          basis_zscore: -0.0000456,
          data_quality: 'ok',
        },
      },
    ],
  });

  assert.equal(panel.instruments[0].featureStats[1].value, '+1.23e+8');
  assert.equal(panel.instruments[0].featureStats[3].value, '-9.88e+8');
  assert.equal(panel.instruments[0].featureStats[4].value, '-4.56e-5');
});
