const FACTOR_LABELS = {
  signed_trade_notional_z: '净主动成交',
  spread_bps_z: '价差',
  oi_delta_z: '未平仓变化',
  basis_zscore_z: '基差偏离',
  trade_count_z: '成交笔数',
  queue_imbalance: '顶档队列不平衡',
  microprice_premium_bps: '微价格偏离',
  spread_level_bps: '价差水平',
  ofi_top_book: '顶档 OFI',
  signed_volume_imbalance: '主动买卖不平衡',
  trade_intensity: '成交强度',
  large_trade_share: '大单占比',
  buy_burst_strength: '主动买爆发',
  sell_burst_strength: '主动卖爆发',
  momentum_30s: '30 秒动量',
  momentum_60s: '60 秒动量',
  momentum_300s: '300 秒动量',
  distance_to_window_extrema: '区间位置',
  breakout_pressure: '突破压力',
  realized_volatility: '已实现波动率',
  realized_range: '区间波动',
  trend_efficiency: '趋势效率',
  basis_bps: '基差水平',
  basis_momentum: '基差动量',
  funding_rate_level: '资金费率',
  funding_rate_delta: '资金费率变化',
  open_interest_level: '持仓量水平',
  open_interest_delta: '持仓量变化',
  price_oi_quadrant: '价格-持仓象限',
  funding_basis_divergence: '资金费率-基差背离',
  premium_shock: '溢价冲击',
  amihud_illiquidity: 'Amihud 非流动性',
  impact_per_notional: '单位成交额冲击',
  depth_to_vol_ratio: '深度-波动比',
  multi_level_book_imbalance: '多档深度不平衡',
  book_slope: '盘口斜率',
};

const FACTOR_CATEGORY_META = {
  microstructure: {
    label: '盘口微观结构',
    caption: '盘口厚度、价差、微价格与顶档供需。',
  },
  trade_flow: {
    label: '成交流',
    caption: '主动打单方向、强度与连续性。',
  },
  price_structure: {
    label: '价格结构',
    caption: '动量、区间位置、波动扩张与趋势效率。',
  },
  perpetual: {
    label: '永续结构',
    caption: '基差、资金费率、持仓与拥挤度。',
  },
  liquidity: {
    label: '流动性与冲击',
    caption: '价格推进成本与盘口承接能力。',
  },
  uncategorized: {
    label: '其他',
    caption: '未分类因子。',
  },
};

export const FACTOR_CATEGORY_ORDER = [
  'microstructure',
  'trade_flow',
  'price_structure',
  'perpetual',
  'liquidity',
  'uncategorized',
];

export const resolveFactorLabel = (factorName) => {
  return FACTOR_LABELS[factorName] || factorName || '--';
};

export const resolveFactorCategoryMeta = (categoryKey) => {
  return FACTOR_CATEGORY_META[categoryKey] || FACTOR_CATEGORY_META.uncategorized;
};
