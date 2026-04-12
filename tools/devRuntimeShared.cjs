const http = require('node:http');
const https = require('node:https');
const net = require('node:net');
const { spawn } = require('node:child_process');

const LOCAL_HOST = '127.0.0.1';
const DEFAULT_BACKEND_PORT = 8000;
const DEFAULT_DEV_SERVER_PORT = 5173;
const WAIT_RETRY_INTERVAL_MS = 500;
const WAIT_MAX_RETRIES = 120;
const UTF8_ENCODING = 'utf-8';

const buildUrl = (port) => `http://${LOCAL_HOST}:${port}`;

const buildRuntimeEnv = ({
  sourceEnv = process.env,
  backendPort,
  devServerPort,
}) => ({
  ...sourceEnv,
  OKX_BACKEND_URL: buildUrl(backendPort),
  OKX_DEV_SERVER_URL: buildUrl(devServerPort),
  PYTHONIOENCODING: UTF8_ENCODING,
  PYTHONUTF8: '1',
});

const probeUrl = (urlString) => new Promise((resolve) => {
  const url = new URL(urlString);
  const client = url.protocol === 'https:' ? https : http;
  const request = client.request({
    hostname: url.hostname,
    port: url.port,
    path: url.pathname || '/',
    method: 'GET',
    timeout: 1000,
  }, (response) => {
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

const waitForUrl = async (url, label, logger = console) => {
  for (let attempt = 1; attempt <= WAIT_MAX_RETRIES; attempt += 1) {
    if (await probeUrl(url)) {
      return;
    }
    if (attempt === WAIT_MAX_RETRIES) {
      throw new Error(`${label} did not become reachable at ${url}`);
    }
    logger.log(`[wait] ${label}... (${attempt}/${WAIT_MAX_RETRIES})`);
    await new Promise((resolve) => setTimeout(resolve, WAIT_RETRY_INTERVAL_MS));
  }
};

const tryListen = (host, port) => new Promise((resolve, reject) => {
  const server = net.createServer();
  server.once('error', reject);
  server.listen(port, host, () => resolve(server));
});

const findAvailablePort = async ({
  host = LOCAL_HOST,
  preferredPort,
}) => {
  if (preferredPort) {
    try {
      const preferredServer = await tryListen(host, preferredPort);
      const { port } = preferredServer.address();
      await new Promise((resolve, reject) => preferredServer.close((error) => (
        error ? reject(error) : resolve()
      )));
      return port;
    } catch (error) {
      if (error?.code !== 'EADDRINUSE') {
        throw error;
      }
    }
  }

  const fallbackServer = await tryListen(host, 0);
  const { port } = fallbackServer.address();
  await new Promise((resolve, reject) => fallbackServer.close((error) => (
    error ? reject(error) : resolve()
  )));
  return port;
};

const writePrefixedLine = (writer, label, line) => {
  writer.write(`[${label}] ${line}\n`);
};

const createOutputDecoder = (encoding = UTF8_ENCODING) => {
  return new TextDecoder(encoding);
};

const createOutputPump = (writer, label, options = {}) => {
  const decoder = createOutputDecoder(options.encoding);
  let pending = '';

  const flush = (text, force = false) => {
    pending += text;
    let newlineIndex = pending.indexOf('\n');

    while (newlineIndex >= 0) {
      writePrefixedLine(writer, label, pending.slice(0, newlineIndex).replace(/\r$/, ''));
      pending = pending.slice(newlineIndex + 1);
      newlineIndex = pending.indexOf('\n');
    }

    if (!force || pending.length === 0) {
      return;
    }

    writePrefixedLine(writer, label, pending.replace(/\r$/, ''));
    pending = '';
  };

  return {
    push(chunk) {
      flush(decoder.decode(chunk, { stream: true }));
    },
    end() {
      flush(decoder.decode(), true);
    },
  };
};

const pipeOutput = (stream, writer, label, options = {}) => {
  if (!stream) {
    return;
  }

  const outputPump = createOutputPump(writer, label, options);
  stream.on('data', (chunk) => outputPump.push(chunk));
  stream.on('end', () => outputPump.end());
};

const WINDOWS_CMD_WRAPPERS = new Set(['npm', 'npx']);

const resolveCommand = (command, platform = process.platform) => {
  if (platform !== 'win32') {
    return command;
  }
  return WINDOWS_CMD_WRAPPERS.has(command) ? `${command}.cmd` : command;
};

const resolveSpawnOptions = (command, platform = process.platform) => {
  if (platform === 'win32' && WINDOWS_CMD_WRAPPERS.has(command)) {
    return {
      command,
      shell: true,
    };
  }

  return {
    command: resolveCommand(command, platform),
    shell: false,
  };
};

const spawnCommand = ({
  label,
  command,
  args,
  cwd,
  env,
}) => {
  const spawnOptions = resolveSpawnOptions(command);
  const child = spawn(spawnOptions.command, args, {
    cwd,
    env,
    shell: spawnOptions.shell,
    stdio: ['ignore', 'pipe', 'pipe'],
  });

  pipeOutput(child.stdout, process.stdout, label);
  pipeOutput(child.stderr, process.stderr, label);
  return child;
};

const terminateChild = async (child) => {
  if (!child || child.exitCode !== null || child.killed) {
    return;
  }

  if (process.platform === 'win32') {
    await new Promise((resolve) => {
      const killer = spawn('taskkill', ['/PID', String(child.pid), '/T', '/F'], {
        stdio: 'ignore',
      });
      killer.on('close', () => resolve());
      killer.on('error', () => resolve());
    });
    return;
  }

  child.kill('SIGTERM');
};

module.exports = {
  LOCAL_HOST,
  DEFAULT_BACKEND_PORT,
  DEFAULT_DEV_SERVER_PORT,
  buildRuntimeEnv,
  buildUrl,
  createOutputPump,
  findAvailablePort,
  probeUrl,
  resolveCommand,
  resolveSpawnOptions,
  spawnCommand,
  terminateChild,
  waitForUrl,
};
