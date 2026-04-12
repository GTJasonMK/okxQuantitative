export const toTradeMarkers = (markers, colors) => (
  (Array.isArray(markers) ? markers : [])
    .map((marker) => ({
      time: Math.floor(Number(marker.timestamp || 0) / 1000),
      position: marker.side === 'buy' ? 'belowBar' : 'aboveBar',
      color: marker.side === 'buy' ? colors.up : colors.down,
      shape: marker.side === 'buy' ? 'arrowUp' : 'arrowDown',
      text: marker.side === 'buy' ? 'B' : 'S',
    }))
    .filter((marker) => Number.isFinite(marker.time) && marker.time > 0)
    .sort((left, right) => left.time - right.time)
);

export const createSeriesMarkerAdapter = ({
  series,
  createSeriesMarkersImpl,
  initialMarkers = [],
  options,
}) => {
  if (!series) {
    throw new TypeError('series is required');
  }
  if (typeof createSeriesMarkersImpl !== 'function') {
    throw new TypeError('createSeriesMarkersImpl must be a function');
  }

  const plugin = createSeriesMarkersImpl(series, initialMarkers, options);
  if (!plugin || typeof plugin.setMarkers !== 'function') {
    throw new TypeError('series markers plugin API is invalid');
  }

  return {
    setMarkers(markers) {
      plugin.setMarkers(Array.isArray(markers) ? markers : []);
    },
    markers() {
      return typeof plugin.markers === 'function' ? plugin.markers() : [];
    },
    detach() {
      if (typeof plugin.detach === 'function') {
        plugin.detach();
      }
    },
  };
};
