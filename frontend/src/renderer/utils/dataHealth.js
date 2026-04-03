export const DATA_HEALTH_STATUS_LABELS = {
  healthy: '良好',
  degraded: '待补齐',
  stale: '陈旧',
  missing: '未入库',
};

export const normalizeDataHealthSymbol = (value) => {
  if (typeof value !== 'string') {
    return '';
  }
  const normalized = value.trim().toUpperCase();
  if (!normalized) {
    return '';
  }
  return normalized.endsWith('-SWAP') ? normalized.slice(0, -5) : normalized;
};

export const normalizeDataHealthInstType = (value) => {
  const normalized = String(value || '').trim().toUpperCase();
  return normalized === 'SWAP' ? 'SWAP' : 'SPOT';
};

export const getDataHealthMarket = (row, instType) => {
  if (!row || typeof row !== 'object') {
    return null;
  }
  const markets = row.markets && typeof row.markets === 'object' ? row.markets : {};
  return markets[normalizeDataHealthInstType(instType)] || null;
};

export const getDataHealthScore = (row) => {
  const score = Number(row?.health_score);
  return Number.isFinite(score) ? Math.round(score) : 0;
};

export const getDataHealthMissingTimeframes = (row) => (
  Array.isArray(row?.missing_timeframes) ? row.missing_timeframes : []
);

export const resolveDataHealthStatus = (row, instType) => {
  if (row?.has_local_data && !getDataHealthMarket(row, instType)) {
    return 'missing';
  }
  const raw = String(row?.status || 'missing').trim().toLowerCase();
  return DATA_HEALTH_STATUS_LABELS[raw] ? raw : 'missing';
};

export const getDataHealthStatusLabel = (row, instType) => (
  DATA_HEALTH_STATUS_LABELS[resolveDataHealthStatus(row, instType)] || DATA_HEALTH_STATUS_LABELS.missing
);

export const formatDataHealthBadgeText = (row, instType) => {
  const normalizedInstType = normalizeDataHealthInstType(instType);
  if (!row) {
    return '数据缺失';
  }
  if (!getDataHealthMarket(row, normalizedInstType) && row?.has_local_data) {
    return `${normalizedInstType}缺失`;
  }
  const missing = getDataHealthMissingTimeframes(row);
  if (missing.length > 0) {
    const preview = missing.slice(0, 2).join('/');
    return `缺 ${preview}${missing.length > 2 ? '+' : ''}`;
  }
  return `数据${getDataHealthStatusLabel(row, normalizedInstType)}`;
};

export const formatDataHealthSummaryText = (row, instType) => {
  const normalizedInstType = normalizeDataHealthInstType(instType);
  if (!row) {
    return `${normalizedInstType} 本地数据库暂无数据`;
  }

  const summary = [`${getDataHealthStatusLabel(row, normalizedInstType)} ${getDataHealthScore(row)}`];
  const market = getDataHealthMarket(row, normalizedInstType);
  if (market) {
    const timeframeCount = Array.isArray(market.timeframes) ? market.timeframes.length : 0;
    summary.push(`${normalizedInstType} ${timeframeCount} 个周期`);
    const missing = getDataHealthMissingTimeframes(row);
    if (missing.length > 0) {
      summary.push(`缺 ${missing.join('/')}`);
    } else {
      summary.push('关键周期已覆盖');
    }
  } else {
    summary.push(`${normalizedInstType} 未入库`);
  }
  return summary.join(' · ');
};
