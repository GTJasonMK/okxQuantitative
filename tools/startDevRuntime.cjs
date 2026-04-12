const path = require('node:path');

const {
  DEFAULT_BACKEND_PORT,
  DEFAULT_DEV_SERVER_PORT,
  buildRuntimeEnv,
  buildUrl,
  findAvailablePort,
  spawnCommand,
  terminateChild,
  waitForUrl,
} = require('./devRuntimeShared.cjs');

const projectRoot = path.resolve(__dirname, '..');
const backendDir = path.join(projectRoot, 'backend');
const frontendDir = path.join(projectRoot, 'frontend');

let backendProcess = null;
let viteProcess = null;
let electronProcess = null;
let shuttingDown = false;

const shutdown = async (exitCode = 0) => {
  if (shuttingDown) {
    return;
  }
  shuttingDown = true;

  await Promise.all([
    terminateChild(electronProcess),
    terminateChild(viteProcess),
    terminateChild(backendProcess),
  ]);

  process.exit(exitCode);
};

const fail = async (message) => {
  process.stderr.write(`[start] ${message}\n`);
  await shutdown(1);
};

const watchChildExit = (child, label, onExit) => {
  child.on('exit', (code, signal) => {
    if (shuttingDown) {
      return;
    }
    onExit(code, signal).catch((error) => {
      process.stderr.write(`[start] ${label} exit handling failed: ${error.message}\n`);
      shutdown(1);
    });
  });
};

const start = async () => {
  const backendPort = await findAvailablePort({ preferredPort: DEFAULT_BACKEND_PORT });
  const devServerPort = await findAvailablePort({ preferredPort: DEFAULT_DEV_SERVER_PORT });
  const runtimeEnv = buildRuntimeEnv({
    backendPort,
    devServerPort,
  });

  process.stdout.write(`[start] backend port: ${backendPort}\n`);
  process.stdout.write(`[start] vite port: ${devServerPort}\n`);

  backendProcess = spawnCommand({
    label: 'backend',
    command: 'uv',
    args: [
      'run',
      'uvicorn',
      'app.main:app',
      '--host',
      '127.0.0.1',
      '--port',
      String(backendPort),
      '--reload',
    ],
    cwd: backendDir,
    env: runtimeEnv,
  });

  watchChildExit(backendProcess, 'backend', async (code, signal) => {
    await fail(`backend exited unexpectedly (code=${code ?? 'null'}, signal=${signal ?? 'none'})`);
  });

  await waitForUrl(`${buildUrl(backendPort)}/health`, 'backend');
  process.stdout.write('[start] backend ready\n');

  viteProcess = spawnCommand({
    label: 'vite',
    command: 'npx',
    args: ['vite', '--host', '127.0.0.1', '--port', String(devServerPort)],
    cwd: frontendDir,
    env: runtimeEnv,
  });

  watchChildExit(viteProcess, 'vite', async (code, signal) => {
    await fail(`vite exited unexpectedly (code=${code ?? 'null'}, signal=${signal ?? 'none'})`);
  });

  await waitForUrl(buildUrl(devServerPort), 'vite');
  process.stdout.write('[start] vite ready\n');

  electronProcess = spawnCommand({
    label: 'electron',
    command: 'npx',
    args: ['electron', '.'],
    cwd: frontendDir,
    env: runtimeEnv,
  });

  watchChildExit(electronProcess, 'electron', async (code) => {
    await shutdown(code ?? 0);
  });
};

process.on('SIGINT', () => {
  shutdown(130);
});
process.on('SIGTERM', () => {
  shutdown(143);
});

start().catch((error) => {
  fail(error.message);
});
