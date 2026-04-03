import {
  computed,
  nextTick,
  onMounted,
  onUnmounted,
  reactive,
  ref,
  shallowRef,
  watch,
} from 'vue';

import { api } from '../../services/api';
import { useGuardianSyncPlans, sortGuardianTimeframes } from '../useGuardianSyncPlans';
import { renderAssistantMessageHtml } from './assistantMarkdown';
import {
  formatDataHealthBadgeText,
  formatDataHealthSummaryText,
  getDataHealthScore,
  resolveDataHealthStatus,
} from '../../utils/dataHealth';

const buildMessageId = () => `assistant-msg-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

const normalizeAssistantText = (value) => String(value || '').replace(/\r\n/g, '\n').trim();

const buildDefaultAssistantMessage = (activeSymbol) => ({
  id: 'assistant-default',
  role: 'assistant',
  content: activeSymbol
    ? `已切换到 ${activeSymbol} 的 AI 分析模式。你可以直接让我先查行情、再做判断，或者要求我编写分析代码验证思路。`
    : '先选择一个关注币种，再让我基于当前行情做工具化分析。',
  htmlContent: activeSymbol
    ? renderAssistantMessageHtml(
        `已切换到 ${activeSymbol} 的 AI 分析模式。你可以直接让我先查行情、再做判断，或者要求我编写分析代码验证思路。`,
        'assistant',
      )
    : renderAssistantMessageHtml('先选择一个关注币种，再让我基于当前行情做工具化分析。', 'assistant'),
  pending: false,
  temporary: false,
});

const createAssistantState = () => ({
  sessionId: '',
  detail: null,
  sessionList: [],
  temporaryMessages: [],
  listLoaded: false,
  listLoading: false,
  detailLoading: false,
});

const normalizeSessionDetail = (detail) => ({
  session: detail?.session || null,
  messages: Array.isArray(detail?.messages) ? detail.messages : [],
  steps: Array.isArray(detail?.steps) ? detail.steps : [],
  order_drafts: Array.isArray(detail?.order_drafts) ? detail.order_drafts : [],
  level_snapshots: Array.isArray(detail?.level_snapshots) ? detail.level_snapshots : [],
});

const formatAssistantTimestamp = (value) => {
  if (!value) {
    return '';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '';
  }
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
};

const summarizePreviewScalar = (value) => {
  if (value == null || value === '') {
    return '--';
  }
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) {
      return '--';
    }
    return Math.abs(value) >= 1000 ? value.toFixed(0) : value.toFixed(4).replace(/\.?0+$/, '');
  }
  if (typeof value === 'boolean') {
    return value ? '是' : '否';
  }
  if (typeof value === 'string') {
    const normalized = normalizeAssistantText(value);
    return normalized.length > 72 ? `${normalized.slice(0, 72)}...` : normalized;
  }
  if (Array.isArray(value)) {
    return `数组(${value.length})`;
  }
  if (typeof value === 'object') {
    return `对象(${Object.keys(value).length})`;
  }
  return String(value);
};

const summarizePreviewObject = (value) => {
  if (!value || typeof value !== 'object') {
    return summarizePreviewScalar(value);
  }

  const entries = Object.entries(value)
    .filter(([key, item]) => (
      key !== 'rows'
      && key !== 'candles'
      && key !== 'messages'
      && key !== 'steps'
      && item !== undefined
    ))
    .slice(0, 4);

  if (entries.length === 0) {
    return `对象(${Object.keys(value).length})`;
  }

  return entries
    .map(([key, item]) => `${key}: ${summarizePreviewScalar(item)}`)
    .join(' / ');
};

const upsertAssistantRecords = (currentRecords, nextRecord, idKey) => {
  const recordId = normalizeAssistantText(nextRecord?.[idKey]);
  if (!recordId) {
    return Array.isArray(currentRecords) ? currentRecords : [];
  }
  const current = Array.isArray(currentRecords) ? currentRecords : [];
  const deduped = current.filter((item) => normalizeAssistantText(item?.[idKey]) !== recordId);
  return [nextRecord, ...deduped];
};

const buildStepPreviewText = (step) => {
  if (step?.status === 'running') {
    const toolName = normalizeAssistantText(step?.tool_name || step?.title);
    return toolName ? `${toolName} 执行中...` : '工具执行中...';
  }
  if (normalizeAssistantText(step?.error_text)) {
    return normalizeAssistantText(step.error_text);
  }
  const output = step?.output;
  if (!output || typeof output !== 'object') {
    return '已完成本步调用。';
  }
  if (output.summary && typeof output.summary === 'string') {
    return normalizeAssistantText(output.summary);
  }
  return summarizePreviewObject(output);
};

const parseAgentResponsePayload = async (response) => {
  const rawText = await response.text();
  const normalized = normalizeAssistantText(rawText);
  if (!normalized) {
    return {};
  }
  try {
    return JSON.parse(normalized);
  } catch (error) {
    return {
      detail: normalized,
    };
  }
};

const consumeAssistantAgentStream = async (
  response,
  {
    onMeta,
    onDelta,
    onDone,
    onError,
  } = {},
) => {
  const reader = response.body?.getReader?.();
  if (!reader) {
    throw new Error('当前环境不支持流式读取');
  }

  const decoder = new TextDecoder('utf-8');
  let buffer = '';

  const dispatchEvent = async (payload) => {
    if (!payload || typeof payload !== 'object') {
      return;
    }
    if (payload.type === 'meta' && typeof onMeta === 'function') {
      await onMeta(payload);
      return;
    }
    if (payload.type === 'delta' && typeof onDelta === 'function') {
      await onDelta(String(payload.delta || ''));
      return;
    }
    if (payload.type === 'done' && typeof onDone === 'function') {
      await onDone(payload);
      return;
    }
    if (payload.type === 'error' && typeof onError === 'function') {
      await onError(payload);
    }
  };

  const flushBuffer = async (force = false) => {
    const chunks = force
      ? [buffer]
      : buffer.split(/\r?\n\r?\n/);
    if (!force) {
      buffer = chunks.pop() || '';
    } else {
      buffer = '';
    }

    for (const chunk of chunks) {
      const normalizedChunk = String(chunk || '').trim();
      if (!normalizedChunk) {
        continue;
      }
      const dataLines = normalizedChunk
        .split(/\r?\n/)
        .filter((line) => line.startsWith('data:'))
        .map((line) => line.slice(5).trim());
      if (dataLines.length === 0) {
        continue;
      }
      const eventText = dataLines.join('\n');
      if (!eventText) {
        continue;
      }
      let payload = null;
      try {
        payload = JSON.parse(eventText);
      } catch (error) {
        continue;
      }
      await dispatchEvent(payload);
    }
  };

  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    await flushBuffer(done);
    if (done) {
      break;
    }
  }
};

const normalizeAssistantTimelineTimestamp = (value) => {
  if (!value) {
    return 0;
  }
  const timestamp = new Date(value).getTime();
  return Number.isFinite(timestamp) ? timestamp : 0;
};

const buildAssistantStepFingerprint = (step) => {
  const stepId = normalizeAssistantText(step?.id);
  if (stepId) {
    return `id:${stepId}`;
  }
  const toolName = normalizeAssistantText(step?.tool_name || step?.title || step?.step_type);
  const createdAt = normalizeAssistantText(step?.created_at);
  return [
    'step',
    step?.step_index ?? '',
    toolName,
    createdAt,
  ].join(':');
};

const compareAssistantTimelineEntries = (left, right) => {
  const timestampDiff = (left.sortTimestamp || 0) - (right.sortTimestamp || 0);
  if (timestampDiff !== 0) {
    return timestampDiff;
  }
  const rankDiff = (left.sortRank || 0) - (right.sortRank || 0);
  if (rankDiff !== 0) {
    return rankDiff;
  }
  return String(left.id || '').localeCompare(String(right.id || ''));
};

export const useMarketViewAssistant = ({
  marketWS,
  activeSymbol,
  marketInstType,
  currentTimeframe,
  displayRangeDays,
  indicators,
  activeTicker,
  activeOrderBook,
  activeSyncJobs,
  candlesData,
  activeSymbolHealthRow,
  activeSymbolMarketHealth,
  activeSymbolHealthStatus,
  activeSymbolHealthSummaryText,
  appendChartAnnotation,
  updateChart,
  openSymbolTab,
  normalizeMonitorSymbol,
  formatPrice,
  formatChange,
}) => {
  const assistantAnchorRef = ref(null);
  const assistantPanelRef = ref(null);
  const assistantMessagesRef = ref(null);
  const assistantInputRef = ref(null);
  const assistantFloatingStyle = shallowRef({});
  const assistantExpanded = ref(false);
  const assistantBusy = ref(false);
  const assistantInput = ref('');
  const assistantError = ref('');
  const assistantProgressVisible = ref(false);
  const assistantStatusLoaded = ref(false);
  const assistantStatus = reactive({
    enabled: false,
    configured: false,
    provider: '',
    model: '',
  });
  const assistantTools = shallowRef([]);
  const assistantToolsLoaded = ref(false);
  const assistantPanelTab = ref('chat');
  const assistantStateStore = reactive({});
  const assistantAbortController = shallowRef(null);
  const assistantCurrentRunStepOffset = ref(0);
  const assistantPatrolStatusLoaded = ref(false);
  const assistantPatrolBusy = ref(false);
  const assistantPatrolConfig = reactive({
    enabled: false,
    intervalSeconds: 300,
    scanLimit: 24,
    candidateLimit: 3,
    instType: 'SWAP',
    timeframes: ['1H', '4H'],
    candlesLimit: 240,
    recentTradeLimit: 40,
    orderbookDepth: 30,
    mode: 'simulated',
    minPriorityScore: 55,
    notificationCooldownSeconds: 900,
  });
  const assistantPatrolStatus = reactive({
    running: false,
    currentPhase: 'idle',
    lastRunStartedAt: '',
    lastRunFinishedAt: '',
    lastRunSummary: {},
    lastError: '',
  });
  const assistantPatrolEvents = shallowRef([]);
  const assistantPatrolRuns = shallowRef([]);
  const assistantPatrolRunsLoaded = ref(false);
  const assistantPatrolRunsLoading = ref(false);
  const assistantPatrolPendingSyncKeys = ref([]);
  const assistantLevelSnapshots = shallowRef([]);
  const assistantLevelSnapshotsLoaded = ref(false);
  const assistantLevelSnapshotsLoading = ref(false);
  const assistantOrderDrafts = shallowRef([]);
  const assistantOrderDraftsLoaded = ref(false);
  const assistantOrderDraftsLoading = ref(false);
  const assistantSnapshotBusy = ref(false);
  const assistantPatrolRunsQueryKey = ref('');
  const assistantLevelSnapshotsQueryKey = ref('');
  const assistantOrderDraftsQueryKey = ref('');
  let assistantPositionRaf = 0;
  let assistantViewportListenersBound = false;
  let assistantProgressPollTimer = 0;
  let assistantPatrolWsHandler = null;
  const {
    planMap: assistantGuardianPlanMap,
    enabledTimeframes: assistantGuardianEnabledTimeframes,
    loadPlans: loadAssistantGuardianPlans,
  } = useGuardianSyncPlans();

  const assistantLayoutPreset = computed(() => ({
    width: 520,
    minWidth: 380,
    preferredHeight: 540,
    minHeight: 400,
    maxHeight: 680,
  }));

  const assistantSessionKey = computed(() => {
    const normalizedSymbol = normalizeMonitorSymbol(activeSymbol.value);
    return normalizedSymbol
      ? `${normalizedSymbol}:${marketInstType.value}`
      : `global:${marketInstType.value}`;
  });

  const ensureAssistantState = (sessionKey = assistantSessionKey.value) => {
    if (!assistantStateStore[sessionKey]) {
      assistantStateStore[sessionKey] = createAssistantState();
    }
    return assistantStateStore[sessionKey];
  };

  const getActiveAssistantState = () => ensureAssistantState(assistantSessionKey.value);

  const assistantPatrolEventList = computed(() => (
    Array.isArray(assistantPatrolEvents.value) ? assistantPatrolEvents.value : []
  ));

  const assistantPatrolRunList = computed(() => (
    Array.isArray(assistantPatrolRuns.value) ? assistantPatrolRuns.value : []
  ));

  const assistantLevelSnapshotList = computed(() => (
    Array.isArray(assistantLevelSnapshots.value) ? assistantLevelSnapshots.value : []
  ));

  const assistantOrderDraftList = computed(() => (
    Array.isArray(assistantOrderDrafts.value) ? assistantOrderDrafts.value : []
  ));

  const assistantPatrolRunsRequestKey = computed(() => (
    [
      String(assistantPatrolConfig.instType || marketInstType.value || '').trim().toUpperCase(),
      normalizeAssistantText(assistantPatrolConfig.mode || 'simulated') || 'simulated',
    ].join(':')
  ));

  const assistantLevelSnapshotsRequestKey = computed(() => (
    normalizeMonitorSymbol(activeSymbol.value)
  ));

  const assistantOrderDraftsRequestKey = computed(() => (
    normalizeMonitorSymbol(activeSymbol.value)
  ));

  const assistantPatrolSummary = computed(() => {
    if (assistantPatrolBusy.value) {
      return '正在扫描关注币种...';
    }
    if (assistantPatrolStatus.lastError) {
      return assistantPatrolStatus.lastError;
    }
    const summary = assistantPatrolStatus.lastRunSummary || {};
    const emittedCount = Number(summary.emitted_candidate_count || 0);
    const candidateCount = Number(summary.filtered_candidate_count || summary.candidate_count || 0);
    if (emittedCount > 0) {
      return `最近一轮推送了 ${emittedCount} 个新机会。`;
    }
    if (candidateCount > 0) {
      return `最近一轮筛出了 ${candidateCount} 个候选机会。`;
    }
    if (assistantPatrolStatus.lastRunFinishedAt) {
      return '最近一轮未发现满足条件的候选机会。';
    }
    return '后台巡检关注币种，推送值得跟踪的候选机会。';
  });

  const assistantPatrolMeta = computed(() => {
    const intervalMinutes = Math.max(1, Math.round((Number(assistantPatrolConfig.intervalSeconds) || 300) / 60));
    return assistantPatrolConfig.enabled ? `每 ${intervalMinutes} 分钟一轮` : '未开启后台巡检';
  });

  const assistantActiveSyncJobs = computed(() => (
    Array.isArray(activeSyncJobs?.value) ? activeSyncJobs.value : []
  ));

  const normalizePatrolCandidateInstType = (candidate) => {
    const raw = String(candidate?.inst_type || assistantPatrolConfig.instType || marketInstType.value || 'SWAP')
      .trim()
      .toUpperCase();
    return raw === 'SPOT' ? 'SPOT' : 'SWAP';
  };

  const getPatrolCandidateInstId = (candidate) => (
    normalizeAssistantText(candidate?.inst_id || candidate?.symbol)
  );

  const getPatrolCandidateHealthRow = (candidate) => (
    candidate?.data_health && typeof candidate.data_health === 'object'
      ? candidate.data_health
      : null
  );

  const getPatrolCandidateHealthMarket = (candidate) => {
    const instType = normalizePatrolCandidateInstType(candidate);
    const healthRow = getPatrolCandidateHealthRow(candidate);
    return healthRow?.markets?.[instType] || null;
  };

  const getPatrolCandidatePresentTimeframes = (candidate) => (
    sortGuardianTimeframes(
      (getPatrolCandidateHealthMarket(candidate)?.timeframes || []).map((item) => item?.timeframe),
    )
  );

  const getPatrolCandidateMissingTimeframes = (candidate) => {
    const present = new Set(getPatrolCandidatePresentTimeframes(candidate));
    return assistantGuardianEnabledTimeframes.value.filter((timeframe) => !present.has(timeframe));
  };

  const buildPatrolCandidateSyncKey = (candidate, timeframe) => (
    [
      normalizeMonitorSymbol(candidate?.symbol || candidate?.inst_id),
      normalizePatrolCandidateInstType(candidate),
      String(timeframe || '').trim(),
    ].join(':')
  );

  const isPatrolCandidateSyncPending = (candidate, timeframe) => (
    assistantPatrolPendingSyncKeys.value.includes(buildPatrolCandidateSyncKey(candidate, timeframe))
  );

  const findPatrolCandidateSyncJob = (candidate, timeframe) => {
    const instId = getPatrolCandidateInstId(candidate);
    const instType = normalizePatrolCandidateInstType(candidate);
    return assistantActiveSyncJobs.value.find((job) => (
      normalizeAssistantText(job?.inst_id) === instId
      && String(job?.inst_type || '').trim().toUpperCase() === instType
      && String(job?.timeframe || '').trim() === String(timeframe || '').trim()
    )) || null;
  };

  const formatPatrolSyncJobStatus = (job) => {
    const status = String(job?.status || '').trim().toLowerCase();
    if (status === 'running') {
      return `${Number(job?.progress || 0)}%`;
    }
    if (status === 'queued') {
      return '排队中';
    }
    if (status === 'completed') {
      return '已完成';
    }
    if (status === 'failed') {
      return '失败';
    }
    return '处理中';
  };

  const buildPatrolCandidateRepairPlans = (candidate) => (
    getPatrolCandidateMissingTimeframes(candidate).map((timeframe) => {
      const job = findPatrolCandidateSyncJob(candidate, timeframe);
      const pending = isPatrolCandidateSyncPending(candidate, timeframe);
      return {
        timeframe,
        job,
        pending,
        disabled: Boolean(job || pending),
        statusText: job
          ? formatPatrolSyncJobStatus(job)
          : (pending ? '创建中' : ''),
      };
    })
  );

  const decoratePatrolCandidate = (candidate) => {
    if (!candidate || typeof candidate !== 'object') {
      return candidate;
    }
    const healthRow = getPatrolCandidateHealthRow(candidate);
    const instType = normalizePatrolCandidateInstType(candidate);
    const marketMissingTimeframes = getPatrolCandidateMissingTimeframes(candidate);
    return {
      ...candidate,
      inst_type: instType,
      data_health: healthRow,
      healthStatus: resolveDataHealthStatus(healthRow, instType),
      healthScore: getDataHealthScore(healthRow),
      healthBadgeText: formatDataHealthBadgeText(healthRow, instType),
      healthSummaryText: formatDataHealthSummaryText(healthRow, instType),
      marketMissingTimeframes,
      repairPlans: buildPatrolCandidateRepairPlans(candidate),
      repairHintText: marketMissingTimeframes.length > 0 ? `缺 ${marketMissingTimeframes.join(' / ')}` : '关键周期齐',
    };
  };

  const syncAssistantPatrolCandidateTimeframe = async (candidate, timeframe) => {
    const instId = getPatrolCandidateInstId(candidate);
    const instType = normalizePatrolCandidateInstType(candidate);
    const normalizedTimeframe = String(timeframe || '').trim();
    if (!instId || !normalizedTimeframe) {
      assistantError.value = '巡检候选缺少有效同步参数';
      return;
    }
    if (findPatrolCandidateSyncJob(candidate, normalizedTimeframe)) {
      assistantError.value = '';
      return;
    }

    const pendingKey = buildPatrolCandidateSyncKey(candidate, normalizedTimeframe);
    if (assistantPatrolPendingSyncKeys.value.includes(pendingKey)) {
      return;
    }

    assistantPatrolPendingSyncKeys.value = [...assistantPatrolPendingSyncKeys.value, pendingKey];
    assistantError.value = '';
    try {
      const plan = assistantGuardianPlanMap.value.get(normalizedTimeframe);
      await api.startSyncJob(instId, {
        instType,
        timeframe: normalizedTimeframe,
        days: Number(plan?.bootstrap_days) || (normalizedTimeframe === '1m' ? 7 : 30),
        mode: plan?.archive_mode === 'full' ? 'full' : 'window',
      });
    } catch (error) {
      assistantError.value = error?.response?.data?.detail || error?.message || '发起数据补齐失败';
    } finally {
      window.setTimeout(() => {
        assistantPatrolPendingSyncKeys.value = assistantPatrolPendingSyncKeys.value
          .filter((item) => item !== pendingKey);
      }, 3500);
    }
  };

  const assistantVisiblePatrolEvents = computed(() => (
    assistantPatrolEventList.value.map((event) => ({
      ...event,
      candidates: Array.isArray(event?.candidates)
        ? event.candidates.map((candidate) => decoratePatrolCandidate(candidate))
        : [],
    }))
  ));

  const assistantVisiblePatrolRuns = computed(() => (
    assistantPatrolRunList.value.map((run) => ({
      ...run,
      candidates: Array.isArray(run?.candidates)
        ? run.candidates.map((candidate) => decoratePatrolCandidate(candidate))
        : [],
      candidateCount: Array.isArray(run?.candidates) ? run.candidates.length : 0,
      triggerLabel: run?.trigger === 'manual' ? '手动巡检' : '自动巡检',
      displayTime: formatAssistantTimestamp(run?.created_at),
      summaryText: normalizeAssistantText(run?.summary?.message)
        || (Array.isArray(run?.candidates) && run.candidates.length > 0
          ? `本轮记录了 ${run.candidates.length} 个候选机会。`
          : '本轮未记录到候选机会。'),
    }))
  ));

  const assistantVisibleLevelSnapshots = computed(() => (
    assistantLevelSnapshotList.value
      .filter((snapshot) => {
        const snapshotInstType = normalizeAssistantText(snapshot?.inst_type).toUpperCase();
        return !marketInstType.value || !snapshotInstType || snapshotInstType === marketInstType.value;
      })
      .map((snapshot) => ({
        ...snapshot,
        supportCount: Array.isArray(snapshot?.supports) ? snapshot.supports.length : 0,
        resistanceCount: Array.isArray(snapshot?.resistances) ? snapshot.resistances.length : 0,
        timeframeLabel: Array.isArray(snapshot?.timeframes) && snapshot.timeframes.length > 0
          ? snapshot.timeframes.join(' / ')
          : '--',
        displayTime: formatAssistantTimestamp(snapshot?.created_at),
        nearestSupport: snapshot?.summary?.nearest_support,
        nearestResistance: snapshot?.summary?.nearest_resistance,
        summaryText: normalizeAssistantText(snapshot?.summary?.message)
          || `支撑 ${Array.isArray(snapshot?.supports) ? snapshot.supports.length : 0} / 压力 ${Array.isArray(snapshot?.resistances) ? snapshot.resistances.length : 0}`,
      }))
  ));

  const assistantVisibleOrderDrafts = computed(() => (
    assistantOrderDraftList.value
      .filter((draft) => {
        const draftInstType = normalizeAssistantText(draft?.inst_type).toUpperCase();
        return !marketInstType.value || !draftInstType || draftInstType === marketInstType.value;
      })
      .map((draft) => ({
        ...draft,
        displayTime: formatAssistantTimestamp(draft?.updated_at || draft?.created_at),
        sideLabel: draft?.side === 'buy' ? '买入' : (draft?.side === 'sell' ? '卖出' : '未定向'),
        modeLabel: draft?.mode === 'live' ? '实盘' : '模拟',
        statusLabel: draft?.status === 'confirmed'
          ? '已确认'
          : (draft?.status === 'cancelled' ? '已取消' : '待确认'),
        statusClass: draft?.status === 'confirmed'
          ? 'is-completed'
          : (draft?.status === 'cancelled' ? 'is-failed' : ''),
        summaryText: normalizeAssistantText(draft?.summary)
          || `${draft?.inst_id || ''} ${draft?.side === 'buy' ? '买入' : (draft?.side === 'sell' ? '卖出' : '交易')}草案`,
        priceLabel: normalizeAssistantText(draft?.price) || '市价',
        stopLossLabel: normalizeAssistantText(draft?.stop_loss_price) || '--',
        takeProfitCount: Array.isArray(draft?.take_profit_prices) ? draft.take_profit_prices.length : 0,
        annotationCount: Array.isArray(draft?.annotations) ? draft.annotations.length : 0,
      }))
  ));

  const selectedIndicatorLabels = computed(() => (
    Object.entries(indicators)
      .filter(([, enabled]) => enabled)
      .map(([key]) => key.toUpperCase())
  ));

  const normalizeChartAnnotationPayload = (annotation, symbol) => {
    if (!annotation || typeof annotation !== 'object') {
      return null;
    }
    const type = String(annotation.type || '').trim();
    if (!['horizontal', 'trendline', 'rectangle', 'ruler'].includes(type)) {
      return null;
    }
    const normalizedSymbol = normalizeMonitorSymbol(symbol);
    const id = `assistant-annotation-${normalizedSymbol || 'symbol'}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    if (type === 'horizontal') {
      const price = Number(annotation.price);
      if (!Number.isFinite(price)) {
        return null;
      }
      return {
        id,
        type,
        price,
        meta: annotation.meta || {},
      };
    }
    const startTs = Number(annotation.startTs);
    const endTs = Number(annotation.endTs);
    const startPrice = Number(annotation.startPrice);
    const endPrice = Number(annotation.endPrice);
    if (
      !Number.isFinite(startTs)
      || !Number.isFinite(endTs)
      || !Number.isFinite(startPrice)
      || !Number.isFinite(endPrice)
    ) {
      return null;
    }
    return {
      id,
      type,
      startTs,
      endTs,
      startPrice,
      endPrice,
      meta: annotation.meta || {},
    };
  };

  const extractStepChartAnnotations = (step) => {
    const rawAnnotations = Array.isArray(step?.output?.chart_annotations)
      ? step.output.chart_annotations
      : [];
    const normalizedSymbol = normalizeMonitorSymbol(activeSymbol.value);
    return rawAnnotations
      .map(annotation => normalizeChartAnnotationPayload(annotation, normalizedSymbol))
      .filter(Boolean);
  };

  const extractPatrolCandidateChartAnnotations = (candidate) => {
    const normalizedSymbol = normalizeMonitorSymbol(candidate?.symbol || candidate?.inst_id || activeSymbol.value);
    return (Array.isArray(candidate?.chart_annotations) ? candidate.chart_annotations : [])
      .map(annotation => normalizeChartAnnotationPayload(annotation, normalizedSymbol))
      .filter(Boolean);
  };

  const extractOrderDraftChartAnnotations = (draft) => {
    const normalizedSymbol = normalizeMonitorSymbol(draft?.inst_id || activeSymbol.value);
    return (Array.isArray(draft?.annotations) ? draft.annotations : [])
      .map(annotation => normalizeChartAnnotationPayload(annotation, normalizedSymbol))
      .filter(Boolean);
  };

  const applyAssistantStepChartAnnotations = (step) => {
    const normalizedSymbol = normalizeMonitorSymbol(activeSymbol.value);
    if (!normalizedSymbol) {
      assistantError.value = '请先选择一个币种再应用图表标记';
      return 0;
    }
    if (typeof appendChartAnnotation !== 'function') {
      assistantError.value = '当前图表标记能力不可用';
      return 0;
    }
    const annotations = extractStepChartAnnotations(step);
    if (annotations.length === 0) {
      assistantError.value = '当前步骤没有可应用到图表的标记';
      return 0;
    }
    annotations.forEach((annotation) => {
      appendChartAnnotation(normalizedSymbol, annotation);
    });
    if (typeof updateChart === 'function') {
      updateChart(normalizedSymbol, { annotationOnly: true });
    }
    assistantError.value = '';
    return annotations.length;
  };

  const applyAssistantPatrolCandidate = async (candidate) => {
    const normalizedSymbol = normalizeMonitorSymbol(candidate?.symbol || candidate?.inst_id);
    if (!normalizedSymbol) {
      assistantError.value = '候选机会缺少有效币种';
      return 0;
    }
    if (typeof openSymbolTab === 'function') {
      openSymbolTab(normalizedSymbol);
      await nextTick();
    }
    if (typeof appendChartAnnotation !== 'function') {
      assistantError.value = '当前图表标记能力不可用';
      return 0;
    }
    const annotations = extractPatrolCandidateChartAnnotations(candidate);
    if (annotations.length === 0) {
      assistantError.value = '该候选机会没有可应用的关键位标记';
      return 0;
    }
    annotations.forEach((annotation) => {
      appendChartAnnotation(normalizedSymbol, annotation);
    });
    if (typeof updateChart === 'function') {
      updateChart(normalizedSymbol, { annotationOnly: true });
    }
    assistantError.value = '';
    return annotations.length;
  };

  const applyAssistantLevelSnapshot = async (snapshot) => {
    const normalizedSymbol = normalizeMonitorSymbol(snapshot?.inst_id || snapshot?.symbol || activeSymbol.value);
    if (!normalizedSymbol) {
      assistantError.value = '关键位快照缺少有效币种';
      return 0;
    }
    if (typeof openSymbolTab === 'function') {
      openSymbolTab(normalizedSymbol);
      await nextTick();
    }
    if (typeof appendChartAnnotation !== 'function') {
      assistantError.value = '当前图表标记能力不可用';
      return 0;
    }
    const annotations = (Array.isArray(snapshot?.chart_annotations) ? snapshot.chart_annotations : [])
      .map(annotation => normalizeChartAnnotationPayload(annotation, normalizedSymbol))
      .filter(Boolean);
    if (annotations.length === 0) {
      assistantError.value = '该关键位快照没有可应用的图表标记';
      return 0;
    }
    annotations.forEach((annotation) => {
      appendChartAnnotation(normalizedSymbol, annotation);
    });
    if (typeof updateChart === 'function') {
      updateChart(normalizedSymbol, { annotationOnly: true });
    }
    assistantError.value = '';
    return annotations.length;
  };

  const applyAssistantOrderDraft = async (draft) => {
    let nextDraft = draft || {};
    const draftId = normalizeAssistantText(draft?.draft_id);

    if (draftId && (!Array.isArray(draft?.annotations) || draft.annotations.length === 0)) {
      try {
        const result = await api.getAssistantOrderDraft(draftId);
        if (result?.data?.draft) {
          nextDraft = result.data.draft;
        }
      } catch (error) {
        // 订单草案详情加载失败时，回退到列表中的缓存数据。
      }
    }

    const normalizedSymbol = normalizeMonitorSymbol(nextDraft?.inst_id || activeSymbol.value);
    if (!normalizedSymbol) {
      assistantError.value = '订单草案缺少有效币种';
      return 0;
    }
    if (typeof openSymbolTab === 'function') {
      openSymbolTab(normalizedSymbol);
      await nextTick();
    }
    if (typeof appendChartAnnotation !== 'function') {
      assistantError.value = '当前图表标记能力不可用';
      return 0;
    }
    const annotations = extractOrderDraftChartAnnotations(nextDraft);
    if (annotations.length === 0) {
      assistantError.value = '该订单草案没有可应用的图表标记';
      return 0;
    }
    annotations.forEach((annotation) => {
      appendChartAnnotation(normalizedSymbol, annotation);
    });
    if (typeof updateChart === 'function') {
      updateChart(normalizedSymbol, { annotationOnly: true });
    }
    assistantError.value = '';
    return annotations.length;
  };

  const quickPromptOptions = computed(() => {
    const symbol = normalizeMonitorSymbol(activeSymbol.value) || '当前币种';
    return [
      `先调用必要工具，帮我判断 ${symbol} 现在更适合观望、低吸还是追涨。`,
      `请给 ${symbol} 生成一份完整交易计划，包含入场区、止损、目标位、仓位预算和失效条件。`,
      `为 ${symbol} 生成一份待确认订单草案，不要下单，只给出方向、价格、数量、止损和目标。`,
      `请基于当前 ${symbol} 数据标出关键支撑位、压力位和失效位，并说明每个关键位的强弱。`,
      `请对 ${symbol} 生成未来一段时间的路径推演，给出 base / bullish / bearish 三种情景。`,
      '主动巡检我当前关注的币种，给我 3 个最值得跟踪的候选机会，并说明理由。',
      '分析我当前关注币种的相关性，告诉我哪些币种过于同向，哪些更适合分散风险。',
      `如果我只做低风险短线，帮我给出 ${symbol} 的计划和风险点。`,
    ];
  });

  const activeAssistantState = computed(() => getActiveAssistantState());

  const assistantVisibleSessions = computed(() => {
    const sessions = Array.isArray(activeAssistantState.value.sessionList)
      ? activeAssistantState.value.sessionList
      : [];
    const activeSessionId = activeAssistantState.value.sessionId
      || activeAssistantState.value.detail?.session?.session_id
      || '';
    return sessions.map((session) => ({
      ...session,
      isActive: session.session_id === activeSessionId,
      displayTime: formatAssistantTimestamp(session.updated_at || session.created_at),
    }));
  });

  const activeAssistantSteps = computed(() => (
    Array.isArray(activeAssistantState.value.detail?.steps)
      ? activeAssistantState.value.detail.steps.map((step) => {
          const chartAnnotations = extractStepChartAnnotations(step);
          return {
            ...step,
            status: normalizeAssistantText(step?.status || 'completed').toLowerCase() || 'completed',
            preview: buildStepPreviewText(step),
            chartAnnotations,
            hasChartAnnotations: chartAnnotations.length > 0,
          };
        })
      : []
  ));

  const assistantConversationMessages = computed(() => {
    const persistedMessages = Array.isArray(activeAssistantState.value.detail?.messages)
      ? activeAssistantState.value.detail.messages
        .filter((message) => (
          (message.role === 'assistant' || message.role === 'user')
          && (
            Boolean(normalizeAssistantText(message.content))
            || (
              message.role === 'assistant'
              && Array.isArray(message.metadata?.tool_calls)
              && message.metadata.tool_calls.length > 0
            )
          )
        ))
        .map((message) => ({
          id: message.id ? `assistant-persisted-${message.id}` : buildMessageId(),
          role: message.role,
          content: message.content || '',
          htmlContent: renderAssistantMessageHtml(message.content || '', message.role),
          pending: false,
          temporary: false,
          createdAt: message.created_at || '',
          metadata: message.metadata || {},
        }))
      : [];
    const temporaryMessages = Array.isArray(activeAssistantState.value.temporaryMessages)
      ? activeAssistantState.value.temporaryMessages
      : [];
    const persistedFingerprints = new Set(
      persistedMessages.map((message) => `${message.role}:${normalizeAssistantText(message.content)}`),
    );
    const filteredTemporaryMessages = temporaryMessages.filter((message) => (
      message.pending
      || !persistedFingerprints.has(`${message.role}:${normalizeAssistantText(message.content)}`)
    ));

    return [...persistedMessages, ...filteredTemporaryMessages].map((message) => ({
      ...message,
      htmlContent: renderAssistantMessageHtml(message.content || '', message.role),
    }));
  });

  const activeAssistantMessages = computed(() => {
    if (
      assistantConversationMessages.value.length === 0
      && activeAssistantSteps.value.length === 0
      && assistantProgressSteps.value.length === 0
    ) {
      return [buildDefaultAssistantMessage(normalizeMonitorSymbol(activeSymbol.value))];
    }
    return assistantConversationMessages.value;
  });

  const assistantProgressSteps = computed(() => {
    const currentRunSteps = activeAssistantSteps.value.slice(assistantCurrentRunStepOffset.value);
    if (currentRunSteps.length > 0) {
      return currentRunSteps;
    }
    if (assistantBusy.value) {
      return [
        {
          id: 'assistant-progress-planning',
          step_index: 1,
          title: '正在规划调用链路',
          tool_name: 'planning',
          status: 'running',
          preview: '正在分析问题并选择合适的工具...',
          created_at: '',
        },
      ];
    }
    return [];
  });

  const activeAssistantTimelineEntries = computed(() => {
    const conversationMessages = assistantConversationMessages.value;
    const pendingAssistantMessage = conversationMessages.find((message) => (
      message.role === 'assistant' && message.pending
    )) || null;
    const pendingAssistantTimestamp = normalizeAssistantTimelineTimestamp(pendingAssistantMessage?.createdAt);
    const persistedStepEntries = activeAssistantSteps.value.map((step) => ({
      id: `assistant-timeline-step-${buildAssistantStepFingerprint(step)}`,
      entryType: 'step',
      step,
      title: step.title || step.tool_name || '工具调用',
      toolName: step.tool_name || step.step_type || '',
      preview: step.preview,
      status: step.status,
      createdAt: step.created_at || '',
      sortTimestamp: normalizeAssistantTimelineTimestamp(step.created_at),
      sortRank: 2,
    }));
    const persistedStepFingerprints = new Set(
      activeAssistantSteps.value.map((step) => buildAssistantStepFingerprint(step)),
    );
    const liveStepEntries = assistantProgressSteps.value
      .filter((step) => !persistedStepFingerprints.has(buildAssistantStepFingerprint(step)))
      .map((step, index) => ({
        id: `assistant-live-step-${buildAssistantStepFingerprint(step)}-${index}`,
        entryType: 'step',
        step,
        title: step.title || step.tool_name || '工具调用',
        toolName: step.tool_name || step.step_type || '',
        preview: step.preview,
        status: step.status,
        createdAt: step.created_at || '',
        sortTimestamp: normalizeAssistantTimelineTimestamp(step.created_at) || pendingAssistantTimestamp || Date.now(),
        sortRank: 2,
      }));

    const messageEntries = conversationMessages.map((message) => ({
      id: `assistant-timeline-message-${message.id}`,
      entryType: 'message',
      role: message.role,
      content: message.content,
      htmlContent: message.htmlContent,
      pending: message.pending,
      metadata: message.metadata || {},
      createdAt: message.createdAt || '',
      sortTimestamp: normalizeAssistantTimelineTimestamp(message.createdAt) || pendingAssistantTimestamp || Date.now(),
      sortRank: message.role === 'user'
        ? 0
        : (
            message.pending
              ? 3
              : (normalizeAssistantText(message.content) ? 3 : 1)
          ),
    }));

    const eventTimeline = [...messageEntries, ...persistedStepEntries, ...liveStepEntries]
      .sort(compareAssistantTimelineEntries);

    const groupedEntries = [];
    let currentAssistantEntry = null;

    const flushAssistantEntry = () => {
      if (!currentAssistantEntry) {
        return;
      }
      const hasVisibleContent = Boolean(normalizeAssistantText(currentAssistantEntry.content)) || currentAssistantEntry.pending;
      const hasStepTrace = currentAssistantEntry.inlineSteps.length > 0;
      if (hasVisibleContent || hasStepTrace) {
        groupedEntries.push({
          ...currentAssistantEntry,
          htmlContent: renderAssistantMessageHtml(currentAssistantEntry.content || '', 'assistant'),
        });
      }
      currentAssistantEntry = null;
    };

    const ensureAssistantEntry = (seed = {}) => {
      if (currentAssistantEntry) {
        return currentAssistantEntry;
      }
      currentAssistantEntry = {
        id: `assistant-group-${seed.id || buildMessageId()}`,
        entryType: 'message',
        role: 'assistant',
        content: '',
        htmlContent: '',
        pending: false,
        createdAt: seed.createdAt || '',
        inlineSteps: [],
      };
      return currentAssistantEntry;
    };

    eventTimeline.forEach((entry) => {
      if (entry.entryType === 'message' && entry.role === 'user') {
        flushAssistantEntry();
        groupedEntries.push({
          ...entry,
          inlineSteps: [],
        });
        return;
      }

      if (entry.entryType === 'step') {
        const assistantEntry = ensureAssistantEntry(entry);
        assistantEntry.inlineSteps.push({
          id: entry.id,
          title: entry.title || '工具调用',
          toolName: entry.toolName || 'planning',
          preview: entry.preview || '',
          status: entry.status || 'running',
          createdAt: entry.createdAt || '',
          output: entry.step?.output || {},
          hasChartAnnotations: Boolean(entry.step?.hasChartAnnotations),
        });
        if (!assistantEntry.createdAt && entry.createdAt) {
          assistantEntry.createdAt = entry.createdAt;
        }
        return;
      }

      if (entry.role === 'assistant') {
        const assistantEntry = ensureAssistantEntry(entry);
        const hasVisibleContent = Boolean(normalizeAssistantText(entry.content)) || entry.pending;
        if (hasVisibleContent) {
          assistantEntry.content = entry.content || '';
          assistantEntry.pending = Boolean(entry.pending);
          assistantEntry.createdAt = entry.createdAt || assistantEntry.createdAt;
        } else if (!assistantEntry.createdAt && entry.createdAt) {
          assistantEntry.createdAt = entry.createdAt;
        }
      }
    });

    flushAssistantEntry();

    if (groupedEntries.length === 0) {
      return [
        {
          id: 'assistant-timeline-default',
          entryType: 'message',
          role: 'assistant',
          content: buildDefaultAssistantMessage(normalizeMonitorSymbol(activeSymbol.value)).content,
          htmlContent: buildDefaultAssistantMessage(normalizeMonitorSymbol(activeSymbol.value)).htmlContent,
          pending: false,
          createdAt: '',
          inlineSteps: [],
        },
      ];
    }
    return groupedEntries;
  });

  const assistantToolCatalog = computed(() => (
    Array.isArray(assistantTools.value)
      ? assistantTools.value.map((tool) => ({
          name: tool?.function?.name || tool?.name || '',
          description: tool?.function?.description || tool?.description || '',
        }))
      : []
  ));

  const assistantToolCount = computed(() => assistantToolCatalog.value.length);

  const assistantCurrentSession = computed(() => (
    activeAssistantState.value.detail?.session || null
  ));

  const assistantCurrentSessionTitle = computed(() => {
    const title = assistantCurrentSession.value?.title || '';
    if (title) {
      return title;
    }
    return normalizeMonitorSymbol(activeSymbol.value)
      ? `${normalizeMonitorSymbol(activeSymbol.value)} 分析会话`
      : '新分析会话';
  });

  const assistantSessionStatusText = computed(() => {
    const status = assistantCurrentSession.value?.status || '';
    if (assistantBusy.value) {
      return '分析中';
    }
    if (status === 'completed') {
      return '已完成';
    }
    if (status === 'failed') {
      return '失败';
    }
    if (status === 'active') {
      return '进行中';
    }
    return activeAssistantState.value.sessionId ? '已连接' : '未建会话';
  });

  const assistantLatestStepTitle = computed(() => (
    activeAssistantSteps.value.length > 0
      ? activeAssistantSteps.value[activeAssistantSteps.value.length - 1].title
      : ''
  ));

  const assistantPanelTabs = computed(() => ([
    {
      key: 'chat',
      label: '对话',
      badge: Math.max(activeAssistantMessages.value.length - 1, 0),
    },
    {
      key: 'steps',
      label: '步骤',
      badge: activeAssistantSteps.value.length,
    },
    {
      key: 'sessions',
      label: '资源',
      badge: (
        assistantVisibleSessions.value.length
        + assistantVisibleLevelSnapshots.value.length
        + assistantVisibleOrderDrafts.value.length
      ),
    },
    {
      key: 'patrol',
      label: '巡检',
      badge: Math.max(assistantPatrolEventList.value.length, assistantVisiblePatrolRuns.value.length),
    },
  ]));

  const assistantTriggerMeta = computed(() => {
    if (assistantBusy.value) {
      return '调用工具中';
    }
    if (!assistantStatusLoaded.value) {
      return '待连接';
    }
    if (!assistantStatus.enabled) {
      return '未启用';
    }
    if (assistantPatrolEventList.value.length > 0) {
      return '发现机会';
    }
    if (!assistantStatus.configured) {
      return '未配置';
    }
    if (activeAssistantSteps.value.length > 0) {
      return `工具 ${activeAssistantSteps.value.length} 步`;
    }
    return assistantStatus.model || '可用';
  });

  const assistantContextSummary = computed(() => {
    const normalizedSymbol = normalizeMonitorSymbol(activeSymbol.value);
    if (!normalizedSymbol) {
      return '未选择币种';
    }
    return `${normalizedSymbol} / ${marketInstType.value} / ${currentTimeframe.value}`;
  });

  const assistantInputPlaceholder = computed(() => {
    if (!normalizeMonitorSymbol(activeSymbol.value)) {
      return '先选币种';
    }
    return '输入分析请求';
  });

  const assistantCanSend = computed(() => (
    Boolean(normalizeAssistantText(assistantInput.value))
    && Boolean(normalizeMonitorSymbol(activeSymbol.value))
    && !assistantBusy.value
  ));

  const scrollAssistantMessagesToBottom = async () => {
    await nextTick();
    const container = assistantMessagesRef.value;
    if (!(container instanceof HTMLElement)) {
      return;
    }
    container.scrollTop = container.scrollHeight;
  };

  const syncAssistantInputHeight = (target = null) => {
    if (typeof window === 'undefined') {
      return;
    }

    const textarea = target?.target instanceof HTMLTextAreaElement
      ? target.target
      : (target instanceof HTMLTextAreaElement ? target : assistantInputRef.value);

    if (!(textarea instanceof HTMLTextAreaElement)) {
      return;
    }

    const styles = window.getComputedStyle(textarea);
    const lineHeight = Number.parseFloat(styles.lineHeight) || 21;
    const paddingTop = Number.parseFloat(styles.paddingTop) || 0;
    const paddingBottom = Number.parseFloat(styles.paddingBottom) || 0;
    const borderTop = Number.parseFloat(styles.borderTopWidth) || 0;
    const borderBottom = Number.parseFloat(styles.borderBottomWidth) || 0;
    const baseHeight = lineHeight + paddingTop + paddingBottom + borderTop + borderBottom;
    const maxHeight = lineHeight * 3 + paddingTop + paddingBottom + borderTop + borderBottom;

    textarea.style.height = 'auto';
    const nextHeight = Math.max(baseHeight, Math.min(textarea.scrollHeight, maxHeight));
    textarea.style.height = `${Math.ceil(nextHeight)}px`;
    textarea.style.overflowY = textarea.scrollHeight > maxHeight + 1 ? 'auto' : 'hidden';
    if (assistantExpanded.value) {
      scheduleAssistantFloatingPosition();
    }
  };

  const cancelAssistantPositionFrame = () => {
    if (assistantPositionRaf) {
      cancelAnimationFrame(assistantPositionRaf);
      assistantPositionRaf = 0;
    }
  };

  const updateAssistantFloatingPosition = () => {
    if (typeof window === 'undefined') {
      return;
    }

    const anchor = assistantAnchorRef.value;
    const viewportWidth = window.innerWidth || document.documentElement.clientWidth || 0;
    const viewportHeight = window.innerHeight || document.documentElement.clientHeight || 0;
    const margin = 12;
    const gap = 8;
    const triggerRight = 16;
    const triggerBottom = 16;
    const topSafeArea = viewportWidth >= 1280 ? 118 : 96;
    const triggerHeight = anchor instanceof HTMLElement
      ? Math.max(anchor.getBoundingClientRect().height || 0, 30)
      : 30;
    const layoutPreset = assistantLayoutPreset.value;
    const availableWidth = Math.max(280, viewportWidth - triggerRight - margin);
    const width = Math.min(layoutPreset.width, availableWidth);
    const panelBottom = triggerBottom + triggerHeight + gap;
    const availableHeight = Math.max(240, viewportHeight - panelBottom - topSafeArea);
    const maxHeight = Math.min(layoutPreset.maxHeight, availableHeight);
    const resolvedHeight = Math.max(
      Math.min(layoutPreset.minHeight, maxHeight),
      Math.min(layoutPreset.preferredHeight, maxHeight),
    );

    assistantFloatingStyle.value = {
      position: 'fixed',
      top: 'auto',
      left: 'auto',
      right: `${triggerRight}px`,
      bottom: `${panelBottom}px`,
      width: `${Math.round(width)}px`,
      height: `${Math.round(resolvedHeight)}px`,
      maxWidth: `${Math.round(availableWidth)}px`,
      maxHeight: `${Math.round(maxHeight)}px`,
      zIndex: 2000,
    };
  };

  const scheduleAssistantFloatingPosition = () => {
    if (typeof window === 'undefined') {
      return;
    }
    cancelAssistantPositionFrame();
    assistantPositionRaf = requestAnimationFrame(() => {
      assistantPositionRaf = 0;
      updateAssistantFloatingPosition();
    });
  };

  const handleAssistantViewportChange = () => {
    if (!assistantExpanded.value) {
      return;
    }
    scheduleAssistantFloatingPosition();
  };

  const bindAssistantViewportListeners = () => {
    if (typeof window === 'undefined' || assistantViewportListenersBound) {
      return;
    }
    assistantViewportListenersBound = true;
    window.addEventListener('resize', handleAssistantViewportChange);
  };

  const unbindAssistantViewportListeners = () => {
    if (typeof window === 'undefined' || !assistantViewportListenersBound) {
      return;
    }
    assistantViewportListenersBound = false;
    window.removeEventListener('resize', handleAssistantViewportChange);
  };

  const applyAssistantSessionSummary = (state, session) => {
    if (!session || !session.session_id) {
      return;
    }
    const nextList = Array.isArray(state.sessionList) ? [...state.sessionList] : [];
    const existingIndex = nextList.findIndex((item) => item.session_id === session.session_id);
    if (existingIndex >= 0) {
      nextList.splice(existingIndex, 1);
    }
    nextList.unshift(session);
    state.sessionList = nextList;
  };

  const hydrateAssistantSessionDetail = (state, detail, options = {}) => {
    const pendingAssistantMessages = options.preservePendingAssistant
      ? (Array.isArray(state.temporaryMessages)
          ? state.temporaryMessages.filter((message) => message.role === 'assistant' && message.pending)
          : [])
      : [];
    state.detail = normalizeSessionDetail(detail);
    state.sessionId = state.detail.session?.session_id || state.sessionId;
    state.temporaryMessages = pendingAssistantMessages;
    if (state.detail.session) {
      applyAssistantSessionSummary(state, state.detail.session);
    }
  };

  const loadAssistantStatus = async (force = false) => {
    if (assistantStatusLoaded.value && !force) {
      return assistantStatus;
    }

    try {
      const result = await api.getAssistantStatus();
      assistantStatus.enabled = !!result?.enabled;
      assistantStatus.configured = !!result?.configured;
      assistantStatus.provider = result?.provider || '';
      assistantStatus.model = result?.model || '';
      assistantError.value = '';
    } catch (error) {
      assistantStatus.enabled = false;
      assistantStatus.configured = false;
      assistantStatus.provider = '';
      assistantStatus.model = '';
      assistantError.value = error?.message || 'AI 助手状态获取失败';
    } finally {
      assistantStatusLoaded.value = true;
    }
    return assistantStatus;
  };

  const loadAssistantTools = async (force = false) => {
    if (assistantToolsLoaded.value && !force) {
      return assistantTools.value;
    }

    try {
      const result = await api.getAssistantAgentTools();
      assistantTools.value = Array.isArray(result?.tools) ? result.tools : [];
      if (typeof result?.enabled === 'boolean') {
        assistantStatus.enabled = result.enabled;
      }
      if (typeof result?.configured === 'boolean') {
        assistantStatus.configured = result.configured;
      }
      assistantError.value = '';
    } catch (error) {
      assistantTools.value = [];
      if (!assistantError.value) {
        assistantError.value = error?.message || 'AI 工具列表加载失败';
      }
    } finally {
      assistantToolsLoaded.value = true;
    }
    return assistantTools.value;
  };

  const applyAssistantPatrolStatusPayload = (payload) => {
    const data = payload?.data || payload || {};
    const settings = data.settings || payload?.settings || {};

    assistantPatrolConfig.enabled = !!settings.enabled;
    assistantPatrolConfig.intervalSeconds = Number(settings.interval_seconds) || 300;
    assistantPatrolConfig.scanLimit = Number(settings.scan_limit) || 24;
    assistantPatrolConfig.candidateLimit = Number(settings.candidate_limit) || 3;
    assistantPatrolConfig.instType = settings.inst_type || 'SWAP';
    assistantPatrolConfig.timeframes = Array.isArray(settings.timeframes) ? settings.timeframes : ['1H', '4H'];
    assistantPatrolConfig.candlesLimit = Number(settings.candles_limit) || 240;
    assistantPatrolConfig.recentTradeLimit = Number(settings.recent_trade_limit) || 40;
    assistantPatrolConfig.orderbookDepth = Number(settings.orderbook_depth) || 30;
    assistantPatrolConfig.mode = settings.mode || 'simulated';
    assistantPatrolConfig.minPriorityScore = Number(settings.min_priority_score) || 55;
    assistantPatrolConfig.notificationCooldownSeconds = Number(settings.notification_cooldown_seconds) || 900;

    assistantPatrolStatus.running = !!data.running;
    assistantPatrolStatus.currentPhase = data.current_phase || 'idle';
    assistantPatrolStatus.lastRunStartedAt = data.last_run_started_at || '';
    assistantPatrolStatus.lastRunFinishedAt = data.last_run_finished_at || '';
    assistantPatrolStatus.lastRunSummary = data.last_run_summary || {};
    assistantPatrolStatus.lastError = data.last_error || '';
    assistantPatrolEvents.value = Array.isArray(data.recent_events) ? data.recent_events : [];
  };

  const upsertAssistantPatrolEvent = (payload) => {
    if (!payload || typeof payload !== 'object') {
      return;
    }
    const nextId = normalizeAssistantText(payload.id);
    const current = Array.isArray(assistantPatrolEvents.value) ? assistantPatrolEvents.value : [];
    const deduped = current.filter(item => normalizeAssistantText(item?.id) !== nextId);
    assistantPatrolEvents.value = [payload, ...deduped].slice(0, 12);
  };

  const upsertAssistantPatrolRun = (run) => {
    if (!run || typeof run !== 'object') {
      return;
    }
    assistantPatrolRuns.value = upsertAssistantRecords(
      assistantPatrolRuns.value,
      run,
      'run_id',
    ).slice(0, 12);
  };

  const upsertAssistantLevelSnapshot = (snapshot) => {
    if (!snapshot || typeof snapshot !== 'object') {
      return;
    }
    assistantLevelSnapshots.value = upsertAssistantRecords(
      assistantLevelSnapshots.value,
      snapshot,
      'snapshot_id',
    ).slice(0, 12);
  };

  const upsertAssistantOrderDraft = (draft) => {
    if (!draft || typeof draft !== 'object') {
      return;
    }
    assistantOrderDrafts.value = upsertAssistantRecords(
      assistantOrderDrafts.value,
      draft,
      'draft_id',
    ).slice(0, 12);
  };

  const loadAssistantPatrolStatus = async (force = false) => {
    if (assistantPatrolStatusLoaded.value && !force) {
      return assistantPatrolStatus;
    }

    try {
      const result = await api.getAssistantPatrolStatus();
      applyAssistantPatrolStatusPayload(result?.data || result);
      assistantError.value = '';
    } catch (error) {
      assistantError.value = error?.message || '加载主动巡检状态失败';
    } finally {
      assistantPatrolStatusLoaded.value = true;
    }
    return assistantPatrolStatus;
  };

  const loadAssistantPatrolRuns = async (force = false) => {
    const requestKey = assistantPatrolRunsRequestKey.value;
    if (
      assistantPatrolRunsLoaded.value
      && !force
      && assistantPatrolRunsQueryKey.value === requestKey
    ) {
      return assistantPatrolRuns.value;
    }

    assistantPatrolRunsLoading.value = true;
    let loadedSuccessfully = false;
    try {
      const result = await api.getAssistantPatrolRuns({
        inst_type: assistantPatrolConfig.instType || marketInstType.value || '',
        mode: assistantPatrolConfig.mode || 'simulated',
        limit: 12,
      });
      assistantPatrolRuns.value = Array.isArray(result?.data?.runs) ? result.data.runs : [];
      assistantPatrolRunsQueryKey.value = requestKey;
      loadedSuccessfully = true;
      assistantError.value = '';
    } catch (error) {
      if (!assistantError.value) {
        assistantError.value = error?.message || '加载巡检历史失败';
      }
    } finally {
      assistantPatrolRunsLoading.value = false;
      assistantPatrolRunsLoaded.value = loadedSuccessfully;
    }
    return assistantPatrolRuns.value;
  };

  const loadAssistantLevelSnapshots = async (force = false) => {
    const normalizedSymbol = normalizeMonitorSymbol(activeSymbol.value);
    const requestKey = assistantLevelSnapshotsRequestKey.value;
    if (!normalizedSymbol) {
      assistantLevelSnapshots.value = [];
      assistantLevelSnapshotsQueryKey.value = requestKey;
      assistantLevelSnapshotsLoaded.value = true;
      return assistantLevelSnapshots.value;
    }
    if (
      assistantLevelSnapshotsLoaded.value
      && !force
      && assistantLevelSnapshotsQueryKey.value === requestKey
    ) {
      return assistantLevelSnapshots.value;
    }

    assistantLevelSnapshotsLoading.value = true;
    let loadedSuccessfully = false;
    try {
      const result = await api.getAssistantLevelSnapshots({
        inst_id: normalizedSymbol,
        limit: 12,
      });
      assistantLevelSnapshots.value = Array.isArray(result?.data?.snapshots) ? result.data.snapshots : [];
      assistantLevelSnapshotsQueryKey.value = requestKey;
      loadedSuccessfully = true;
      assistantError.value = '';
    } catch (error) {
      if (!assistantError.value) {
        assistantError.value = error?.message || '加载关键位快照失败';
      }
    } finally {
      assistantLevelSnapshotsLoading.value = false;
      assistantLevelSnapshotsLoaded.value = loadedSuccessfully;
    }
    return assistantLevelSnapshots.value;
  };

  const loadAssistantOrderDrafts = async (force = false) => {
    const normalizedSymbol = normalizeMonitorSymbol(activeSymbol.value);
    const requestKey = assistantOrderDraftsRequestKey.value;
    if (!normalizedSymbol) {
      assistantOrderDrafts.value = [];
      assistantOrderDraftsQueryKey.value = requestKey;
      assistantOrderDraftsLoaded.value = true;
      return assistantOrderDrafts.value;
    }
    if (
      assistantOrderDraftsLoaded.value
      && !force
      && assistantOrderDraftsQueryKey.value === requestKey
    ) {
      return assistantOrderDrafts.value;
    }

    assistantOrderDraftsLoading.value = true;
    let loadedSuccessfully = false;
    try {
      const result = await api.getAssistantOrderDrafts({
        inst_id: normalizedSymbol,
        limit: 12,
      });
      assistantOrderDrafts.value = Array.isArray(result?.data?.drafts) ? result.data.drafts : [];
      assistantOrderDraftsQueryKey.value = requestKey;
      loadedSuccessfully = true;
      assistantError.value = '';
    } catch (error) {
      if (!assistantError.value) {
        assistantError.value = error?.message || '加载订单草案失败';
      }
    } finally {
      assistantOrderDraftsLoading.value = false;
      assistantOrderDraftsLoaded.value = loadedSuccessfully;
    }
    return assistantOrderDrafts.value;
  };

  const saveAssistantLevelSnapshot = async () => {
    const normalizedSymbol = normalizeMonitorSymbol(activeSymbol.value);
    if (!normalizedSymbol || assistantSnapshotBusy.value) {
      return null;
    }

    const baseTimeframes = [
      currentTimeframe.value,
      '1H',
      '4H',
      '1D',
    ]
      .map(value => normalizeAssistantText(value))
      .filter(Boolean);
    const timeframes = [...new Set(baseTimeframes)];

    assistantSnapshotBusy.value = true;
    try {
      const result = await api.createAssistantLevelSnapshot({
        source: 'market_view',
        title: `${normalizedSymbol} 关键位快照`,
        note: '由行情监控面板保存',
        inst_id: normalizedSymbol,
        inst_type: marketInstType.value,
        timeframes,
      });
      const snapshot = result?.data?.snapshot || null;
      if (snapshot) {
        upsertAssistantLevelSnapshot(snapshot);
      }
      assistantLevelSnapshotsQueryKey.value = assistantLevelSnapshotsRequestKey.value;
      assistantPanelTab.value = 'sessions';
      assistantError.value = '';
      return result?.data || null;
    } catch (error) {
      assistantError.value = error?.message || '保存关键位快照失败';
      return null;
    } finally {
      assistantSnapshotBusy.value = false;
      assistantLevelSnapshotsLoaded.value = true;
    }
  };

  const setAssistantPatrolEnabled = async (nextEnabled) => {
    assistantPatrolBusy.value = true;
    try {
      const result = await api.updateAssistantPatrolConfig({
        enabled: Boolean(nextEnabled),
        interval_seconds: assistantPatrolConfig.intervalSeconds,
        scan_limit: assistantPatrolConfig.scanLimit,
        candidate_limit: assistantPatrolConfig.candidateLimit,
        inst_type: assistantPatrolConfig.instType,
        timeframes: assistantPatrolConfig.timeframes,
        candles_limit: assistantPatrolConfig.candlesLimit,
        recent_trade_limit: assistantPatrolConfig.recentTradeLimit,
        orderbook_depth: assistantPatrolConfig.orderbookDepth,
        mode: assistantPatrolConfig.mode,
        min_priority_score: assistantPatrolConfig.minPriorityScore,
        notification_cooldown_seconds: assistantPatrolConfig.notificationCooldownSeconds,
      });
      applyAssistantPatrolStatusPayload(result?.status || result?.data || result);
      assistantError.value = '';
    } catch (error) {
      assistantError.value = error?.message || '更新主动巡检配置失败';
    } finally {
      assistantPatrolBusy.value = false;
    }
  };

  const runAssistantPatrolNow = async () => {
    assistantPatrolBusy.value = true;
    try {
      const result = await api.runAssistantPatrolNow();
      if (result?.data?.event) {
        upsertAssistantPatrolEvent(result.data.event);
      }
      if (normalizeAssistantText(result?.data?.run_id)) {
        const runDetail = await api.getAssistantPatrolRun(result.data.run_id);
        if (runDetail?.data?.run) {
          upsertAssistantPatrolRun(runDetail.data.run);
        }
      } else {
        await loadAssistantPatrolRuns(true);
      }
      await loadAssistantPatrolStatus(true);
      assistantPanelTab.value = 'patrol';
      assistantError.value = '';
    } catch (error) {
      assistantError.value = error?.message || '主动巡检执行失败';
    } finally {
      assistantPatrolBusy.value = false;
    }
  };

  const loadAssistantSessionList = async (force = false) => {
    const state = getActiveAssistantState();
    if (state.listLoaded && !force) {
      return state.sessionList;
    }

    state.listLoading = true;
    try {
      const result = await api.getAssistantAgentSessions(24);
      const normalizedSymbol = normalizeMonitorSymbol(activeSymbol.value);
      const nextList = Array.isArray(result?.data)
        ? result.data.filter((session) => {
            if (session?.kind && session.kind !== 'agent') {
              return false;
            }
            if (session?.inst_type && marketInstType.value && session.inst_type !== marketInstType.value) {
              return false;
            }
            if (!normalizedSymbol) {
              return true;
            }
            return session?.inst_id === normalizedSymbol;
          })
        : [];
      state.sessionList = nextList;
      state.listLoaded = true;
      return state.sessionList;
    } catch (error) {
      assistantError.value = error?.message || '分析会话列表加载失败';
      return state.sessionList;
    } finally {
      state.listLoading = false;
    }
  };

  const stopAssistantProgressPolling = () => {
    if (assistantProgressPollTimer) {
      clearTimeout(assistantProgressPollTimer);
      assistantProgressPollTimer = 0;
    }
  };

  const loadAssistantSessionDetail = async (sessionId, options = {}) => {
    const normalizedSessionId = normalizeAssistantText(sessionId);
    if (!normalizedSessionId) {
      return null;
    }

    const state = getActiveAssistantState();
    if (!options.force && state.detail?.session?.session_id === normalizedSessionId) {
      return state.detail;
    }

    if (!options.silent) {
      state.detailLoading = true;
    }
    try {
      const result = await api.getAssistantAgentSessionDetail(normalizedSessionId);
      if (result?.data) {
        hydrateAssistantSessionDetail(state, result.data, {
          preservePendingAssistant: options.preservePendingAssistant ?? false,
        });
        if (Array.isArray(state.detail?.level_snapshots)) {
          state.detail.level_snapshots.forEach((snapshot) => {
            upsertAssistantLevelSnapshot(snapshot);
          });
        }
        if (Array.isArray(state.detail?.order_drafts)) {
          state.detail.order_drafts.forEach((draft) => {
            upsertAssistantOrderDraft(draft);
          });
        }
      }
      return state.detail;
    } catch (error) {
      if (!options.silent) {
        assistantError.value = error?.message || '分析会话详情加载失败';
      }
      return null;
    } finally {
      if (!options.silent) {
        state.detailLoading = false;
      }
    }
  };

  const scheduleAssistantProgressPolling = (sessionId, delay = 900) => {
    stopAssistantProgressPolling();
    if (!assistantBusy.value || !normalizeAssistantText(sessionId)) {
      return;
    }
    assistantProgressPollTimer = window.setTimeout(async () => {
      assistantProgressPollTimer = 0;
      if (!assistantBusy.value) {
        return;
      }
      await loadAssistantSessionDetail(sessionId, {
        force: true,
        silent: true,
        preservePendingAssistant: true,
      });
      scheduleAssistantProgressPolling(sessionId, delay);
    }, delay);
  };

  const startAssistantProgressPolling = async (sessionId) => {
    const normalizedSessionId = normalizeAssistantText(sessionId);
    if (!normalizedSessionId) {
      return;
    }
    stopAssistantProgressPolling();
    await loadAssistantSessionDetail(normalizedSessionId, {
      force: true,
      silent: true,
      preservePendingAssistant: true,
    });
    scheduleAssistantProgressPolling(normalizedSessionId);
  };

  const activateAssistantSession = async (sessionId) => {
    assistantPanelTab.value = 'chat';
    assistantProgressVisible.value = false;
    return loadAssistantSessionDetail(sessionId, { force: true });
  };

  const ensureAssistantSession = async (normalizedSymbol, marketContext) => {
    const state = getActiveAssistantState();
    const currentSessionId = state.sessionId || state.detail?.session?.session_id || '';
    if (currentSessionId) {
      return currentSessionId;
    }

    const result = await api.createAssistantAgentSession({
      title: `${normalizedSymbol} ${marketInstType.value} 分析`,
      inst_id: normalizedSymbol,
      inst_type: marketInstType.value,
      mode: 'simulated',
      metadata: {
        market_context: marketContext,
      },
    });
    const createdSession = result?.data || null;
    const createdSessionId = normalizeAssistantText(createdSession?.session_id);
    if (!createdSessionId) {
      throw new Error('创建分析会话失败');
    }

    state.sessionId = createdSessionId;
    state.detail = normalizeSessionDetail({
      session: createdSession,
      messages: [],
      steps: [],
    });
    state.temporaryMessages = [];
    applyAssistantSessionSummary(state, createdSession);
    void loadAssistantSessionList(true);
    return createdSessionId;
  };

  const buildMarketContext = () => {
    const normalizedSymbol = normalizeMonitorSymbol(activeSymbol.value);
    const candles = Array.isArray(candlesData[normalizedSymbol]) ? candlesData[normalizedSymbol] : [];
    const normalizedCandles = candles.slice(-80).map((candle) => ({
      timestamp: candle?.timestamp ?? null,
      open: Number(candle?.open) || 0,
      high: Number(candle?.high) || 0,
      low: Number(candle?.low) || 0,
      close: Number(candle?.close) || 0,
      volume: Number(candle?.volume) || 0,
    }));
    const book = activeOrderBook.value || {};
    const healthRow = activeSymbolHealthRow?.value || null;
    const marketHealth = activeSymbolMarketHealth?.value || null;
    const healthStatus = activeSymbolHealthStatus?.value || healthRow?.status || 'missing';
    const healthSummary = activeSymbolHealthSummaryText?.value || '';

    return {
      symbol: normalizedSymbol,
      inst_type: marketInstType.value,
      timeframe: currentTimeframe.value,
      display_range_days: Number(displayRangeDays.value) || 0,
      indicator_selection: selectedIndicatorLabels.value,
      ticker: {
        last: Number(activeTicker.value?.last) || 0,
        change_24h: Number(activeTicker.value?.change_24h) || 0,
        high_24h: Number(activeTicker.value?.high_24h) || 0,
        low_24h: Number(activeTicker.value?.low_24h) || 0,
        vol_24h: Number(activeTicker.value?.vol_24h) || 0,
        last_display: formatPrice(activeTicker.value?.last),
        change_display: formatChange(activeTicker.value?.change_24h),
      },
      order_book: {
        best_bid: Number(book?.best_bid) || 0,
        best_ask: Number(book?.best_ask) || 0,
        spread: Number(book?.spread) || 0,
        spread_rate: Number(book?.spread_rate) || 0,
        bids: Array.isArray(book?.bids)
          ? book.bids.slice(0, 12).map((level) => ({
              price: Number(level?.price) || 0,
              size: Number(level?.size) || 0,
              order_count: Number(level?.order_count) || 0,
            }))
          : [],
        asks: Array.isArray(book?.asks)
          ? book.asks.slice(0, 12).map((level) => ({
              price: Number(level?.price) || 0,
              size: Number(level?.size) || 0,
              order_count: Number(level?.order_count) || 0,
            }))
          : [],
      },
      candles: normalizedCandles,
      data_health: healthRow
        ? {
            symbol: healthRow.symbol || normalizedSymbol,
            status: healthStatus,
            health_score: Number(healthRow.health_score) || 0,
            coverage_ratio: Number(healthRow.coverage_ratio) || 0,
            missing_timeframes: Array.isArray(healthRow.missing_timeframes) ? healthRow.missing_timeframes : [],
            watched: Boolean(healthRow.watched),
            orphan: Boolean(healthRow.orphan),
            has_local_data: Boolean(healthRow.has_local_data),
            summary: healthSummary,
            market: marketHealth
              ? {
                  inst_type: marketHealth.inst_type || marketInstType.value,
                  inst_id: marketHealth.inst_id || normalizedSymbol,
                  health_score: Number(marketHealth.health_score) || 0,
                  candle_count: Number(marketHealth.candle_count) || 0,
                  timeframe_count: Number(marketHealth.timeframe_count) || 0,
                  timeframes: Array.isArray(marketHealth.timeframes)
                    ? marketHealth.timeframes.map((item) => ({
                        timeframe: item?.timeframe || '',
                        candle_count: Number(item?.candle_count) || 0,
                        history_complete: Boolean(item?.history_complete),
                        status: item?.status || 'missing',
                        health_score: Number(item?.health_score) || 0,
                        last_sync_time: item?.last_sync_time || '',
                        newest_time: item?.newest_time || '',
                      }))
                    : [],
                }
              : null,
          }
        : null,
    };
  };

  const syncAssistantBootstrapData = async (force = false) => {
    await Promise.all([
      loadAssistantGuardianPlans(force),
      loadAssistantStatus(force),
      loadAssistantTools(force),
      loadAssistantPatrolStatus(force),
      loadAssistantSessionList(force),
      loadAssistantLevelSnapshots(force),
      loadAssistantOrderDrafts(force),
    ]);
    await loadAssistantPatrolRuns(force);
    const state = getActiveAssistantState();
    const currentSessionId = state.sessionId || state.detail?.session?.session_id || '';
    if (currentSessionId && !state.detail) {
      await loadAssistantSessionDetail(currentSessionId, { force: false });
    }
  };

  const stopAssistantResponse = () => {
    const controller = assistantAbortController.value;
    if (controller) {
      controller.abort();
      assistantAbortController.value = null;
    }
    stopAssistantProgressPolling();

    const state = getActiveAssistantState();
    if (Array.isArray(state.temporaryMessages) && state.temporaryMessages.length > 0) {
      state.temporaryMessages = state.temporaryMessages.map((message, index) => (
        index === state.temporaryMessages.length - 1
          ? {
              ...message,
              content: normalizeAssistantText(message.content) || '本次分析已手动停止。',
              pending: false,
            }
          : message
      ));
    }

    assistantBusy.value = false;
  };

  const clearAssistantConversation = () => {
    stopAssistantResponse();
    const state = getActiveAssistantState();
    state.sessionId = '';
    state.detail = null;
    state.temporaryMessages = [];
    assistantCurrentRunStepOffset.value = 0;
    assistantProgressVisible.value = false;
    assistantError.value = '';
    assistantPanelTab.value = 'chat';
  };

  const setAssistantExpanded = (nextExpanded) => {
    const normalizedExpanded = Boolean(nextExpanded);
    if (assistantExpanded.value === normalizedExpanded) {
      return;
    }

    assistantExpanded.value = normalizedExpanded;
    if (!normalizedExpanded) {
      unbindAssistantViewportListeners();
      cancelAssistantPositionFrame();
      return;
    }

    void syncAssistantBootstrapData(false);
    bindAssistantViewportListeners();
    nextTick(() => {
      updateAssistantFloatingPosition();
      scheduleAssistantFloatingPosition();
      syncAssistantInputHeight();
      void scrollAssistantMessagesToBottom();
    });
  };

  const toggleAssistantExpanded = () => {
    setAssistantExpanded(!assistantExpanded.value);
  };

  const setAssistantPanelTab = (tabKey) => {
    assistantPanelTab.value = tabKey || 'chat';
    if (assistantPanelTab.value === 'chat') {
      void scrollAssistantMessagesToBottom();
    }
  };

  const patchTemporaryAssistantMessage = (patcher) => {
    const state = getActiveAssistantState();
    if (!Array.isArray(state.temporaryMessages) || state.temporaryMessages.length === 0) {
      return;
    }
    state.temporaryMessages = state.temporaryMessages.map((message, index) => {
      if (index !== state.temporaryMessages.length - 1 || message.role !== 'assistant') {
        return message;
      }
      return patcher(message);
    });
  };

  const submitAssistantMessage = async (prefilledText = '') => {
    const normalizedSymbol = normalizeMonitorSymbol(activeSymbol.value);
    const userInput = normalizeAssistantText(prefilledText || assistantInput.value);
    if (!normalizedSymbol || !userInput || assistantBusy.value) {
      return;
    }

    assistantError.value = '';
    assistantInput.value = '';
    await syncAssistantBootstrapData(false);
    if (!assistantStatus.enabled) {
      assistantError.value = 'AI 助手当前未启用。';
      return;
    }
    if (!assistantStatus.configured) {
      assistantError.value = 'AI 助手尚未配置，请先在设置页面填写 AI Key 和模型参数。';
      return;
    }

    const state = getActiveAssistantState();
    const marketContext = buildMarketContext();
    const currentSessionId = await ensureAssistantSession(normalizedSymbol, marketContext);
    assistantCurrentRunStepOffset.value = activeAssistantSteps.value.length;
    assistantProgressVisible.value = true;
    const now = new Date().toISOString();
    const temporaryUserMessage = {
      id: buildMessageId(),
      role: 'user',
      content: userInput,
      pending: false,
      temporary: true,
      createdAt: now,
    };
    const temporaryAssistantMessage = {
      id: buildMessageId(),
      role: 'assistant',
      content: '',
      pending: true,
      temporary: true,
      createdAt: now,
    };
    state.temporaryMessages = [temporaryUserMessage, temporaryAssistantMessage];
    state.sessionId = currentSessionId;
    assistantPanelTab.value = 'chat';
    assistantBusy.value = true;
    await scrollAssistantMessagesToBottom();
    await startAssistantProgressPolling(currentSessionId);

    const controller = new AbortController();
    assistantAbortController.value = controller;
    const requestPayload = {
      session_id: currentSessionId,
      title: '',
      message: userInput,
      inst_id: normalizedSymbol,
      inst_type: marketInstType.value,
      mode: 'simulated',
      market_context: marketContext,
      max_tool_rounds: 4,
    };

    try {
      let handledByStream = false;
      let streamDonePayload = null;
      let streamErrorMessage = '';

      const streamResponse = await api.streamAssistantAgentChat(requestPayload, {
        signal: controller.signal,
      });
      if (streamResponse.ok) {
        handledByStream = true;
        await consumeAssistantAgentStream(streamResponse, {
          onDelta: async (delta) => {
            if (!delta) {
              return;
            }
            patchTemporaryAssistantMessage((message) => ({
              ...message,
              content: `${message.content || ''}${delta}`,
              pending: true,
            }));
            await scrollAssistantMessagesToBottom();
          },
          onDone: async (payload) => {
            streamDonePayload = payload || {};
          },
          onError: async (payload) => {
            streamErrorMessage = normalizeAssistantText(payload?.message || payload?.detail || 'AI 助手请求失败');
          },
        });

        if (streamErrorMessage) {
          throw new Error(streamErrorMessage);
        }

        state.temporaryMessages = [];
        if (normalizeAssistantText(streamDonePayload?.session_id)) {
          state.sessionId = normalizeAssistantText(streamDonePayload.session_id);
        }
      } else if (streamResponse.status !== 404 && streamResponse.status !== 405) {
        const payload = await parseAgentResponsePayload(streamResponse);
        throw new Error(
          normalizeAssistantText(payload?.detail)
          || normalizeAssistantText(payload?.message)
          || normalizeAssistantText(payload?.error)
          || `请求失败 (${streamResponse.status})`
        );
      }

      if (!handledByStream) {
        const response = await api.runAssistantAgentChat(requestPayload, {
          signal: controller.signal,
        });

        const payload = await parseAgentResponsePayload(response);
        if (!response.ok) {
          throw new Error(
            normalizeAssistantText(payload?.detail)
            || normalizeAssistantText(payload?.message)
            || normalizeAssistantText(payload?.error)
            || `请求失败 (${response.status})`
          );
        }

        const resultData = payload?.data || {};
        state.temporaryMessages = [];
        if (resultData?.detail) {
          hydrateAssistantSessionDetail(state, resultData.detail);
        } else if (resultData?.session_id) {
          await loadAssistantSessionDetail(resultData.session_id, { force: true });
        }
        if (resultData?.session_id) {
          state.sessionId = resultData.session_id;
        }
      }
      assistantError.value = '';
      await Promise.all([
        loadAssistantSessionList(true),
        loadAssistantLevelSnapshots(true),
        loadAssistantOrderDrafts(true),
      ]);
      await scrollAssistantMessagesToBottom();
    } catch (error) {
      const isAbortError = error?.name === 'AbortError';
      if (isAbortError) {
        state.temporaryMessages = [
          temporaryUserMessage,
          {
            ...temporaryAssistantMessage,
            pending: false,
            content: '本次分析已手动停止。',
          },
        ];
      } else {
        const message = error?.message || 'AI 助手请求失败';
        state.temporaryMessages = [
          temporaryUserMessage,
          {
            ...temporaryAssistantMessage,
            pending: false,
            content: message,
          },
        ];
        assistantError.value = message;
      }
    } finally {
      stopAssistantProgressPolling();
      assistantBusy.value = false;
      assistantAbortController.value = null;
      await loadAssistantSessionDetail(currentSessionId, { force: true, silent: true });
      await scrollAssistantMessagesToBottom();
      await nextTick();
      syncAssistantInputHeight();
    }
  };

  watch(assistantExpanded, (expanded) => {
    if (!expanded) {
      return;
    }
    nextTick(() => {
      updateAssistantFloatingPosition();
      scheduleAssistantFloatingPosition();
      syncAssistantInputHeight();
      void scrollAssistantMessagesToBottom();
    });
  }, { flush: 'post' });

  watch([activeSymbol, marketInstType], () => {
    assistantLevelSnapshotsLoaded.value = false;
    assistantOrderDraftsLoaded.value = false;
    assistantPatrolRunsLoaded.value = false;
    assistantLevelSnapshots.value = [];
    assistantOrderDrafts.value = [];
    assistantPatrolRuns.value = [];
    if (!assistantExpanded.value) {
      return;
    }
    const state = getActiveAssistantState();
    if (state.sessionId && !state.detail) {
      void loadAssistantSessionDetail(state.sessionId);
    }
    void loadAssistantSessionList(true);
    void loadAssistantLevelSnapshots(true);
    void loadAssistantOrderDrafts(true);
    void loadAssistantPatrolRuns(true);
    nextTick(() => {
      updateAssistantFloatingPosition();
      scheduleAssistantFloatingPosition();
      syncAssistantInputHeight();
      void scrollAssistantMessagesToBottom();
    });
  });

  watch(assistantPanelTab, (tabKey) => {
    if (tabKey === 'chat') {
      nextTick(() => {
        syncAssistantInputHeight();
      });
      void scrollAssistantMessagesToBottom();
      return;
    }
    if (tabKey === 'patrol') {
      void loadAssistantPatrolRuns(false);
      return;
    }
    if (tabKey === 'sessions') {
      void loadAssistantLevelSnapshots(false);
      void loadAssistantOrderDrafts(false);
    }
  });

  watch(assistantInput, () => {
    nextTick(() => {
      syncAssistantInputHeight();
    });
  }, { flush: 'post' });

  onMounted(() => {
    if (!marketWS?.subscribeAssistantPatrol) {
      return;
    }
    assistantPatrolWsHandler = (payload) => {
      upsertAssistantPatrolEvent(payload);
      assistantPatrolStatus.lastRunFinishedAt = payload?.created_at || assistantPatrolStatus.lastRunFinishedAt;
      assistantPatrolStatus.lastRunSummary = {
        ...(assistantPatrolStatus.lastRunSummary || {}),
        emitted_candidate_count: Array.isArray(payload?.candidates) ? payload.candidates.length : 0,
      };
      if (normalizeAssistantText(payload?.run_id)) {
        void api.getAssistantPatrolRun(payload.run_id)
          .then((result) => {
            if (result?.data?.run) {
              upsertAssistantPatrolRun(result.data.run);
            }
          })
          .catch(() => {});
      } else if (assistantExpanded.value) {
        void loadAssistantPatrolRuns(true);
      }
    };
    marketWS.subscribeAssistantPatrol(assistantPatrolWsHandler);
  });

  onUnmounted(() => {
    stopAssistantResponse();
    stopAssistantProgressPolling();
    unbindAssistantViewportListeners();
    cancelAssistantPositionFrame();
    if (assistantPatrolWsHandler && marketWS?.unsubscribeAssistantPatrol) {
      marketWS.unsubscribeAssistantPatrol(assistantPatrolWsHandler);
      assistantPatrolWsHandler = null;
    }
  });

  return {
    assistantAnchorRef,
    assistantPanelRef,
    assistantMessagesRef,
    assistantInputRef,
    assistantFloatingStyle,
    assistantExpanded,
    assistantProgressVisible,
    assistantBusy,
    assistantInput,
    assistantError,
    assistantStatus,
    assistantStatusLoaded,
    assistantPatrolStatusLoaded,
    assistantPatrolBusy,
    assistantPatrolConfig,
    assistantPatrolStatus,
    assistantPatrolSummary,
    assistantPatrolMeta,
    assistantPatrolEvents: assistantVisiblePatrolEvents,
    assistantPatrolRuns: assistantVisiblePatrolRuns,
    assistantPatrolRunsLoaded,
    assistantPatrolRunsLoading,
    assistantPanelTab,
    assistantPanelTabs,
    activeAssistantMessages,
    activeAssistantTimelineEntries,
    activeAssistantSteps,
    assistantProgressSteps,
    quickPromptOptions,
    assistantTriggerMeta,
    assistantContextSummary,
    assistantInputPlaceholder,
    assistantCanSend,
    assistantVisibleSessions,
    assistantVisibleLevelSnapshots,
    assistantVisibleOrderDrafts,
    assistantLevelSnapshotsLoaded,
    assistantLevelSnapshotsLoading,
    assistantOrderDraftsLoaded,
    assistantOrderDraftsLoading,
    assistantSnapshotBusy,
    assistantToolCatalog,
    assistantToolCount,
    assistantCurrentSessionTitle,
    assistantSessionStatusText,
    assistantLatestStepTitle,
    syncAssistantInputHeight,
    assistantSessionListLoading: computed(() => activeAssistantState.value.listLoading),
    assistantDetailLoading: computed(() => activeAssistantState.value.detailLoading),
    loadAssistantStatus,
    loadAssistantTools,
    loadAssistantPatrolStatus,
    loadAssistantPatrolRuns,
    loadAssistantLevelSnapshots,
    loadAssistantOrderDrafts,
    loadAssistantSessionList,
    loadAssistantSessionDetail,
    activateAssistantSession,
    setAssistantExpanded,
    setAssistantPanelTab,
    applyAssistantStepChartAnnotations,
    applyAssistantPatrolCandidate,
    syncAssistantPatrolCandidateTimeframe,
    applyAssistantLevelSnapshot,
    applyAssistantOrderDraft,
    saveAssistantLevelSnapshot,
    setAssistantPatrolEnabled,
    runAssistantPatrolNow,
    toggleAssistantExpanded,
    clearAssistantConversation,
    stopAssistantResponse,
    submitAssistantMessage,
    formatAssistantTimestamp,
  };
};
