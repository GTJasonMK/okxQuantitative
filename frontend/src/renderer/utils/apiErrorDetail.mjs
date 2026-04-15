export function formatApiErrorDetail(error, fallbackMessage) {
  const detail = error?.response?.data?.detail;
  if (typeof detail === 'string' && detail.trim()) {
    return detail;
  }
  if (detail && typeof detail === 'object') {
    return buildObjectDetailMessage(detail, fallbackMessage);
  }
  return error?.message || fallbackMessage;
}

function buildObjectDetailMessage(detail, fallbackMessage) {
  const message = String(detail.message || detail.detail || fallbackMessage).trim();
  const blockingIds = resolveBlockingIds(detail);
  if (blockingIds.length === 0) {
    return message;
  }
  return `${message}：${blockingIds.join('、')}`;
}

function resolveBlockingIds(detail) {
  if (Array.isArray(detail.blocking_dataset_ids)) {
    return detail.blocking_dataset_ids.map(item => String(item));
  }
  if (Array.isArray(detail.blocking_training_run_ids)) {
    return detail.blocking_training_run_ids.map(item => String(item));
  }
  return [];
}
