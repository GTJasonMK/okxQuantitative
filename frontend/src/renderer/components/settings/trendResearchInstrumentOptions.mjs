const SWAP_SUFFIX = '-USDT-SWAP';
const LIVE_STATE = 'live';
const USDT = 'USDT';
const SWAP_SEGMENT_LENGTH = 3;

const normalizeText = (value = '') => String(value || '').trim().toUpperCase();

const parseInstIdParts = (instId = '') => {
  const [baseCcy = '', quoteCcy = '', type = ''] = normalizeText(instId).split('-');
  return { baseCcy, quoteCcy, type };
};

const toOption = (instrument) => ({
  instId: instrument.inst_id,
  baseCcy: instrument.base_ccy || parseInstIdParts(instrument.inst_id).baseCcy,
  quoteCcy: instrument.quote_ccy || parseInstIdParts(instrument.inst_id).quoteCcy,
  state: instrument.state || '',
  label: instrument.inst_id,
});

const isEligibleSwap = (instrument) => {
  if (!instrument || normalizeText(instrument.state) !== LIVE_STATE.toUpperCase()) {
    return false;
  }

  const normalizedInstId = normalizeText(instrument.inst_id);
  const quoteCcy = normalizeText(instrument.quote_ccy) || parseInstIdParts(normalizedInstId).quoteCcy;

  return (
    quoteCcy === USDT &&
    normalizedInstId.endsWith(SWAP_SUFFIX) &&
    normalizedInstId.split('-').length === SWAP_SEGMENT_LENGTH
  );
};

export const buildTrendResearchInstrumentOptions = ({ instruments = [], selectedInstIds = [] } = {}) => {
  const options = instruments
    .filter(isEligibleSwap)
    .map(toOption)
    .sort((left, right) => left.instId.localeCompare(right.instId));

  const optionIds = new Set(options.map((item) => item.instId));
  const missingSelected = selectedInstIds
    .map((instId) => normalizeText(instId))
    .filter((instId) => instId && !optionIds.has(instId))
    .map((instId) => ({
      instId,
      baseCcy: instId.split('-')[0] || '',
      quoteCcy: USDT,
      state: 'missing',
      label: instId,
    }));

  return { options, missingSelected };
};

export const filterTrendResearchInstrumentOptions = (options = [], search = '') => {
  const keyword = normalizeText(search);
  if (!keyword) {
    return [...options];
  }

  return options.filter((item) => {
    return normalizeText(item.instId).includes(keyword) || normalizeText(item.baseCcy).includes(keyword);
  });
};
