import { buildTrendTimelineSegments } from './trendResearchProcessViewModel.mjs';
import { buildTrendModelStatus } from './trendResearchModelStatusViewModel.mjs';
import { formatCompactNumber, formatPercentValue, formatPrice } from '../../utils/formatting.js';
import {
  FACTOR_CATEGORY_ORDER,
  resolveFactorCategoryMeta,
  resolveFactorLabel,
} from './trendResearchFactorMeta.mjs';
import { formatEtaLabel, formatReturnLabel } from './trendResearchPredictionFormatting.mjs';

const TREND_STATE_META = {
  uptrend_confirmed: { label: '上行确认', tone: 'up' },
  downtrend_confirmed: { label: '下行确认', tone: 'down' },
  range: { label: '震荡', tone: 'neutral' },
  model_not_ready: { label: '模型未就绪', tone: 'warning' },
};

const FACTOR_CARD_NUMBER_OPTIONS = Object.freeze({
  digits: 3,
  maxChars: 8,
  scientificDigits: 2,
});

const resolveTrendStateMeta = (trendState) => {
  return TREND_STATE_META[trendState] || TREND_STATE_META.range;
};

const compareFactorRows = (left, right) => {
  const leftAvailable = left?.available !== false ? 1 : 0;
  const rightAvailable = right?.available !== false ? 1 : 0;
  if (leftAvailable !== rightAvailable) {
    return rightAvailable - leftAvailable;
  }
  const leftStability = Number(left?.stability_score ?? -Infinity);
  const rightStability = Number(right?.stability_score ?? -Infinity);
  if (leftStability !== rightStability) {
    return rightStability - leftStability;
  }
  return String(left?.factor_name || '').localeCompare(String(right?.factor_name || ''));
};

const resolveStatusLabel = (row, available) => {
  if (available) {
    return Number(row?.tier || 0) > 0 ? `Tier ${Number(row?.tier || 0)}` : '已启用';
  }
  return row?.unavailable_reason || '暂不可用';
};

const formatDistributionCount = (topSeries = [], bottomSeries = []) => {
  return Math.max(Array.isArray(topSeries) ? topSeries.length : 0, Array.isArray(bottomSeries) ? bottomSeries.length : 0);
};

export const buildTrendRows = (rows = []) => {
  return [...rows]
    .sort((left, right) => (Number(right.confidence || 0) - Number(left.confidence || 0)))
    .map((row) => {
      const trendState = row.trend_state || 'range';
      const stateMeta = resolveTrendStateMeta(trendState);
      const trendScore = Number(row.trend_score || 0);

      return {
        instId: row.inst_id,
        trendScore: trendScore.toFixed(1),
        trendState,
        trendStateLabel: stateMeta.label,
        trendStateTone: stateMeta.tone,
        scoreSignClass: trendScore >= 0 ? 'price-up' : 'price-down',
        confidencePct: `${(Number(row.confidence || 0) * 100).toFixed(1)}%`,
        currentPriceLabel: formatPrice(Number(row.current_price || 0)),
        topEtaLabel: formatEtaLabel(row.predicted_top_eta_seconds),
        bottomEtaLabel: formatEtaLabel(row.predicted_bottom_eta_seconds),
        topPriceLabel: formatPrice(Number(row.predicted_top_price || 0)),
        bottomPriceLabel: formatPrice(Number(row.predicted_bottom_price || 0)),
        topReturnLabel: formatReturnLabel(row.predicted_top_return),
        bottomReturnLabel: formatReturnLabel(row.predicted_bottom_return),
        topTimeSeries: Array.isArray(row.top_time_distribution) ? row.top_time_distribution : [],
        bottomTimeSeries: Array.isArray(row.bottom_time_distribution) ? row.bottom_time_distribution : [],
        distributionPointCount: formatDistributionCount(row.top_time_distribution, row.bottom_time_distribution),
        qualityLabel: row.data_quality === 'ok' ? '完整' : '部分数据',
        qualityTone: row.data_quality === 'ok' ? 'ok' : 'partial',
      };
    });
};

