const MARKET_MODE = 'market';
const BACKTEST_MODE = 'backtest';

const MARKET_CONFIG = Object.freeze({
  constrainVisibleRange: true,
  chartOverrides: {},
});

const BACKTEST_CONFIG = Object.freeze({
  constrainVisibleRange: false,
  chartOverrides: {
    timeScale: {
      borderColor: 'rgba(255, 255, 255, 0.06)',
      timeVisible: true,
      secondsVisible: false,
      rightOffset: 0,
      barSpacing: 6,
      minBarSpacing: 0.5,
      fixLeftEdge: true,
      fixRightEdge: true,
      shiftVisibleRangeOnNewBar: false,
    },
  },
});

export function resolveKlineChartModeConfig(mode = MARKET_MODE) {
  if (mode === BACKTEST_MODE) {
    return BACKTEST_CONFIG;
  }

  return MARKET_CONFIG;
}

