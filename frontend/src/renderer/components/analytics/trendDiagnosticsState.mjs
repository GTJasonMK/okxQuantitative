const DEFAULT_TIMELINE_LIMIT = 80;

const normalizeArray = (value) => {
  return Array.isArray(value) ? value : [];
};

const trimTimeline = (timeline, limit = DEFAULT_TIMELINE_LIMIT) => {
  return normalizeArray(timeline).slice(-limit);
};

export const buildTrendDiagnosticsState = (payload = {}) => {
  return {
    selectedInstId: payload.selected_inst_id || '',
    instruments: normalizeArray(payload.instruments),
    globalHealth: payload.global_health || {},
    instrumentHealth: payload.instrument_health || {},
    timeline: trimTimeline(payload.timeline),
    details: payload.details || {},
    emittedAt: payload.emitted_at || null,
    error: '',
  };
};

const appendTimelineEntry = (state, entry) => {
  if (!entry) {
    return state.timeline;
  }
  return trimTimeline([...state.timeline, entry]);
};

const mergeIncrementalState = (state, event) => {
  const payload = event.payload || {};
  return {
    ...state,
    emittedAt: event.emitted_at || state.emittedAt,
    instruments: normalizeArray(event.instruments).length > 0 ? event.instruments : state.instruments,
    globalHealth: payload.global_health || state.globalHealth,
    instrumentHealth: payload.instrument_health || state.instrumentHealth,
    details: payload.details || state.details,
    timeline: appendTimelineEntry(state, payload.timeline_entry),
  };
};

export const applyTrendDiagnosticsEvent = (state, event = {}) => {
  if (event.event_type === 'snapshot') {
    return buildTrendDiagnosticsState(event);
  }

  if (event.event_type === 'timeline_appended') {
    return mergeIncrementalState(state, event);
  }

  if (['health_changed', 'feature_emitted', 'inference_emitted', 'runtime_error_changed'].includes(event.event_type)) {
    return mergeIncrementalState(state, event);
  }

  return state;
};
