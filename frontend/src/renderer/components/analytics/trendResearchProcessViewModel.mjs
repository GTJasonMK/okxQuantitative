import { formatCompactNumber, formatCompactSignedNumber } from '../../utils/formatting.js';
import { formatEtaLabel, formatReturnLabel } from './trendResearchPredictionFormatting.mjs';

const PROCESS_STATE_LABELS = {
  inference_ready: '推断完成',
  feature_ready: '特征已生成',
  waiting_trade: '等待逐笔成交',
  waiting_book: '等待盘口',
  waiting_state: '等待合约状态',
  collecting: '采集中',
};

const STAGE_ORDER = ['trade', 'book', 'state', 'feature', 'inference'];

const SUMMARY_CARD_DEFS = [
  ['白名单', 'whitelist_count'],
  ['逐笔就绪', 'trade_ready_count'],
  ['盘口就绪', 'book_ready_count'],
  ['状态就绪', 'state_ready_count'],
  ['特征已出', 'feature_ready_count'],
  ['推断已出', 'inference_ready_count'],
];

const FEATURE_COUNT_OPTIONS = Object.freeze({
  digits: 0,
  maxChars: 7,
  scientificDigits: 2,
});

const FEATURE_SIGNED_OPTIONS = Object.freeze({
  digits: 1,
  maxChars: 8,
  scientificDigits: 2,
});

const FEATURE_NUMBER_OPTIONS = Object.freeze({
  digits: 1,
  maxChars: 8,
  scientificDigits: 2,
});

const clamp = (value, min, max) => Math.min(Math.max(value, min), max);

const formatSigned = (value) => {
  const number = Number(value || 0);
  return `${number >= 0 ? '+' : ''}${number.toFixed(1)}`;
};

const formatPercent = (value) => `${(Number(value || 0) * 100).toFixed(1)}%`;
const formatRuntimeNumber = (value) => formatCompactNumber(value || 0, FEATURE_NUMBER_OPTIONS);
const formatTradeSide = (value) => String(value || '--').toUpperCase();

const buildSummaryCards = (summary = {}) => {
  return SUMMARY_CARD_DEFS.map(([label, key]) => ({
    label,
    value: String(summary[key] ?? 0),
  }));
};

const buildStageRows = (stages = {}) => {
  return STAGE_ORDER.map((key) => ({
    key,
    ready: !!stages[key]?.ready,
    label: stages[key]?.label || '',
  }));
};

export const buildTrendTimelineSegments = (bars = []) => {
  const normalizedBars = Array.isArray(bars) ? bars : [];
  const maxAbsNotional = normalizedBars.reduce((maxValue, bar) => {
    return Math.max(maxValue, Math.abs(Number(bar?.signed_trade_notional || 0)));
  }, 0);
  const denominator = maxAbsNotional || 1;

  return normalizedBars.map((bar, index) => {
    const signedTradeNotional = Number(bar?.signed_trade_notional || 0);
    return {
      key: `${bar?.second_bucket || index}`,
      height: signedTradeNotional === 0 ? 12 : clamp(Math.round(Math.abs(signedTradeNotional) / denominator * 100), 24, 100),
      tone: signedTradeNotional > 0 ? 'up' : (signedTradeNotional < 0 ? 'down' : 'flat'),
      qualityTone: bar?.data_quality === 'ok' ? 'ok' : 'partial',
      title: `${bar?.second_bucket || '--'} | ${formatSigned(signedTradeNotional)}`,
    };
  });
};

const buildInstrumentCard = (instrument = {}) => {
  const latestFeatureBar = instrument.latest_feature_bar || null;
  const latestInference = instrument.latest_inference || null;
  const recentBars = Array.isArray(instrument.recent_feature_bars)
    ? instrument.recent_feature_bars
    : [];

  return {
    instId: instrument.inst_id || '--',
    pipelineState: instrument.pipeline_state || '',
    displayState: PROCESS_STATE_LABELS[instrument.pipeline_state] || '采集中',
    stages: buildStageRows(instrument.stages),
    runtime: instrument.runtime || {},
    runtimeStats: [
      { label: '待处理逐笔', value: formatCompactNumber(instrument.runtime?.pending_trade_count || 0, FEATURE_COUNT_OPTIONS) },
      { label: '最新成交价', value: formatRuntimeNumber(instrument.runtime?.last_trade_price) },
      { label: '最新方向', value: formatTradeSide(instrument.runtime?.last_trade_side) },
    ],
    featureStats: [
      { label: '逐笔数', value: formatCompactNumber(latestFeatureBar?.trade_count || 0, FEATURE_COUNT_OPTIONS) },
      { label: '净成交额', value: formatCompactSignedNumber(latestFeatureBar?.signed_trade_notional || 0, FEATURE_SIGNED_OPTIONS) },
      { label: '价差(bps)', value: formatCompactNumber(latestFeatureBar?.spread_bps || 0, FEATURE_NUMBER_OPTIONS) },
      { label: 'OI 变化', value: formatCompactSignedNumber(latestFeatureBar?.oi_delta || 0, FEATURE_SIGNED_OPTIONS) },
      { label: '基差', value: formatCompactNumber(latestFeatureBar?.basis_zscore || 0, FEATURE_NUMBER_OPTIONS) },
      { label: '质量', value: latestFeatureBar?.data_quality === 'ok' ? '完整' : '部分' },
    ],
    latestInference: latestInference ? {
      trendState: latestInference.trend_state || 'range',
      trendScore: Number(latestInference.trend_score || 0).toFixed(1),
      confidencePct: formatPercent(latestInference.confidence || 0),
      topEtaLabel: formatEtaLabel(latestInference.predicted_top_eta_seconds),
      bottomEtaLabel: formatEtaLabel(latestInference.predicted_bottom_eta_seconds),
      topPriceLabel: formatCompactNumber(latestInference.predicted_top_price || 0, FEATURE_NUMBER_OPTIONS),
      bottomPriceLabel: formatCompactNumber(latestInference.predicted_bottom_price || 0, FEATURE_NUMBER_OPTIONS),
      topReturnLabel: formatReturnLabel(latestInference.predicted_top_return),
      bottomReturnLabel: formatReturnLabel(latestInference.predicted_bottom_return),
    } : null,
    recentBars,
    timelineSegments: buildTrendTimelineSegments(recentBars),
  };
};

export const buildTrendProcessPanelModel = (payload = {}) => {
  const instruments = Array.isArray(payload.instruments) ? payload.instruments : [];

  return {
    summaryCards: buildSummaryCards(payload.summary),
    summaryStats: {
      whitelist_count: Number(payload.summary?.whitelist_count || 0),
      trade_ready_count: Number(payload.summary?.trade_ready_count || 0),
      book_ready_count: Number(payload.summary?.book_ready_count || 0),
      state_ready_count: Number(payload.summary?.state_ready_count || 0),
      feature_ready_count: Number(payload.summary?.feature_ready_count || 0),
      inference_ready_count: Number(payload.summary?.inference_ready_count || 0),
    },
    instruments: instruments.map(buildInstrumentCard),
    barLimit: Number(payload.bar_limit || 0),
  };
};
