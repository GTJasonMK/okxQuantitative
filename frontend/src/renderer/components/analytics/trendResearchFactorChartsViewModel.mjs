import { formatCompactNumber } from '../../utils/formatting.js';
import { buildTrendFactorRows } from './trendResearchViewModel.mjs';

const STEP_LINE_TYPE = 1;
const DEFAULT_COLOR = '#94A3B8';
const TOOLTIP_NUMBER_OPTIONS = Object.freeze({
  digits: 3,
  maxChars: 12,
  scientificDigits: 2,
});

const GROUP_DEFINITIONS = Object.freeze([
  {
    key: 'overview',
    label: '总览图',
    caption: '跨分类代表因子的共振、切换与背离。',
    normalize: true,
    factors: ['queue_imbalance', 'signed_trade_notional_z', 'momentum_60s', 'realized_volatility', 'basis_momentum', 'impact_per_notional'],
  },
  {
    key: 'microstructure',
    label: '盘口微观结构',
    caption: '盘口厚度、价差与微价格压力。',
    normalize: true,
    factors: ['spread_bps_z', 'queue_imbalance', 'microprice_premium_bps', 'spread_level_bps', 'ofi_top_book', 'multi_level_book_imbalance', 'book_slope'],
  },
  {
    key: 'trade_flow',
    label: '成交流与订单流',
    caption: '主动打单方向、强度和持续性。',
    normalize: true,
    factors: ['signed_trade_notional_z', 'trade_count_z', 'signed_volume_imbalance', 'trade_intensity', 'large_trade_share', 'buy_burst_strength', 'sell_burst_strength'],
  },
  {
    key: 'price_structure',
    label: '价格结构',
    caption: '动量、区间位置与突破压力。',
    normalize: true,
    factors: ['momentum_30s', 'momentum_60s', 'momentum_300s', 'distance_to_window_extrema', 'breakout_pressure'],
  },
  {
    key: 'volatility_efficiency',
    label: '波动与效率',
    caption: '波动扩张、区间波动与趋势效率。',
    normalize: true,
    factors: ['realized_volatility', 'realized_range', 'trend_efficiency'],
  },
  {
    key: 'perpetual',
    label: '永续特有结构',
    caption: '资金费率、基差、持仓与四象限结构。',
    normalize: false,
    factors: ['oi_delta_z', 'basis_zscore_z', 'basis_bps', 'basis_momentum', 'funding_rate_level', 'funding_rate_delta', 'open_interest_level', 'open_interest_delta', 'price_oi_quadrant', 'funding_basis_divergence', 'premium_shock'],
  },
  {
    key: 'liquidity',
    label: '流动性与冲击成本',
    caption: '非流动性、单位冲击和深度承接能力。',
    normalize: true,
    factors: ['amihud_illiquidity', 'impact_per_notional', 'depth_to_vol_ratio'],
  },
]);

const PERPETUAL_LEFT_AXIS = new Set([
  'basis_zscore_z',
  'basis_bps',
  'basis_momentum',
  'funding_rate_level',
  'funding_rate_delta',
  'funding_basis_divergence',
  'premium_shock',
]);

const PERPETUAL_RIGHT_AXIS = new Set([
  'oi_delta_z',
  'open_interest_level',
  'open_interest_delta',
]);

const FIXED_RANGE_FACTORS = new Set(['price_oi_quadrant']);

const FACTOR_COLORS = Object.freeze({
  queue_imbalance: '#F59E0B',
  signed_trade_notional_z: '#22C55E',
  momentum_60s: '#38BDF8',
  realized_volatility: '#FB7185',
  basis_momentum: '#A78BFA',
  impact_per_notional: '#F97316',
  spread_bps_z: '#CBD5E1',
  microprice_premium_bps: '#2DD4BF',
  spread_level_bps: '#F8FAFC',
  ofi_top_book: '#60A5FA',
  multi_level_book_imbalance: '#818CF8',
  book_slope: '#C084FC',
  trade_count_z: '#E879F9',
  signed_volume_imbalance: '#34D399',
  trade_intensity: '#06B6D4',
  large_trade_share: '#F97316',
  buy_burst_strength: '#4ADE80',
  sell_burst_strength: '#F87171',
  momentum_30s: '#FCD34D',
  momentum_300s: '#7DD3FC',
  distance_to_window_extrema: '#10B981',
  breakout_pressure: '#F43F5E',
  realized_range: '#A3E635',
  trend_efficiency: '#F472B6',
  oi_delta_z: '#93C5FD',
  basis_zscore_z: '#F5D0FE',
  basis_bps: '#FDE68A',
  funding_rate_level: '#C4B5FD',
  funding_rate_delta: '#DDD6FE',
  open_interest_level: '#38BDF8',
  open_interest_delta: '#0EA5E9',
  price_oi_quadrant: '#E2E8F0',
  funding_basis_divergence: '#FB7185',
  premium_shock: '#FDBA74',
  amihud_illiquidity: '#FCA5A5',
  depth_to_vol_ratio: '#86EFAC',
});

