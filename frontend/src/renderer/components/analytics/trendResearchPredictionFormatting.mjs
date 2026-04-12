import { formatPercentValue } from '../../utils/formatting.js';

export const formatEtaLabel = (seconds) => {
  const value = Number(seconds);
  if (!Number.isFinite(value) || value <= 0) {
    return '--';
  }
  return `${Math.round(value / 60)} 分钟`;
};

export const formatReturnLabel = (value) => {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return '--';
  }
  return `${number >= 0 ? '+' : ''}${formatPercentValue(number * 100, 1)}`;
};
