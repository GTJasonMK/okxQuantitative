const SWIMLANES = [
  { key: 'public', label: '公共 REST' },
  { key: 'private', label: '私有 REST' },
  { key: 'trade', label: '交易 REST' },
  { key: 'ws_control', label: 'WebSocket 控制' },
];

const OK_COLOR = '#22c55e';
const ERROR_COLOR = '#ef4444';
const WS_COLOR = '#f59e0b';

const clamp = (value, min, max) => Math.min(Math.max(value, min), max);

const formatTick = (value) => {
  const date = new Date(value);
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');
  const seconds = String(date.getSeconds()).padStart(2, '0');
  return `${hours}:${minutes}:${seconds}`;
};

const escapeHtml = (value) => String(value || '')
  .replaceAll('&', '&amp;')
  .replaceAll('<', '&lt;')
  .replaceAll('>', '&gt;')
  .replaceAll('"', '&quot;')
  .replaceAll("'", '&#39;');

const resolveLaneIndex = (event) => {
  const laneIndex = SWIMLANES.findIndex((lane) => lane.key === event?.target_group);
  return laneIndex >= 0 ? laneIndex : SWIMLANES.length - 1;
};

const resolvePointColor = (event) => {
  if (event?.result !== 'ok') {
    return ERROR_COLOR;
  }
  if (event?.channel === 'ws') {
    return WS_COLOR;
  }
  return OK_COLOR;
};

const buildPoint = (event) => ({
  value: [Number(event.ts || 0) * 1000, resolveLaneIndex(event), Number(event.latency_ms || 0)],
  name: event.op_key,
  symbolSize: clamp(8 + Math.round(Number(event.latency_ms || 0) / 20), 8, 18),
  itemStyle: {
    color: resolvePointColor(event),
    borderColor: 'rgba(255,255,255,0.72)',
    borderWidth: 1,
    shadowBlur: 10,
    shadowColor: 'rgba(15, 23, 42, 0.35)',
  },
  meta: event,
});

const buildTooltip = () => ({
  trigger: 'item',
  confine: true,
  backgroundColor: 'rgba(15, 23, 42, 0.94)',
  borderColor: 'rgba(148, 163, 184, 0.25)',
  textStyle: {
    color: '#e2e8f0',
    fontSize: 11,
  },
  formatter: (params) => {
    const event = params?.data?.meta || {};
    const ts = event.ts ? new Date(event.ts * 1000).toLocaleTimeString() : '--';
    const instId = event.inst_id ? escapeHtml(event.inst_id) : '--';
    const mode = event.mode ? escapeHtml(event.mode) : '--';
    const result = event.result ? escapeHtml(event.result) : '--';
    const latency = Number(event.latency_ms || 0);
    return [
      `<div style="font-weight:600;margin-bottom:6px;">${escapeHtml(event.op_key || params?.name || '--')}</div>`,
      `<div>时间: ${ts}</div>`,
      `<div>inst_id: ${instId}</div>`,
      `<div>mode: ${mode}</div>`,
      `<div>result: ${result}</div>`,
      `<div>latency: ${latency} ms</div>`,
    ].join('');
  },
});

export const buildOkxOutboundTimelineOption = ({
  windowSeconds = 600,
  generatedAt = Date.now() / 1000,
  events = [],
} = {}) => {
  const normalizedWindowSeconds = Math.max(Number(windowSeconds || 600), 10);
  const normalizedGeneratedAt = Number(generatedAt || Date.now() / 1000);
  const endMs = normalizedGeneratedAt * 1000;
  const startMs = endMs - normalizedWindowSeconds * 1000;
  const points = events.map(buildPoint);

  return {
    animation: false,
    grid: {
      top: 18,
      left: 96,
      right: 20,
      bottom: 32,
      containLabel: false,
    },
    tooltip: buildTooltip(),
    xAxis: {
      type: 'time',
      min: startMs,
      max: endMs,
      axisLabel: {
        color: '#94a3b8',
        fontSize: 10,
        formatter: formatTick,
      },
      axisLine: {
        lineStyle: { color: 'rgba(148, 163, 184, 0.24)' },
      },
      splitLine: {
        lineStyle: { color: 'rgba(148, 163, 184, 0.1)' },
      },
    },
    yAxis: {
      type: 'category',
      data: SWIMLANES.map((lane) => lane.label),
      axisLabel: {
        color: '#cbd5e1',
        fontSize: 11,
        fontWeight: 600,
      },
      axisLine: {
        lineStyle: { color: 'rgba(148, 163, 184, 0.2)' },
      },
      axisTick: { show: false },
    },
    series: [
      {
        type: 'scatter',
        data: points,
        encode: {
          x: 0,
          y: 1,
          tooltip: [2],
        },
        emphasis: {
          scale: 1.12,
        },
      },
    ],
  };
};

export { SWIMLANES };
