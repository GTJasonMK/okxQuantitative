import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

import {
  buildTrendFactorChartModel,
  buildTrendFactorLegendRows,
} from '../src/renderer/components/analytics/trendResearchFactorChartsViewModel.mjs';


test('buildTrendFactorChartModel builds overview duplication and perpetual axis mapping', () => {
  const payload = {
    second_buckets: [1712365200, 1712365201],
    series: [
      { factor_name: 'queue_imbalance', category: 'microstructure', available: true, tier: 0, unavailable_reason: '', values: [0.1, 0.2] },
      { factor_name: 'signed_trade_notional_z', category: 'trade_flow', available: true, tier: 0, unavailable_reason: '', values: [0.3, 0.7] },
      { factor_name: 'momentum_60s', category: 'price_structure', available: true, tier: 0, unavailable_reason: '', values: [0.0, 0.3] },
      { factor_name: 'basis_momentum', category: 'perpetual', available: true, tier: 0, unavailable_reason: '', values: [1.0, 2.0] },
      { factor_name: 'open_interest_level', category: 'perpetual', available: true, tier: 0, unavailable_reason: '', values: [1000.0, 1010.0] },
      { factor_name: 'price_oi_quadrant', category: 'perpetual', available: true, tier: 0, unavailable_reason: '', values: [0.5, -1.0] },
      { factor_name: 'multi_level_book_imbalance', category: 'microstructure', available: false, tier: 1, unavailable_reason: '依赖多档盘口', values: [] },
    ],
    score_meta: [
      { factor_name: 'queue_imbalance', stability_score: 0.41, spearman_ic: 0.22, category: 'microstructure', tier: 0, available: true, unavailable_reason: '' },
      { factor_name: 'signed_trade_notional_z', stability_score: 0.49, spearman_ic: 0.35, category: 'trade_flow', tier: 0, available: true, unavailable_reason: '' },
      { factor_name: 'momentum_60s', stability_score: 0.52, spearman_ic: 0.31, category: 'price_structure', tier: 0, available: true, unavailable_reason: '' },
      { factor_name: 'basis_momentum', stability_score: 0.44, spearman_ic: 0.28, category: 'perpetual', tier: 0, available: true, unavailable_reason: '' },
      { factor_name: 'open_interest_level', stability_score: 0.33, spearman_ic: -0.12, category: 'perpetual', tier: 0, available: true, unavailable_reason: '' },
      { factor_name: 'price_oi_quadrant', stability_score: 0.29, spearman_ic: 0.08, category: 'perpetual', tier: 0, available: true, unavailable_reason: '' },
      { factor_name: 'multi_level_book_imbalance', stability_score: null, spearman_ic: null, category: 'microstructure', tier: 1, available: false, unavailable_reason: '依赖多档盘口' },
    ],
  };

  const model = buildTrendFactorChartModel(payload);
  const legendRows = buildTrendFactorLegendRows(payload.score_meta);
  const perpetualGroup = model.groups.find((group) => group.key === 'perpetual');

  assert.equal(model.groups.length, 7);
  assert.equal(model.groups[0].key, 'overview');
  assert.equal(model.groups[0].series.length, 4);
  assert.equal(perpetualGroup.series.find((row) => row.factorName === 'basis_momentum').axis, 'left');
  assert.equal(perpetualGroup.series.find((row) => row.factorName === 'open_interest_level').axis, 'right');
  assert.equal(perpetualGroup.series.find((row) => row.factorName === 'price_oi_quadrant').lineType, 1);
  assert.equal(legendRows.find((row) => row.factorName === 'multi_level_book_imbalance').available, false);
});


test('api service exposes trend research factor series endpoint', () => {
  const apiSource = fs.readFileSync(
    new URL('../src/renderer/services/api.js', import.meta.url),
    'utf8',
  );

  assert.match(apiSource, /getTrendResearchFactorSeries/);
  assert.match(apiSource, /\/api\/trend-research\/factor-series\//);
});
