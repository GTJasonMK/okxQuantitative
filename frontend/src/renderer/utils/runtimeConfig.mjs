export const readElectronRuntimeConfig = (windowLike = globalThis.window) => {
  try {
    const config = windowLike?.electronAPI?.getRuntimeConfig?.();
    return config && typeof config === 'object' ? config : {};
  } catch {
    return {};
  }
};

const normalizeUrl = (value) => (
  typeof value === 'string' && value.trim() ? value.trim() : ''
);

export const resolveRuntimeBackendUrl = ({
  defaultUrl,
  savedUrl = '',
  windowLike = globalThis.window,
}) => {
  const runtimeUrl = normalizeUrl(readElectronRuntimeConfig(windowLike).backendUrl);
  return runtimeUrl || normalizeUrl(savedUrl) || defaultUrl;
};
