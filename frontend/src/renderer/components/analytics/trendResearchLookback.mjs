export const TREND_LOOKBACK_OPTIONS = Object.freeze([
  { label: '30 分钟', seconds: 1800 },
  { label: '60 分钟', seconds: 3600 },
  { label: '90 分钟', seconds: 5400 },
  { label: '120 分钟', seconds: 7200 },
]);

export const DEFAULT_TREND_LOOKBACK_SECONDS = 3600;

const LOOKBACK_SET = new Set(TREND_LOOKBACK_OPTIONS.map((item) => item.seconds));

export const normalizeTrendLookbackSeconds = (value) => {
  const seconds = Number(value);
  if (LOOKBACK_SET.has(seconds)) {
    return seconds;
  }
  return DEFAULT_TREND_LOOKBACK_SECONDS;
};

export const formatTrendLookbackLabel = (value) => {
  const seconds = normalizeTrendLookbackSeconds(value);
  return `最近 ${Math.round(seconds / 60)} 分钟`;
};
