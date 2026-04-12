const { waitForDevServer, probeDevServer } = require('../src/main/devServer');

const DEFAULT_MAX_RETRIES = 120;
const DEFAULT_RETRY_INTERVAL_MS = 500;

const parseInteger = (value, fallback) => {
  const numeric = Number.parseInt(value, 10);
  return Number.isFinite(numeric) ? numeric : fallback;
};

const main = async () => {
  const url = process.argv[2];
  const maxRetries = parseInteger(process.argv[3], DEFAULT_MAX_RETRIES);
  const retryIntervalMs = parseInteger(process.argv[4], DEFAULT_RETRY_INTERVAL_MS);

  if (!url) {
    throw new Error('Usage: node waitForDevServer.js <url> [maxRetries] [retryIntervalMs]');
  }

  await waitForDevServer({
    probe: () => probeDevServer(url),
    maxRetries,
    retryIntervalMs,
    logger: console,
    sleepFn: (delay) => new Promise((resolve) => setTimeout(resolve, delay)),
  });
};

main().catch((error) => {
  console.error(`[waitForDevServer] ${error.message}`);
  process.exitCode = 1;
});
