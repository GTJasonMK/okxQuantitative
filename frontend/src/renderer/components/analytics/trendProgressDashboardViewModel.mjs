import { formatRelativeSeconds, formatUnixSeconds, resolvePipelineStageLabel } from './trendDiagnosticsView.mjs';
const MAX_TIMELINE_ITEMS = 8;
const PIPELINE_STEPS = Object.freeze([
  { key: 'trade', label: 'Trade' },
  { key: 'book', label: 'Book' },
  { key: 'state', label: 'State' },
  { key: 'feature', label: 'Feature' },
  { key: 'inference', label: 'Inference' },
]);
const PIPELINE_WAIT_TARGETS = Object.freeze({
  waiting_trade: 'trade',
  waiting_book: 'book',
  waiting_state: 'state',
  collecting: 'feature',
  feature_ready: 'inference',
  inference_ready: 'inference',
});
const BLOCKING_SUBJECTS = Object.freeze({
  trade: '逐笔成交输入',
  book: '盘口输入',
  state: '状态同步',
  feature: '特征条',
  inference: '推断结果',
});
const NORMAL_FLOW_COPY = Object.freeze({
  waiting_trade: {
    title: '等待 Trade',
    message: '当前还没有收到第一笔逐笔成交，流程会从 Trade 开始推进。',
  },
  waiting_book: {
    title: '等待 Book',
    message: '当前已收到 Trade，正在等待新的 Book 输入。',
  },
  waiting_state: {
    title: '等待 State',
    message: '当前已收到 Trade 和 Book，正在等待状态同步。',
  },
  collecting: {
    title: '正在采集中',
    message: '当前输入链路正常，正在等待形成新的 Feature。',
  },
  feature_ready: {
    title: '已完成 Feature',
    message: '当前没有异常，等待下一次 Inference。',
  },
  inference_ready: {
    title: '已完成 Inference',
    message: '当前没有异常，等待下一轮输入刷新。',
  },
});
const toInt = (value) => {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return 0;
  }
  return Math.max(Math.trunc(number), 0);
};
const normalizeArray = (value) => {
  return Array.isArray(value) ? value : [];
};
const resolveCurrentStepKey = (processInstrument = {}, instrumentHealth = {}) => {
  const pipelineStage = String(instrumentHealth.pipeline_stage || processInstrument.pipelineState || '');
  if (PIPELINE_WAIT_TARGETS[pipelineStage]) {
    return PIPELINE_WAIT_TARGETS[pipelineStage];
  }
  const firstPending = normalizeArray(processInstrument.stages).find((item) => !item?.ready);
  return firstPending?.key || 'inference';
};
const resolveAgeValue = (instrumentHealth = {}, stepKey) => {
  if (stepKey === 'trade') {
    return instrumentHealth.trade_age_seconds;
  }
  if (stepKey === 'book') {
    return instrumentHealth.book_age_seconds;
  }
  if (stepKey === 'state') {
    return instrumentHealth.state_age_seconds;
  }
  return null;
};
const resolveFreshnessLabel = (value) => {
  const age = formatRelativeSeconds(value);
  if (age === '--') {
    return '--';
  }
  return `${age} 前`;
};
const resolveStepTone = (ready, isCurrent, instrumentHealth = {}) => {
  if (ready) {
    return 'ok';
  }
  if (isCurrent && (instrumentHealth.is_error || instrumentHealth.current_error)) {
    return 'danger';
  }
  if (isCurrent && instrumentHealth.is_stale) {
    return 'warning';
  }
  if (isCurrent) {
    return 'accent';
  }
  return 'neutral';
};
const resolveStepStatusLabel = (ready, isCurrent, instrumentHealth = {}) => {
  if (ready) {
    return '已完成';
  }
  if (isCurrent && (instrumentHealth.is_error || instrumentHealth.current_error)) {
    return '异常';
  }
  if (isCurrent && instrumentHealth.is_stale) {
    return '当前阻塞';
  }
  return '未到达';
};

const resolveStepNote = (stepKey, ready, isCurrent, instrumentHealth = {}) => {
  if (stepKey === 'feature') {
    if (ready) {
      return formatUnixSeconds(instrumentHealth.last_feature_at);
    }
    if (isCurrent && instrumentHealth.is_stale) {
      return '长时间未形成新特征';
    }
    return '等待生成';
  }
  if (stepKey === 'inference') {
    if (ready) {
      return formatUnixSeconds(instrumentHealth.last_inference_at);
    }
    if (isCurrent && instrumentHealth.is_stale) {
      return '长时间未形成新推断';
    }
    return '等待生成';
  }
  const age = formatRelativeSeconds(resolveAgeValue(instrumentHealth, stepKey));
  if (age === '--') {
    return ready ? '已收到输入' : '等待输入';
  }
  return ready ? `${age} 前更新` : `${age} 未更新`;
};

const resolveBlockingReason = (processInstrument = {}, instrumentHealth = {}, currentStepKey) => {
  if (instrumentHealth.current_error) {
    return instrumentHealth.current_error;
  }
  if (instrumentHealth.is_error) {
    return '流程已进入异常状态，请查看最近错误时间和事件回放。';
  }
  if (instrumentHealth.is_stale) {
    const age = formatRelativeSeconds(resolveAgeValue(instrumentHealth, currentStepKey));
    if (age !== '--' && BLOCKING_SUBJECTS[currentStepKey]) {
      return `${age} 未收到新的${BLOCKING_SUBJECTS[currentStepKey]}。`;
    }
    return '当前步骤长时间没有新的有效输入或输出。';
  }
  const pipelineStage = String(instrumentHealth.pipeline_stage || processInstrument.pipelineState || '');
  return NORMAL_FLOW_COPY[pipelineStage]?.message || '当前没有异常，流程仍在推进。';
};

