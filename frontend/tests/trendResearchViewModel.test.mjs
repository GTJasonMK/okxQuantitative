import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildTrendFeatureWindowModel,
  buildTrendFactorGroups,
  buildTrendFactorRows,
  buildTrendModelStatus,
  buildTrendPanelState,
  buildTrendRows,
  mergeTrendFeatureBars,
} from '../src/renderer/components/analytics/trendResearchViewModel.mjs';

test('buildTrendRows maps direct extrema predictions into row labels', () => {
  const rows = buildTrendRows([
    {
      inst_id: 'BTC-USDT-SWAP',
      current_price: 60000,
      trend_score: 100,
      trend_state: 'uptrend_confirmed',
      predicted_top_eta_seconds: 900,
      predicted_bottom_eta_seconds: 2280,
      predicted_top_price: 61212.080402,
      predicted_bottom_price: 59402.990025,
      predicted_top_return: 0.02,
      predicted_bottom_return: -0.01,
      top_time_distribution: Array.from({ length: 60 }, (_, index) => index === 14 ? 0.6 : 0),
      bottom_time_distribution: Array.from({ length: 60 }, (_, index) => index === 37 ? 0.7 : 0),
      confidence: 0.7,
      data_quality: 'ok',
    },
    {
      inst_id: 'ETH-USDT-SWAP',
      current_price: 3100,
      trend_score: 5.0,
      trend_state: 'range',
      predicted_top_eta_seconds: 1200,
      predicted_bottom_eta_seconds: 1800,
      predicted_top_price: 3150,
      predicted_bottom_price: 3050,
      predicted_top_return: 0.016,
      predicted_bottom_return: -0.016,
      top_time_distribution: Array.from({ length: 60 }, (_, index) => index === 19 ? 0.3 : 0),
      bottom_time_distribution: Array.from({ length: 60 }, (_, index) => index === 29 ? 0.35 : 0),
      confidence: 0.35,
      data_quality: 'partial',
    },
  ]);

  assert.equal(rows[0].instId, 'BTC-USDT-SWAP');
  assert.equal(rows[0].confidencePct, '70.0%');
  assert.equal(rows[0].topEtaLabel, '15 分钟');
  assert.equal(rows[0].bottomEtaLabel, '38 分钟');
  assert.equal(rows[0].topReturnLabel, '+2.0%');
  assert.equal(rows[0].distributionPointCount, 60);
  assert.equal(rows[1].qualityLabel, '部分数据');
  assert.equal(rows[0].trendStateLabel, '上行确认');
  assert.equal(rows[0].trendStateTone, 'up');
  assert.equal(rows[1].trendStateLabel, '震荡');
  assert.equal(rows[1].scoreSignClass, 'price-up');
});

test('buildTrendPanelState explains why the panel is empty', () => {
  const disabledState = buildTrendPanelState({
    enabled: false,
    status: 'disabled',
    whitelist: [],
    rows: [],
  });
  const collectingState = buildTrendPanelState({
    enabled: true,
    status: 'collecting',
    whitelist: ['BTC-USDT-SWAP'],
    rows: [],
  });

  assert.equal(disabledState.title, '趋势研究未启用');
  assert.match(disabledState.description, /系统设置/);
  assert.doesNotMatch(disabledState.description, /TREND_RESEARCH_ENABLED=true/);
  assert.equal(collectingState.tone, 'info');
  assert.match(collectingState.description, /正在等待首批实时数据/);
});

test('buildTrendPanelState points unconfigured users to settings instead of env', () => {
  const unconfiguredState = buildTrendPanelState({
    enabled: true,
    status: 'unconfigured',
    whitelist: [],
    rows: [],
  });

  assert.equal(unconfiguredState.title, '趋势研究白名单为空');
  assert.match(unconfiguredState.description, /系统设置/);
  assert.doesNotMatch(unconfiguredState.description, /config\/\.env/);
});

test('buildTrendPanelState exposes runtime collection errors explicitly', () => {
  const errorState = buildTrendPanelState({
    enabled: true,
    status: 'error',
    whitelist: ['BTC-USDT-SWAP'],
    rows: [],
    runtime_error: 'BTC-USDT-SWAP funding unavailable',
  });

  assert.equal(errorState.tone, 'danger');
  assert.equal(errorState.title, '趋势研究运行错误');
  assert.match(errorState.description, /funding unavailable/);
});

test('buildTrendModelStatus maps ready model diagnostics into a compact card model', () => {
  const model = buildTrendModelStatus({
    model_status: {
      ready: true,
      architecture: 'tcn',
      trained_at: '2026-04-06T00:00:00+00:00',
      input_minutes: 120,
      horizon_minutes: 60,
      selected_feature_count: 8,
      metrics: {
        top_time_mae_minutes: 4.0,
        bottom_time_mae_minutes: 5.0,
        top_price_mae_bps: 40.0,
        bottom_price_mae_bps: 55.0,
        joint_hit_rate: 0.42,
      },
    },
  });

  assert.equal(model.ready, true);
  assert.equal(model.title, '模型已就绪');
  assert.equal(model.probabilitySourceLabel, '直接极值模型');
  assert.equal(model.horizonLabel, '60 分钟');
  assert.equal(model.selectedFeatureCountLabel, '8');
  assert.match(model.trainedAtLabel, /2026/);
  assert.equal(model.validationCards[0].label, '顶部时间 MAE');
  assert.match(model.validationCards[0].value, /4\.000/);
  assert.equal(model.validationCards[4].label, '联合命中');
  assert.match(model.validationCards[4].value, /42\.0%/);
});

