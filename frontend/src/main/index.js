// Electron Main Process

const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');

// Development mode: use app.isPackaged (more reliable)
const isDev = !app.isPackaged;

let mainWindow = null;

const DEV_SERVER_URL = 'http://localhost:5173';
const MAX_RETRIES = 30;
const RETRY_INTERVAL_MS = 1000;

/**
 * 加载 Vite 开发服务器 URL，连接失败时自动重试
 * 解决 Electron 启动快于 Vite 导致 ERR_CONNECTION_REFUSED 的问题
 */
function loadDevURL(win, retryCount = 0) {
  win.loadURL(DEV_SERVER_URL).catch(() => {
    if (retryCount >= MAX_RETRIES) {
      console.error(`[Electron] Vite 开发服务器连接失败，已重试 ${MAX_RETRIES} 次`);
      return;
    }
    console.log(`[Electron] 等待 Vite 开发服务器... (${retryCount + 1}/${MAX_RETRIES})`);
    setTimeout(() => loadDevURL(win, retryCount + 1), RETRY_INTERVAL_MS);
  });
}

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
    // Dev mode: 加载 Vite 开发服务器，连接失败时自动重试
    loadDevURL(mainWindow);
    mainWindow.webContents.openDevTools();
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
