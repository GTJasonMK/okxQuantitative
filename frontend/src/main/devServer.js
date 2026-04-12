const http = require('node:http');
const https = require('node:https');

const DEFAULT_DEV_SERVER_URL = 'http://127.0.0.1:5173';
const MAX_RETRIES = 30;
const RETRY_INTERVAL_MS = 1000;
const PROBE_TIMEOUT_MS = 1000;

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const assertWindow = (win) => {
  if (!win || typeof win.loadURL !== 'function') {
    throw new TypeError('BrowserWindow with loadURL() is required');
  }
};

const createRequestOptions = (url) => ({
  hostname: url.hostname,
  port: url.port,
  path: url.pathname || '/',
  method: 'GET',
  timeout: PROBE_TIMEOUT_MS,
});

const probeDevServer = (urlString) => new Promise((resolve) => {
  const url = new URL(urlString);
  const client = url.protocol === 'https:' ? https : http;
  const request = client.request(createRequestOptions(url), (response) => {
    response.resume();
    resolve((response.statusCode || 0) < 500);
  });

  request.on('error', () => resolve(false));
  request.on('timeout', () => {
    request.destroy();
    resolve(false);
  });
  request.end();
});

const waitForDevServer = async ({
  probe,
  maxRetries,
  retryIntervalMs,
  logger,
  sleepFn,
}) => {
  for (let attempt = 1; attempt <= maxRetries; attempt += 1) {
    if (await probe()) {
      return;
    }
    if (attempt === maxRetries) {
      throw new Error(`Dev server unavailable after ${maxRetries} retries`);
    }
    logger.info(`[Electron] Waiting for Vite dev server... (${attempt}/${maxRetries})`);
    await sleepFn(retryIntervalMs);
  }
};

const connectDevServerWindow = async (win, options = {}) => {
  assertWindow(win);

  const url = options.url ?? DEFAULT_DEV_SERVER_URL;
  const logger = options.logger ?? console;
  const maxRetries = options.maxRetries ?? MAX_RETRIES;
  const retryIntervalMs = options.retryIntervalMs ?? RETRY_INTERVAL_MS;
  const sleepFn = options.sleep ?? sleep;
  const probe = options.probe ?? (() => probeDevServer(url));

  await waitForDevServer({
    probe,
    maxRetries,
    retryIntervalMs,
    logger,
    sleepFn,
  });
  await win.loadURL(url);
};

module.exports = {
  DEFAULT_DEV_SERVER_URL,
  MAX_RETRIES,
  RETRY_INTERVAL_MS,
  connectDevServerWindow,
  probeDevServer,
  waitForDevServer,
};