test('buildTrendModelStatus distinguishes model-not-ready state from collection status', () => {
  const model = buildTrendModelStatus({
    status: 'collecting',
    whitelist: ['BTC-USDT-SWAP'],
    model_status: {
      ready: false,
      trained_at: '',
      horizon_minutes: 0,
      selected_feature_count: 0,
    },
  });

  assert.equal(model.ready, false);
  assert.equal(model.title, '模型未就绪');
  assert.equal(model.probabilitySourceLabel, '未加载');
  assert.match(model.description, /尚未加载或训练/);
  assert.equal(model.horizonLabel, '--');
});

test('buildTrendFactorRows sorts factors by stability and formats labels', () => {
  const rows = buildTrendFactorRows([
    {
      factor_name: 'spread_bps_z',
      spearman_ic: 0.18,
      stability_score: 0.12,
      redundancy_cluster: 'microstructure',
      category: 'microstructure',
      tier: 0,
      available: true,
      unavailable_reason: '',
    },
    {
      factor_name: 'signed_trade_notional_z',
      spearman_ic: 0.42,
      stability_score: 0.42,
      redundancy_cluster: 'flow',
      category: 'trade_flow',
      tier: 0,
      available: true,
      unavailable_reason: '',
    },
  ]);

  assert.equal(rows[0].factorName, 'signed_trade_notional_z');
  assert.equal(rows[0].factorLabel, '净主动成交');
  assert.equal(rows[0].stabilityScore, '0.420');
  assert.equal(rows[1].categoryKey, 'microstructure');
  assert.equal(rows[0].categoryLabel, '成交流');
});

test('buildTrendFactorRows compacts oversized or tiny factor metrics for narrow cards', () => {
  const rows = buildTrendFactorRows([
    {
      factor_name: 'signed_trade_notional_z',
      spearman_ic: -0.0000456,
      stability_score: 123456789,
      redundancy_cluster: 'flow',
      category: 'trade_flow',
      tier: 0,
      available: true,
      unavailable_reason: '',
    },
  ]);

  assert.equal(rows[0].stabilityScore, '1.23e+8');
  assert.equal(rows[0].spearmanIc, '-4.56e-5');
});

test('buildTrendFactorRows keeps unavailable factor placeholders explicit', () => {
  const rows = buildTrendFactorRows([
    {
      factor_name: 'multi_level_book_imbalance',
      spearman_ic: null,
      stability_score: null,
      redundancy_cluster: 'microstructure',
      category: 'microstructure',
      tier: 1,
      available: false,
      unavailable_reason: '依赖多档盘口',
    },
  ]);

  assert.equal(rows[0].available, false);
  assert.equal(rows[0].stabilityScore, '--');
  assert.equal(rows[0].spearmanIc, '--');
  assert.equal(rows[0].statusLabel, '依赖多档盘口');
});

test('buildTrendFactorGroups groups rows by factor category order', () => {
  const groups = buildTrendFactorGroups([
    {
      factorName: 'signed_trade_notional_z',
      factorLabel: '净主动成交',
      categoryKey: 'trade_flow',
      categoryLabel: '成交流',
      available: true,
      stabilityScoreValue: 0.4,
    },
    {
      factorName: 'queue_imbalance',
      factorLabel: '顶档队列不平衡',
      categoryKey: 'microstructure',
      categoryLabel: '盘口微观结构',
      available: true,
      stabilityScoreValue: 0.3,
    },
    {
      factorName: 'amihud_illiquidity',
      factorLabel: 'Amihud 非流动性',
      categoryKey: 'liquidity',
      categoryLabel: '流动性与冲击',
      available: true,
      stabilityScoreValue: 0.2,
    },
  ]);

  assert.deepEqual(groups.map((group) => group.key), ['microstructure', 'trade_flow', 'liquidity']);
  assert.equal(groups[0].items[0].factorName, 'queue_imbalance');
});

test('buildTrendFeatureWindowModel builds compact window metadata and timeline bars', () => {
  const model = buildTrendFeatureWindowModel([
    {
      second_bucket: 1712365199,
      signed_trade_notional: -20000,
      trade_count: 3,
      spread_bps: 2.4,
      oi_delta: -5,
      basis_zscore: -0.6,
      data_quality: 'partial',
    },
    {
      second_bucket: 1712365200,
      signed_trade_notional: 62500,
      trade_count: 12,
      spread_bps: 1.8,
      oi_delta: 35,
      basis_zscore: 4.2,
      data_quality: 'ok',
    },
  ]);

  assert.equal(model.qualityLabel, '完整');
  assert.equal(model.timelineSegments[0].tone, 'down');
  assert.equal(model.timelineSegments[1].tone, 'up');
});

test('mergeTrendFeatureBars prefers newer buckets and keeps the latest window', () => {
  const rows = mergeTrendFeatureBars(
    [
      { second_bucket: 1, signed_trade_notional: -1 },
      { second_bucket: 2, signed_trade_notional: 2 },
    ],
    [
      { second_bucket: 2, signed_trade_notional: 22 },
      { second_bucket: 3, signed_trade_notional: 3 },
    ],
    2,
  );

  assert.deepEqual(rows.map((item) => item.second_bucket), [2, 3]);
  assert.equal(rows[0].signed_trade_notional, 22);
  assert.equal(rows[1].signed_trade_notional, 3);
});