const buildOverviewItems = (processSummary = {}, globalHealth = {}) => {
  const whitelistCount = toInt(processSummary.whitelist_count || globalHealth.whitelist_count);
  const inferenceReadyCount = toInt(processSummary.inference_ready_count);
  const staleCount = toInt(globalHealth.stale_count);
  const errorCount = toInt(globalHealth.error_count);
  const processingCount = Math.max(whitelistCount - inferenceReadyCount - staleCount - errorCount, 0);

  return [
    { label: '白名单', value: String(whitelistCount) },
    { label: '推断完成', value: String(inferenceReadyCount) },
    { label: '处理中', value: String(processingCount) },
    { label: '停滞', value: String(staleCount) },
    { label: '异常', value: String(errorCount) },
  ];
};

const buildConclusion = (processInstrument = {}, instrumentHealth = {}, loading = false) => {
  const instId = processInstrument.instId || instrumentHealth.inst_id || '当前合约';
  const pipelineStage = String(instrumentHealth.pipeline_stage || processInstrument.pipelineState || '');
  const currentStepKey = resolveCurrentStepKey(processInstrument, instrumentHealth);
  const currentStepLabel = PIPELINE_STEPS.find((item) => item.key === currentStepKey)?.label || '流程';
  const stageLabel = resolvePipelineStageLabel(pipelineStage);
  const blockingReason = resolveBlockingReason(processInstrument, instrumentHealth, currentStepKey);
  const snapshotTime = formatUnixSeconds(instrumentHealth.last_event_at);

  if (loading) {
    return {
      title: `${instId} 正在同步运行进度`,
      message: '正在拉取最新快照并等待实时事件...',
      metaItems: [
        { label: '当前阶段', value: stageLabel || '--' },
        { label: '最近事件', value: snapshotTime },
      ],
    };
  }
  if (instrumentHealth.current_error || instrumentHealth.is_error) {
    return {
      title: `${instId} 当前异常`,
      message: `流程中断，原因：${blockingReason}`,
      metaItems: [
        { label: '当前阶段', value: stageLabel || '--' },
        { label: '最近事件', value: snapshotTime },
      ],
    };
  }
  if (instrumentHealth.is_stale) {
    return {
      title: `${instId} 当前停在 ${currentStepLabel}`,
      message: blockingReason,
      metaItems: [
        { label: '当前阶段', value: stageLabel || '--' },
        { label: '最近事件', value: snapshotTime },
      ],
    };
  }
  const normalCopy = NORMAL_FLOW_COPY[pipelineStage] || NORMAL_FLOW_COPY.collecting;
  return {
    title: `${instId} ${normalCopy.title}`,
    message: normalCopy.message,
    metaItems: [
      { label: '当前阶段', value: stageLabel || '--' },
      { label: '最近事件', value: snapshotTime },
    ],
  };
};

const buildPipelineSteps = (processInstrument = {}, instrumentHealth = {}) => {
  const stageMap = new Map(normalizeArray(processInstrument.stages).map((item) => [item.key, item]));
  const currentStepKey = resolveCurrentStepKey(processInstrument, instrumentHealth);

  return PIPELINE_STEPS.map((item) => {
    const stage = stageMap.get(item.key) || {};
    const ready = !!stage.ready;
    const isCurrent = currentStepKey === item.key && !ready;
    return {
      key: item.key,
      label: item.label,
      statusLabel: resolveStepStatusLabel(ready, isCurrent, instrumentHealth),
      tone: resolveStepTone(ready, isCurrent, instrumentHealth),
      note: resolveStepNote(item.key, ready, isCurrent, instrumentHealth),
      isCurrent,
    };
  });
};

const buildEvidenceCards = (processInstrument = {}, diagnosticsState = {}) => {
  const instrumentHealth = diagnosticsState.instrumentHealth || {};
  const currentStepKey = resolveCurrentStepKey(processInstrument, instrumentHealth);
  const leadReason = instrumentHealth.is_error || instrumentHealth.current_error || instrumentHealth.is_stale
    ? resolveBlockingReason(processInstrument, instrumentHealth, currentStepKey)
    : '当前没有异常，流程仍在推进。';
  return [
    {
      label: '当前阻塞原因',
      items: [
        {
          label: '系统判断',
          value: leadReason,
        },
      ],
    },
    {
      label: '最近有效输入',
      items: [
        { label: '最近 Trade', value: resolveFreshnessLabel(instrumentHealth.trade_age_seconds) },
        { label: '最近 Book', value: resolveFreshnessLabel(instrumentHealth.book_age_seconds) },
        { label: '最近 State', value: resolveFreshnessLabel(instrumentHealth.state_age_seconds) },
      ],
    },
    {
      label: '最近有效产出',
      items: [
        { label: '最近 Feature', value: formatUnixSeconds(instrumentHealth.last_feature_at) },
        { label: '最近 Inference', value: formatUnixSeconds(instrumentHealth.last_inference_at) },
      ],
    },
  ];
};

export const buildTrendProgressDashboardModel = ({
  processSummary = {},
  processInstrument = {},
  diagnosticsState = {},
  loading = false,
} = {}) => {
  return {
    overviewItems: buildOverviewItems(processSummary, diagnosticsState.globalHealth || {}),
    conclusion: buildConclusion(processInstrument, diagnosticsState.instrumentHealth || {}, loading),
    pipelineSteps: buildPipelineSteps(processInstrument, diagnosticsState.instrumentHealth || {}),
    evidenceCards: buildEvidenceCards(processInstrument, diagnosticsState),
    timelineItems: normalizeArray(diagnosticsState.timeline).slice(-MAX_TIMELINE_ITEMS),
  };
};
