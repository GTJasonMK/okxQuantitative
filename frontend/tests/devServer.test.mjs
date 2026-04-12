import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);

const {
  DEFAULT_DEV_SERVER_URL,
  connectDevServerWindow,
} = require('../src/main/devServer.js');

test('connectDevServerWindow uses ipv4 loopback by default', async () => {
  const callLog = [];

  await connectDevServerWindow({
    loadURL: async (url) => {
      callLog.push(`load:${url}`);
    },
  }, {
    probe: async () => true,
    sleep: async () => {},
    logger: { info: () => {} },
  });

  assert.equal(DEFAULT_DEV_SERVER_URL, 'http://127.0.0.1:5173');
  assert.deepEqual(callLog, ['load:http://127.0.0.1:5173']);
});

test('connectDevServerWindow waits for probe success before calling loadURL', async () => {
  const callLog = [];
  const windowMock = {
    loadURL: async (url) => {
      callLog.push(`load:${url}`);
    },
  };

  let probeCount = 0;
  const logger = {
    info: (message) => callLog.push(`info:${message}`),
  };

  await connectDevServerWindow(windowMock, {
    url: 'http://localhost:5173',
    maxRetries: 3,
    retryIntervalMs: 0,
    probe: async () => {
      probeCount += 1;
      callLog.push(`probe:${probeCount}`);
      return probeCount >= 3;
    },
    sleep: async () => {
      callLog.push('sleep');
    },
    logger,
  });

  assert.equal(probeCount, 3);
  assert.deepEqual(callLog, [
    'probe:1',
    'info:[Electron] Waiting for Vite dev server... (1/3)',
    'sleep',
    'probe:2',
    'info:[Electron] Waiting for Vite dev server... (2/3)',
    'sleep',
    'probe:3',
    'load:http://localhost:5173',
  ]);
});

test('connectDevServerWindow throws after retries without loading the window', async () => {
  let loadCount = 0;
  const windowMock = {
    loadURL: async () => {
      loadCount += 1;
    },
  };

  await assert.rejects(
    connectDevServerWindow(windowMock, {
      url: 'http://localhost:5173',
      maxRetries: 2,
      retryIntervalMs: 0,
      probe: async () => false,
      sleep: async () => {},
      logger: { info: () => {} },
    }),
    /Dev server unavailable after 2 retries/,
  );

  assert.equal(loadCount, 0);
});
