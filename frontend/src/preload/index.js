// Preload 脚本
// 在渲染进程中安全地暴露主进程API

const { contextBridge, ipcRenderer } = require('electron');

// 暴露给渲染进程的API
contextBridge.exposeInMainWorld('electronAPI', {
  // 获取应用信息
  getAppInfo: () => ipcRenderer.invoke('get-app-info'),

  // 获取系统路径
  getPath: (name) => ipcRenderer.invoke('get-path', name),

  // 平台信息
  platform: process.platform,
});
