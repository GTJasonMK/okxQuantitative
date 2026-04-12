import { formatCompactNumber, formatDateTime, formatPercentValue } from '../../utils/formatting.js';

const METRIC_CARD_NUMBER_OPTIONS = Object.freeze({
  digits: 3,
  maxChars: 8,
  scientificDigits: 2,
});

const resolveModelPayload = (payload = {}) => {
  if (payload?.model_status && typeof payload.model_status === 'object') {
    return payload.model_status;
  }
  if (payload?.model && typeof payload.model === 'object') {
    return payload.model;
  }
  if (payload?.summary && typeof payload.summary === 'object') {
    return {
      ready: payload.summary.model_ready,
      trained_at: payload.summary.trained_at,
      horizon_minutes: payload.summary.horizon_minutes,
      selected_feature_count: payload.summary.selected_feature_count,
    };
  }
  return {};
};

const buildMetricCard = (label, value, suffix = '') => {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return { label, value: '--' };
  }
  return {
    label,
    value: `${formatCompactNumber(number, METRIC_CARD_NUMBER_OPTIONS)}${suffix}`,
  };
};

const buildHitRateCard = (label, value) => {
  const number = Number(value);
  return {
    label,
    value: Number.isFinite(number) ? formatPercentValue(number * 100, 1) : '--',
  };
};

const buildValidationCards = (metrics = {}) => {
  return [
    buildMetricCard('顶部时间 MAE', metrics?.top_time_mae_minutes, ' 分钟'),
    buildMetricCard('底部时间 MAE', metrics?.bottom_time_mae_minutes, ' 分钟'),
    buildMetricCard('顶部价格 MAE', metrics?.top_price_mae_bps, ' bps'),
    buildMetricCard('底部价格 MAE', metrics?.bottom_price_mae_bps, ' bps'),
    buildHitRateCard('联合命中', metrics?.joint_hit_rate),
  ];
};

export const buildTrendModelStatus = (payload = {}) => {
  const status = String(payload?.status || '');
  const model = resolveModelPayload(payload);
  if (status === 'disabled') {
    return {
      ready: false,
      title: '功能未启用',
      tone: 'neutral',
      description: '启用趋势研究后，系统才会开始训练和使用模型。',
      probabilitySourceLabel: '--',
      horizonLabel: '--',
      trainedAtLabel: '--',
      selectedFeatureCountLabel: '--',
      validationCards: buildValidationCards(),
    };
  }
  if (status === 'unconfigured') {
    return {
      ready: false,
      title: '等待白名单',
      tone: 'neutral',
      description: '先配置永续白名单，系统才会开始采集和训练模型。',
      probabilitySourceLabel: '--',
      horizonLabel: '--',
      trainedAtLabel: '--',
      selectedFeatureCountLabel: '--',
      validationCards: buildValidationCards(),
    };
  }
  const ready = Boolean(model?.ready);
  return {
    ready,
    title: ready ? '模型已就绪' : '模型未就绪',
    tone: ready ? 'ok' : 'warning',
    description: ready
      ? '当前模型直接预测未来周期内的顶部与底部时间、价格和空间。'
      : '模型尚未加载或训练，当前不会输出直接极值预测。',
    probabilitySourceLabel: ready ? '直接极值模型' : '未加载',
    horizonLabel: Number(model?.horizon_minutes) > 0 ? `${Number(model.horizon_minutes)} 分钟` : '--',
    trainedAtLabel: ready && model?.trained_at ? formatDateTime(model.trained_at) : '--',
    selectedFeatureCountLabel: Number(model?.selected_feature_count) > 0
      ? formatCompactNumber(model.selected_feature_count, {
        digits: 0,
        maxChars: 6,
        scientificDigits: 2,
      })
      : '--',
    validationCards: buildValidationCards(model?.metrics),
  };
};
