import { normalizeMonitorSymbol } from '../utils/formatting.js';

const MIN_CORRELATION_SYMBOLS = 2;
const DEFAULT_CORRELATION_PICK_COUNT = 3;

export function extractAvailableBaseSymbols(rows = []) {
  return [...new Set((rows || []).map(row => normalizeMonitorSymbol(row?.inst_id)).filter(Boolean))];
}

export function filterCorrelationSymbols(rows = [], options = {}) {
  const instType = String(options.instType || 'SPOT').toUpperCase();
  const timeframe = String(options.timeframe || '1H').trim();
  return extractAvailableBaseSymbols(
    (rows || []).filter((row) => {
      if (String(row?.inst_type || '').toUpperCase() !== instType) {
        return false;
      }
      return Array.isArray(row?.timeframes) && row.timeframes.includes(timeframe);
    }),
  );
}

export function reconcileCorrelationSelection(selectedSymbols = [], availableSymbols = []) {
  const nextSelected = (selectedSymbols || []).filter(symbol => availableSymbols.includes(symbol));
  if (nextSelected.length >= MIN_CORRELATION_SYMBOLS) {
    return nextSelected;
  }
  return availableSymbols.slice(0, DEFAULT_CORRELATION_PICK_COUNT);
}

export function buildCorrelationAvailabilityMessage(options = {}) {
  const instType = String(options.instType || 'SPOT').toUpperCase();
  const timeframe = String(options.timeframe || '1H').trim();
  return `当前 ${instType} / ${timeframe} 本地数据不足，至少需要 2 个币种`;
}