export const buildTrendFactorRows = (rows = []) => {
  const sortedRows = [...rows].sort(compareFactorRows);
  const maxStability = sortedRows.reduce((maxValue, row) => {
    if (row?.available === false) {
      return maxValue;
    }
    return Math.max(maxValue, Number(row?.stability_score || 0));
  }, 0);
  let nextRank = 1;

  return sortedRows.map((row) => {
      const factorName = row.factor_name || '';
      const available = row.available !== false;
      const categoryKey = row.category || 'uncategorized';
      const categoryMeta = resolveFactorCategoryMeta(categoryKey);
      const stabilityScoreValue = available ? Number(row.stability_score || 0) : null;
      const spearmanValue = available && row.spearman_ic !== null && row.spearman_ic !== undefined
        ? Number(row.spearman_ic)
        : null;
      const rank = available ? nextRank++ : null;
      const strengthValue = available && maxStability > 0
        ? Math.max((stabilityScoreValue / maxStability) * 100, 10)
        : 0;

      return {
        factorName,
        factorLabel: resolveFactorLabel(factorName),
        categoryKey,
        categoryLabel: categoryMeta.label,
        categoryCaption: categoryMeta.caption,
        stabilityScoreValue,
        stabilityScore: available
          ? formatCompactNumber(stabilityScoreValue, FACTOR_CARD_NUMBER_OPTIONS)
          : '--',
        spearmanIcValue: spearmanValue,
        spearmanIc: spearmanValue === null
          ? '--'
          : formatCompactNumber(spearmanValue, FACTOR_CARD_NUMBER_OPTIONS),
        spearmanTone: spearmanValue === null ? 'neutral' : (spearmanValue >= 0 ? 'up' : 'down'),
        clusterLabel: row.redundancy_cluster || 'uncategorized',
        available,
        tier: Number(row.tier || 0),
        unavailableReason: row.unavailable_reason || '',
        statusLabel: resolveStatusLabel(row, available),
        rank,
        rankClass: rank === 1 ? 'is-rank-1' : rank === 2 ? 'is-rank-2' : rank === 3 ? 'is-rank-3' : '',
        strengthWidth: `${strengthValue.toFixed(1)}%`,
        relativeStrengthLabel: available && maxStability > 0 ? `${Math.round(strengthValue)}%` : '--',
      };
    });
};

export const buildTrendFactorGroups = (rows = []) => {
  const groups = new Map();
  for (const row of Array.isArray(rows) ? rows : []) {
    const categoryKey = row?.categoryKey || 'uncategorized';
    const group = groups.get(categoryKey) || {
      key: categoryKey,
      label: row?.categoryLabel || resolveFactorCategoryMeta(categoryKey).label,
      caption: row?.categoryCaption || resolveFactorCategoryMeta(categoryKey).caption,
      items: [],
      availableCount: 0,
    };
    group.items.push(row);
    if (row?.available !== false) {
      group.availableCount += 1;
    }
    groups.set(categoryKey, group);
  }
  return FACTOR_CATEGORY_ORDER
    .map((key) => groups.get(key))
    .filter(Boolean);
};

export const buildTrendFeatureWindowModel = (rows = []) => {
  const normalizedRows = Array.isArray(rows) ? rows : [];
  const latestRow = normalizedRows.at(-1) || null;

  return {
    qualityLabel: latestRow ? (latestRow.data_quality === 'ok' ? '完整' : '部分') : '--',
    timelineSegments: buildTrendTimelineSegments(normalizedRows),
  };
};

export const mergeTrendFeatureBars = (existingRows = [], incomingRows = [], limit = 60) => {
  const mergedByBucket = new Map();
  for (const row of Array.isArray(existingRows) ? existingRows : []) {
    mergedByBucket.set(Number(row?.second_bucket || 0), row);
  }
  for (const row of Array.isArray(incomingRows) ? incomingRows : []) {
    mergedByBucket.set(Number(row?.second_bucket || 0), row);
  }
  return [...mergedByBucket.values()]
    .filter((row) => Number(row?.second_bucket || 0) > 0)
    .sort((left, right) => Number(left.second_bucket || 0) - Number(right.second_bucket || 0))
    .slice(-maxWindowLimit(limit));
};

const maxWindowLimit = (limit) => {
  return Math.max(intLimit(limit), 1);
};

const intLimit = (limit) => {
  return Number.isFinite(Number(limit)) ? Number(limit) : 60;
};

export const buildTrendPanelState = (payload = {}) => {
  const status = String(payload.status || '');
  const whitelist = Array.isArray(payload.whitelist) ? payload.whitelist : [];
  const runtimeError = String(payload.runtime_error || '');

  if (status === 'disabled') {
    return {
      tone: 'warning',
      title: '趋势研究未启用',
      description: '请前往系统设置启用趋势研究，然后保存配置使其立即生效。',
    };
  }

  if (status === 'unconfigured') {
    return {
      tone: 'warning',
      title: '趋势研究白名单为空',
      description: '请前往系统设置填写永续白名单，例如 BTC-USDT-SWAP，然后保存并热更新。',
    };
  }

  if (status === 'collecting') {
    return {
      tone: 'info',
      title: '趋势研究正在采集',
      description: `白名单已加载 ${whitelist.length} 个永续，正在等待首批实时数据和推断结果。`,
    };
  }

  if (status === 'error') {
    return {
      tone: 'danger',
      title: '趋势研究运行错误',
      description: runtimeError || '运行时采集链路发生错误，请查看后端日志。',
    };
  }

  return {
    tone: 'neutral',
    title: '',
    description: '',
  };
};

export { buildTrendModelStatus };
