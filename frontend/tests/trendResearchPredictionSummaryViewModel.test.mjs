import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildTrendPredictionSummaryModel,
  buildTrendTimeDistributionModel,
} from '../src/renderer/components/analytics/trendResearchPredictionSummaryViewModel.mjs';

test('buildTrendPredictionSummaryModel maps direct extrema labels into compact summary cards', () => {
  const model = buildTrendPredictionSummaryModel({
    selectedTrendRow: {
      instId: 'BTC-USDT-SWAP',
      currentPriceLabel: '60000.00',
      topEtaLabel: '15 分钟',
      topPriceLabel: '61212.08',
      topReturnLabel: '+2.0%',
      bottomEtaLabel: '38 分钟',
      bottomPriceLabel: '59402.99',
      bottomReturnLabel: '-1.0%',
      confidencePct: '70.0%',
      qualityLabel: '完整',
      distributionPointCount: 60,
    },
    processStateLabel: '推断完成',
  });

  assert.equal(model.caption, '推断完成 · 基于 60 个未来分钟桶输出顶底时间分布。');
  assert.deepEqual(
    model.cards.map((card) => card.label),
    ['当前价', '顶部时间', '顶部价格', '顶部空间', '底部时间', '底部价格', '底部空间', '置信度', '数据质量'],
  );
  assert.equal(model.cards[0].value, '60000.00');
  assert.equal(model.cards[1].value, '15 分钟');
  assert.equal(model.cards[5].value, '59402.99');
  assert.equal(model.cards[7].value, '70.0%');
});

test('buildTrendPredictionSummaryModel keeps empty states explicit when no contract is selected', () => {
  const model = buildTrendPredictionSummaryModel({
    selectedTrendRow: null,
    processStateLabel: '',
  });

  assert.equal(model.caption, '当前没有可展示的合约结论。');
  assert.deepEqual(model.cards, []);
});

test('buildTrendTimeDistributionModel converts top and bottom distributions into chart groups', () => {
  const model = buildTrendTimeDistributionModel({
    topTimeSeries: [0.1, 0.3, 0.6],
    bottomTimeSeries: [0.5, 0.25, 0.25],
  });

  assert.equal(model.groups.length, 2);
  assert.equal(model.groups[0].label, '顶部时间分布');
  assert.equal(model.groups[0].series[0].data[2].time, 180);
  assert.equal(model.groups[0].series[0].data[2].value, 0.6);
  assert.equal(model.groups[1].label, '底部时间分布');
  assert.equal(model.groups[1].series[0].data[0].time, 60);
  assert.equal(model.groups[1].series[0].data[0].value, 0.5);
});
