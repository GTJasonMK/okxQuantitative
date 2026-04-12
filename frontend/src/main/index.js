// Electron Main Process

const { app, BrowserWindow, ipcMain, Notification } = require('electron');
const path = require('path');
const {
  connectDevServerWindow,
  DEFAULT_DEV_SERVER_URL,
  MAX_RETRIES,
  RETRY_INTERVAL_MS,
} = require('./devServer');

// Development mode: use app.isPackaged (more reliable)
const isDev = !app.isPackaged;

let mainWindow = null;
const activeDevServerUrl = process.env.OKX_DEV_SERVER_URL || DEFAULT_DEV_SERVER_URL;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1200,
    minHeight: 700,
    title: 'OKX Quantitative Trading',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, '../preload/index.js'),
    },
    frame: true,
    backgroundColor: '#1a1a2e',
  });

  if (isDev) {
    connectDevServerWindow(mainWindow, {
      url: activeDevServerUrl,
      maxRetries: MAX_RETRIES,
      retryIntervalMs: RETRY_INTERVAL_MS,
    })
      .then(() => {
        mainWindow.webContents.openDevTools();
      })
      .catch((error) => {
        console.error(`[Electron] ${error.message}`);
      });
  } else {
    // Production: load built files
    mainWindow.loadFile(path.join(__dirname, '../../dist-renderer/index.html'));
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// App ready
app.whenReady().then(() => {
  createWindow();

  // macOS: recreate window when dock icon clicked
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

// Quit when all windows closed (except macOS)
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// IPC: get app info
ipcMain.handle('get-app-info', () => {
  return {
    name: app.getName(),
    version: app.getVersion(),
    platform: process.platform,
    isDev: isDev,
  };
});

// IPC: get system path
ipcMain.handle('get-path', (event, name) => {
  return app.getPath(name);
});

// IPC: show desktop notification
ipcMain.handle('show-notification', (event, payload = {}) => {
  if (!Notification.isSupported()) {
    return { success: false, message: '当前环境不支持桌面通知' };
  }

  const notification = new Notification({
    title: payload.title || 'OKX Quant',
    body: payload.body || '',
    silent: Boolean(payload.silent),
  });
  notification.show();

  return { success: true };
});
