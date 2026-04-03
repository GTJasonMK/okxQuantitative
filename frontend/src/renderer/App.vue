<template>
  <div class="app-container">
    <!-- 侧边栏 -->
    <aside class="app-sidebar" :class="{ collapsed: sidebarCollapsed }">
      <div class="sidebar-header">
        <div class="sidebar-brand" :title="sidebarCollapsed ? 'OKX Quant' : ''">
          <span class="logo-icon">&#9670;</span>
          <span v-show="!sidebarCollapsed" class="logo-text">OKX Quant</span>
        </div>
        <button
          class="sidebar-toggle-btn"
          :title="sidebarToggleLabel"
          :aria-label="sidebarToggleLabel"
          @click="toggleSidebarCollapsed"
        >
          <span class="sidebar-toggle-icon">{{ sidebarCollapsed ? '▶' : '◀' }}</span>
        </button>
      </div>

      <nav class="sidebar-nav">
        <router-link
          v-for="item in navigationItems"
          :key="item.to"
          :to="item.to"
          class="nav-item"
          :class="{ 'nav-item-live': item.live }"
          :title="sidebarCollapsed ? item.label : ''"
        >
          <span class="nav-icon">{{ item.icon }}</span>
          <span v-show="!sidebarCollapsed" class="nav-text">{{ item.label }}</span>
          <span v-if="item.live" class="live-badge" :class="{ compact: sidebarCollapsed }">
            {{ sidebarCollapsed ? '●' : 'LIVE' }}
          </span>
        </router-link>
      </nav>

      <div class="sidebar-footer">
        <div class="connection-status">
          <span class="status-dot" :class="{ connected: isConnected }"></span>
          <span v-show="!sidebarCollapsed" class="status-text">{{ isConnected ? '已连接' : '未连接' }}</span>
        </div>
        <div class="mode-badge" :class="{ compact: sidebarCollapsed }">
          {{ sidebarCollapsed ? modeShortLabel : mode }}
        </div>
      </div>
    </aside>

    <!-- 主区域 -->
    <div class="app-content">
      <!-- 主内容区 -->
      <main class="app-main">
        <router-view v-slot="{ Component }">
          <keep-alive :include="cachedViews" :max="5">
            <component :is="Component" />
          </keep-alive>
        </router-view>
      </main>

      <!-- 底部状态栏 -->
      <footer class="app-footer">
        <span>{{ currentTime }}</span>
        <span class="footer-divider">|</span>
        <span>后端: {{ backendUrl }}</span>
      </footer>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { useAppStore } from './stores/app';
import { getBaseURL } from './services/api';
import marketWS from './services/websocket';

const appStore = useAppStore();
const SIDEBAR_COLLAPSE_STORAGE_KEY = 'okxquant.sidebar.collapsed';
const sidebarCollapsed = ref(false);

const navigationItems = [
  { to: '/', label: '行情监控', icon: '◼' },
  { to: '/data', label: '数据中心', icon: '▣' },
  { to: '/trading', label: '交易中心', icon: '◆' },
  { to: '/analytics', label: '分析中心', icon: '▥' },
  { to: '/journal', label: '交易日志', icon: '✎' },
  { to: '/strategy', label: '策略中心', icon: '★' },
  { to: '/settings', label: '系统设置', icon: '⚙' },
];

// 需要缓存的页面组件名称
const cachedViews = ['MarketView', 'AnalyticsView', 'DataCenterView', 'StrategyCenterView', 'TradingCenterView']

// 连接状态
const isConnected = computed(() => appStore.isConnected);
// 侧边栏左下角徽章：表示“系统默认模式”（由后端 OKX_USE_SIMULATED 决定），不是当前页面的“查看模式”
const mode = computed(() => appStore.isSimulated ? '默认：模拟盘' : '默认：实盘');
const modeShortLabel = computed(() => appStore.isSimulated ? 'SIM' : 'LIVE');
const sidebarToggleLabel = computed(() => sidebarCollapsed.value ? '展开侧栏' : '收起侧栏');

