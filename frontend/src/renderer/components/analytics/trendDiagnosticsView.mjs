import { formatDateTime } from '../../utils/formatting';

const PIPELINE_STAGE_LABELS = Object.freeze({
  waiting_trade: '等待 Trade',
  waiting_book: '等待 Book',
  waiting_state: '等待状态同步',
  collecting: '采集中',
  feature_ready: '特征已生成',
  inference_ready: '推断已生成',
});

const TIMELINE_TONES = Object.freeze({
  trade: 'info',
  book: 'info',
  state: 'neutral',
  feature: 'accent',
  inference: 'ok',
  error: 'danger',
  recovery: 'ok',
});

export const resolveInstId = (item = {}) => {
  return String(item.inst_id || item.instId || '');
};

export const resolvePipelineStageLabel = (stage) => {
  return PIPELINE_STAGE_LABELS[String(stage || '')] || '等待 Trade';
};

export const resolveHealthTone = (health = {}) => {
  if (health.is_error) {
    return 'danger';
  }
  if (health.is_stale) {
    return 'warning';
  }
  return 'ok';
};

export const resolveHealthLabel = (health = {}) => {
  if (health.is_error) {
    return '异常';
  }
  if (health.is_stale) {
    return '停滞';
  }
  return '活跃';
};

export const resolveTimelineTone = (kind) => {
  return TIMELINE_TONES[String(kind || '')] || 'neutral';
};

export const formatRelativeSeconds = (value) => {
  const seconds = Number(value);
  if (!Number.isFinite(seconds)) {
    return '--';
  }
  return `${seconds.toFixed(1)}s`;
};

export const formatUnixSeconds = (value) => {
  const ts = Number(value);
  if (!Number.isFinite(ts) || ts <= 0) {
    return '--';
  }
  return formatDateTime(ts * 1000);
};

export const formatBucketLabel = (value) => {
  const bucket = Number(value);
  if (!Number.isFinite(bucket)) {
    return '--';
  }
  return `${bucket}`;
};

export const resolveTimelineCaption = (item = {}) => {
  if (item.message) {
    return item.message;
  }
  if (item.second_bucket !== null && item.second_bucket !== undefined) {
    return `秒桶 ${formatBucketLabel(item.second_bucket)}`;
  }
  return '无附加信息';
};
