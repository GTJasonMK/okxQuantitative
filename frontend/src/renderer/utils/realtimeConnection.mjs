export function formatRealtimeConnectionError(error, fallbackMessage) {
  const detail = String(
    error?.response?.data?.detail
      || error?.message
      || fallbackMessage
      || '实时连接失败'
  ).trim();
  return detail || fallbackMessage || '实时连接失败';
}

function updateRealtimeConnectionError(errorRef, state = {}, disconnectMessage) {
  if (state.connected) {
    errorRef.value = '';
    return;
  }
  if (String(state.reason || '').trim() === 'manual disconnect') {
    return;
  }
  const detail = String(state.reason || '').trim();
  errorRef.value = detail ? `${disconnectMessage}：${detail}` : disconnectMessage;
}

export function bindRealtimeConnection({
  realtime,
  errorRef,
  connectMessage,
  disconnectMessage,
}) {
  const handleConnectionState = (state = {}) => {
    updateRealtimeConnectionError(errorRef, state, disconnectMessage);
  };

  const attachRealtimeConnection = () => {
    if (typeof realtime?.addConnectionListener === 'function') {
      realtime.addConnectionListener(handleConnectionState);
    }
    Promise.resolve()
      .then(() => realtime.connect())
      .then(() => {
        errorRef.value = '';
      })
      .catch((error) => {
        errorRef.value = formatRealtimeConnectionError(error, connectMessage);
      });
  };

  const detachRealtimeConnection = () => {
    if (typeof realtime?.removeConnectionListener === 'function') {
      realtime.removeConnectionListener(handleConnectionState);
    }
  };

  return {
    attachRealtimeConnection,
    detachRealtimeConnection,
  };
}
