const normalizeNumber = (value) => {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return 'na';
  }
  return String(number);
};

export const resolveTrendDiagnosticsTimelineKey = (item = {}) => {
  return [
    `seq:${normalizeNumber(item.sequence)}`,
    `kind:${String(item.kind || 'event')}`,
    `emitted:${normalizeNumber(item.emitted_at)}`,
    `bucket:${normalizeNumber(item.second_bucket)}`,
  ].join('|');
};