// 后端地址（从API模块获取，支持动态更新）
const backendUrl = computed(() => {
  const url = getBaseURL();
  // 去掉协议前缀，只显示地址
  return url.replace(/^https?:\/\//, '');
});

// 当前时间
const currentTime = ref('');
let timer = null;
let alertHandler = null;
let assistantPatrolHandler = null;

const persistSidebarCollapsed = () => {
  try {
    window.localStorage.setItem(SIDEBAR_COLLAPSE_STORAGE_KEY, sidebarCollapsed.value ? '1' : '0');
  } catch (error) {
    console.warn('保存侧栏状态失败:', error);
  }
};

const toggleSidebarCollapsed = () => {
  sidebarCollapsed.value = !sidebarCollapsed.value;
  persistSidebarCollapsed();
};

const updateTime = () => {
  const now = new Date();
  currentTime.value = now.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
};

const showDesktopAlert = async (alert) => {
  const title = alert?.title || 'OKX Quant 价格提醒';
  const body = alert?.message || '';

  try {
    if (window.electronAPI?.showNotification) {
      await window.electronAPI.showNotification({ title, body });
      return;
    }
  } catch (error) {
    console.error('Electron 桌面通知失败:', error);
  }

  if ('Notification' in window) {
    if (Notification.permission === 'granted') {
      new Notification(title, { body });
    } else if (Notification.permission !== 'denied') {
      const permission = await Notification.requestPermission();
      if (permission === 'granted') {
        new Notification(title, { body });
      }
    }
  }
};

onMounted(() => {
  try {
    const savedValue = window.localStorage.getItem(SIDEBAR_COLLAPSE_STORAGE_KEY);
    if (savedValue === '1' || savedValue === '0') {
      sidebarCollapsed.value = savedValue === '1';
    }
  } catch (error) {
    console.warn('读取侧栏状态失败:', error);
  }

  updateTime();
  timer = setInterval(updateTime, 1000);
  appStore.checkConnection();

  alertHandler = (alert) => {
    showDesktopAlert(alert);
  };
  assistantPatrolHandler = (payload) => {
    showDesktopAlert(payload);
  };

  marketWS.connect().catch((error) => {
    console.warn('全局 WebSocket 连接失败:', error);
  });
  marketWS.subscribeAlerts(alertHandler);
  marketWS.subscribeAssistantPatrol(assistantPatrolHandler);
});

onUnmounted(() => {
  if (timer) clearInterval(timer);
  if (alertHandler) {
    marketWS.unsubscribeAlerts(alertHandler);
  }
  if (assistantPatrolHandler) {
    marketWS.unsubscribeAssistantPatrol(assistantPatrolHandler);
  }
});
</script>

<style scoped>
.app-container {
  display: flex;
  height: 100vh;
  background-color: var(--bg-primary);
  color: var(--text-primary);
}

/* ===== 侧边栏 — True Void + 橙色发光边 ===== */
.app-sidebar {
  display: flex;
  flex-direction: column;
  width: 220px;
  flex: 0 0 220px;
  background: linear-gradient(180deg, #0F1115 0%, #030304 100%);
  border-right: 1px solid rgba(255, 255, 255, 0.04);
  position: relative;
  transition: width 0.22s ease, flex-basis 0.22s ease;
}

.app-sidebar.collapsed {
  width: 72px;
  flex-basis: 72px;
}

/* 右侧发光线 — Bitcoin 橙渐变 */
.app-sidebar::after {
  content: '';
  position: absolute;
  right: 0;
  top: 0;
  bottom: 0;
  width: 1px;
  background: linear-gradient(180deg, #F7931A 0%, transparent 40%, #EA580C 80%, transparent 100%);
  opacity: 0.4;
}

/* ===== 顶部 Logo ===== */
.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 18px 14px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

.sidebar-brand {
  min-width: 0;
  display: inline-flex;
  align-items: center;
  gap: 12px;
}

.app-sidebar.collapsed .sidebar-header {
  justify-content: center;
  padding-inline: 10px;
}

.logo-icon {
  font-size: 28px;
  color: var(--accent-color);
  text-shadow: 0 0 20px rgba(247, 147, 26, 0.5);
  animation: logo-glow 3s ease-in-out infinite;
}

@keyframes logo-glow {
  0%, 100% { text-shadow: 0 0 10px rgba(247, 147, 26, 0.3); }
  50% { text-shadow: 0 0 30px rgba(247, 147, 26, 0.6), 0 0 50px rgba(255, 214, 0, 0.2); }
}

.logo-text {
  font-family: var(--font-heading);
  font-size: 18px;
  font-weight: 700;
  background: linear-gradient(135deg, #F7931A 0%, #FFD600 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  letter-spacing: 0.5px;
}

.sidebar-toggle-btn {
  width: 30px;
  height: 30px;
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.03);
  color: var(--text-secondary);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.sidebar-toggle-btn:hover {
  color: var(--accent-color);
  border-color: rgba(247, 147, 26, 0.3);
  background: rgba(247, 147, 26, 0.08);
}

.sidebar-toggle-icon {
  font-size: 12px;
  line-height: 1;
}

.app-sidebar.collapsed .sidebar-toggle-btn {
  position: absolute;
  right: -12px;
  top: 18px;
  width: 24px;
  height: 24px;
  border-radius: 999px;
  background: #0F1115;
  border-color: rgba(247, 147, 26, 0.2);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
  z-index: 3;
}

/* ===== 导航 ===== */
.sidebar-nav {
  flex: 1;
  padding: 16px 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 12px 16px;
  border-radius: var(--radius-lg);
  color: var(--text-secondary);
  text-decoration: none;
  transition: all 0.2s ease;
  position: relative;
  overflow: hidden;
}

.app-sidebar.collapsed .sidebar-nav { padding-inline: 8px; }

.app-sidebar.collapsed .nav-item {
  justify-content: center;
  gap: 0;
  min-height: 46px;
  padding: 10px 0;
}

/* 左侧橙色指示条 */
.nav-item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: linear-gradient(180deg, #F7931A, #FFD600);
  transform: scaleY(0);
  transition: transform 0.2s ease;
  border-radius: 0 2px 2px 0;
}

.nav-item:hover {
  color: var(--text-primary);
  background: rgba(255, 255, 255, 0.04);
}

.nav-item.router-link-active {
  color: var(--accent-color);
  background: rgba(247, 147, 26, 0.08);
}

.nav-item.router-link-active::before {
  transform: scaleY(1);
}

.nav-icon {
  font-size: 18px;
  width: 24px;
  text-align: center;
  transition: transform 0.2s ease;
}

.nav-item:hover .nav-icon {
  transform: scale(1.1);
}

.nav-text {
  font-family: var(--font-body);
  font-size: 13px;
  font-weight: 500;
  white-space: nowrap;
}

/* LIVE 徽章 */
.nav-item-live { position: relative; }

.live-badge {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  padding: 3px 8px;
  font-family: var(--font-mono);
  font-size: 9px;
  font-weight: 700;
  background: linear-gradient(135deg, #EF4444, #DC2626);
  color: #fff;
  border-radius: var(--radius-pill);
  letter-spacing: 0.5px;
  box-shadow: 0 0 12px rgba(239, 68, 68, 0.4);
  animation: pulse 2s ease-in-out infinite;
}

.live-badge.compact {
  right: 8px;
  top: 9px;
  transform: none;
  min-width: 10px;
  height: 10px;
  padding: 0;
  border-radius: 999px;
  font-size: 0;
  box-shadow: 0 0 10px rgba(239, 68, 68, 0.5);
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

.nav-item-live.router-link-active .live-badge {
  box-shadow: 0 0 18px rgba(239, 68, 68, 0.6);
}

/* ===== 底部 ===== */
.sidebar-footer {
  padding: 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.04);
  background: rgba(15, 17, 21, 0.5);
}

.app-sidebar.collapsed .sidebar-footer {
  padding: 14px 8px;
}

.connection-status {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.app-sidebar.collapsed .connection-status {
  justify-content: center;
  margin-bottom: 8px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: var(--color-danger);
  box-shadow: 0 0 8px rgba(239, 68, 68, 0.5);
  transition: all 0.3s ease;
}

.status-dot.connected {
  background-color: var(--color-success);
  box-shadow: 0 0 8px rgba(34, 197, 94, 0.5);
  animation: pulse 2s ease-in-out infinite;
}

.status-text {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-muted);
  font-weight: 400;
}

.mode-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 5px 12px;
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 500;
  border-radius: var(--radius-pill);
  background: rgba(247, 147, 26, 0.08);
  color: var(--accent-color);
  border: 1px solid rgba(247, 147, 26, 0.2);
  text-transform: uppercase;
  letter-spacing: 0.8px;
}

.mode-badge.compact {
  width: 100%;
  min-height: 28px;
  padding: 0;
  border-radius: 10px;
  font-size: 10px;
}

/* ===== 主内容区 ===== */
.app-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.app-main {
  flex: 1;
  overflow: hidden;
  padding: 20px;
  contain: layout style;
}

.app-footer {
  display: flex;
  align-items: center;
  gap: 16px;
  height: 30px;
  padding: 0 20px;
  background: #0F1115;
  border-top: 1px solid rgba(255, 255, 255, 0.04);
  font-size: 11px;
  color: var(--text-muted);
  font-family: var(--font-mono);
}

.footer-divider {
  color: rgba(255, 255, 255, 0.1);
}

/* ===== 响应式 ===== */
@media (max-width: 1100px) {
  .app-sidebar { width: 72px; flex-basis: 72px; }

  .sidebar-header { justify-content: center; padding-inline: 10px; }

  .sidebar-brand .logo-text,
  .status-text,
  .nav-text { display: none; }

  .sidebar-nav { padding-inline: 8px; }

  .nav-item {
    justify-content: center;
    gap: 0;
    min-height: 46px;
    padding-inline: 0;
  }

  .sidebar-footer { padding: 14px 8px; }
  .connection-status { justify-content: center; }
  .mode-badge { width: 100%; justify-content: center; }
}
</style>