const normalizeNumber = (value) => {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
};

const normalizeSeriesValues = (values = []) => values.map(normalizeNumber);

const zscoreValues = (values = []) => {
  const finiteValues = values.filter((value) => Number.isFinite(value));
  if (finiteValues.length === 0) {
    return [];
  }
  const mean = finiteValues.reduce((sum, value) => sum + value, 0) / finiteValues.length;
  const variance = finiteValues.reduce((sum, value) => sum + ((value - mean) ** 2), 0) / finiteValues.length;
  if (variance <= 0) {
    return values.map((value) => (Number.isFinite(value) ? 0 : null));
  }
  const std = Math.sqrt(variance);
  return values.map((value) => (Number.isFinite(value) ? ((value - mean) / std) : null));
};

const toChartPoints = (secondBuckets = [], values = []) => {
  return secondBuckets.reduce((points, secondBucket, index) => {
    const value = values[index];
    if (!Number.isFinite(value)) {
      return points;
    }
    points.push({ time: Number(secondBucket), value });
    return points;
  }, []);
};

const formatTooltipValue = (value) => {
  return formatCompactNumber(value, TOOLTIP_NUMBER_OPTIONS);
};

const buildFactorMetaMap = (scoreMeta = []) => {
  return new Map(buildTrendFactorRows(scoreMeta).map((row) => [row.factorName, row]));
};

const resolveAxis = (factorName) => {
  if (PERPETUAL_LEFT_AXIS.has(factorName)) {
    return 'left';
  }
  if (PERPETUAL_RIGHT_AXIS.has(factorName)) {
    return 'right';
  }
  return 'right';
};

const buildSeriesRow = (factorName, secondBuckets, rawSeries, factorMeta, normalize) => {
  if (!rawSeries || rawSeries.available === false) {
    return null;
  }
  const rawValues = normalizeSeriesValues(rawSeries.values);
  const displayValues = normalize ? zscoreValues(rawValues) : rawValues;
  const data = toChartPoints(secondBuckets, displayValues);
  if (data.length === 0) {
    return null;
  }
  const rawValueByTime = new Map(secondBuckets.map((bucket, index) => [Number(bucket), rawValues[index]]));
  return {
    factorName,
    label: factorMeta?.factorLabel || factorName,
    categoryKey: factorMeta?.categoryKey || rawSeries.category || 'uncategorized',
    color: FACTOR_COLORS[factorName] || DEFAULT_COLOR,
    axis: resolveAxis(factorName),
    lineType: FIXED_RANGE_FACTORS.has(factorName) ? STEP_LINE_TYPE : 0,
    fixedRange: FIXED_RANGE_FACTORS.has(factorName) ? [-1, 1] : null,
    data,
    tooltipValueFormatter: (_value, time) => {
      return formatTooltipValue(rawValueByTime.get(Number(time)));
    },
  };
};

const buildGroup = (definition, secondBuckets, seriesMap, factorMetaMap) => {
  const series = definition.factors
    .map((factorName) => {
      return buildSeriesRow(
        factorName,
        secondBuckets,
        seriesMap.get(factorName),
        factorMetaMap.get(factorName),
        definition.normalize,
      );
    })
    .filter(Boolean);
  return {
    key: definition.key,
    label: definition.label,
    caption: definition.caption,
    normalize: definition.normalize,
    hasLeftAxis: definition.key === 'perpetual',
    hasData: series.length > 0,
    series,
  };
};

export const buildTrendFactorLegendRows = (scoreMeta = []) => {
  return buildTrendFactorRows(scoreMeta).map((row) => ({
    ...row,
    selectable: row.available !== false,
  }));
};

export const buildTrendFactorChartModel = (payload = {}) => {
  const secondBuckets = Array.isArray(payload.second_buckets) ? payload.second_buckets.map(Number) : [];
  const seriesRows = Array.isArray(payload.series) ? payload.series : [];
  const legendRows = buildTrendFactorLegendRows(payload.score_meta || []);
  const factorMetaMap = buildFactorMetaMap(payload.score_meta || []);
  const seriesMap = new Map(seriesRows.map((row) => [row.factor_name, row]));
  return {
    secondBuckets,
    legendRows,
    factorMetaMap,
    groups: GROUP_DEFINITIONS.map((definition) => {
      return buildGroup(definition, secondBuckets, seriesMap, factorMetaMap);
    }),
  };
};
