import { formatPercentValue } from '../../utils/formatting.js';

const SUMMARY_CARD_DEFS = [
  ['当前价', 'currentPriceLabel'],
  ['顶部时间', 'topEtaLabel'],
  ['顶部价格', 'topPriceLabel'],
  ['顶部空间', 'topReturnLabel'],
  ['底部时间', 'bottomEtaLabel'],
  ['底部价格', 'bottomPriceLabel'],
  ['底部空间', 'bottomReturnLabel'],
  ['置信度', 'confidencePct'],
  ['数据质量', 'qualityLabel'],
];

const DISTRIBUTION_GROUPS = [
  ['top', '顶部时间分布', '未来窗口内顶部落在各分钟桶的概率质量。', '#22C55E'],
  ['bottom', '底部时间分布', '未来窗口内底部落在各分钟桶的概率质量。', '#F97316'],
];

const buildSummaryCards = (row) => {
  return SUMMARY_CARD_DEFS.map(([label, key]) => ({
    label,
    value: row?.[key] || '--',
  }));
};

const buildDistributionPoints = (values = []) => {
  return values.reduce((points, value, index) => {
    const probability = Number(value);
    if (!Number.isFinite(probability)) {
      return points;
    }
    points.push({
      time: (index + 1) * 60,
      value: probability,
    });
    return points;
  }, []);
};

const formatProbability = (value) => {
  return formatPercentValue(Number(value) * 100, 1);
};

const buildDistributionGroup = ([key, label, caption, color], row = {}) => {
  const sourceKey = key === 'top' ? 'topTimeSeries' : 'bottomTimeSeries';
  const points = buildDistributionPoints(row?.[sourceKey] || []);
  return {
    key,
    label,
    caption,
    hasData: points.length > 0,
    emptyLabel: `当前没有${label}数据。`,
    series: points.length === 0 ? [] : [{
      factorName: `${key}-distribution`,
      label: key === 'top' ? '顶部概率' : '底部概率',
      color,
      axis: 'right',
      data: points,
      tooltipValueFormatter: (value) => formatProbability(value),
    }],
  };
};

export const buildTrendPredictionSummaryModel = ({ selectedTrendRow, processStateLabel }) => {
  if (!selectedTrendRow) {
    return {
      caption: '当前没有可展示的合约结论。',
      cards: [],
    };
  }
  const bucketCount = Number(selectedTrendRow.distributionPointCount || 0);
  const distributionText = bucketCount > 0
    ? `基于 ${bucketCount} 个未来分钟桶输出顶底时间分布。`
    : '当前仍在等待时间分布输出。';
  return {
    caption: `${processStateLabel || '推断中'} · ${distributionText}`,
    cards: buildSummaryCards(selectedTrendRow),
  };
};

export const buildTrendTimeDistributionModel = (selectedTrendRow = null) => {
  return {
    groups: DISTRIBUTION_GROUPS.map((definition) => buildDistributionGroup(definition, selectedTrendRow)),
  };
};
