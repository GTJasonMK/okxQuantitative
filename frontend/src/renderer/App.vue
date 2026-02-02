<template>
  <div class="app-container">
    <!-- 侧边栏 -->
    <aside class="app-sidebar">
      <div class="sidebar-header">
        <span class="logo-icon">&#9670;</span>
        <span class="logo-text">OKX Quant</span>
      </div>

      <nav class="sidebar-nav">
        <router-link to="/" class="nav-item">
          <span class="nav-icon">&#9632;</span>
          <span class="nav-text">行情监控</span>
        </router-link>
        <router-link to="/trading/simulated" class="nav-item">
          <span class="nav-icon">&#9830;</span>
          <span class="nav-text">模拟盘交易</span>
        </router-link>
        <router-link to="/trading/live" class="nav-item nav-item-live">
          <span class="nav-icon">&#9830;</span>
          <span class="nav-text">实盘交易</span>
          <span class="live-badge">LIVE</span>
        </router-link>
        <router-link to="/backtest" class="nav-item">
          <span class="nav-icon">&#9654;</span>
          <span class="nav-text">策略回测</span>
        </router-link>
        <router-link to="/strategy" class="nav-item">
          <span class="nav-icon">&#9733;</span>
          <span class="nav-text">策略管理</span>
        </router-link>
        <router-link to="/settings" class="nav-item">
          <span class="nav-icon">&#9881;</span>
          <span class="nav-text">系统设置</span>
        </router-link>
      </nav>

      <div class="sidebar-footer">
        <div class="connection-status">
          <span class="status-dot" :class="{ connected: isConnected }"></span>
          <span class="status-text">{{ isConnected ? '已连接' : '未连接' }}</span>
        </div>
        <div class="mode-badge">{{ mode }}</div>
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

const appStore = useAppStore();

// 需要缓存的页面组件名称
const cachedViews = ['TradingView', 'MarketView', 'BacktestView']

// 连接状态
const isConnected = computed(() => appStore.isConnected);
// 侧边栏左下角徽章：表示“系统默认模式”（由后端 OKX_USE_SIMULATED 决定），不是当前页面的“查看模式”
const mode = computed(() => appStore.isSimulated ? '默认：模拟盘' : '默认：实盘');

// 后端地址（从API模块获取，支持动态更新）
const backendUrl = computed(() => {
  const url = getBaseURL();
  // 去掉协议前缀，只显示地址
  return url.replace(/^https?:\/\//, '');
});

// 当前时间
const currentTime = ref('');
let timer = null;

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

onMounted(() => {
  updateTime();
  timer = setInterval(updateTime, 1000);
  appStore.checkConnection();
});

onUnmounted(() => {
  if (timer) clearInterval(timer);
});
</script>

<style scoped>
.app-container {
  display: flex;
  height: 100vh;
  background-color: var(--bg-primary);
  color: var(--text-primary);
}

/* 侧边栏 */
.app-sidebar {
  display: flex;
  flex-direction: column;
  width: 220px;
  background: linear-gradient(180deg, var(--bg-secondary) 0%, var(--bg-primary) 100%);
  border-right: 1px solid var(--border-color);
  position: relative;
}

.app-sidebar::after {
  content: '';
  position: absolute;
  right: 0;
  top: 0;
  bottom: 0;
  width: 1px;
  background: linear-gradient(180deg, var(--accent-color) 0%, transparent 50%, var(--secondary-color) 100%);
  opacity: 0.3;
}

.sidebar-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 24px 20px;
  border-bottom: 1px solid var(--border-color);
}

.logo-icon {
  font-size: 28px;
  color: var(--accent-color);
  text-shadow: 0 0 20px var(--accent-glow);
  animation: pulse-glow 3s ease-in-out infinite;
  will-change: text-shadow;
}

@keyframes pulse-glow {
  0%, 100% { text-shadow: 0 0 10px var(--accent-glow); }
  50% { text-shadow: 0 0 25px var(--accent-glow), 0 0 40px var(--accent-glow); }
}

.logo-text {
  font-size: 18px;
  font-weight: 700;
  background: linear-gradient(135deg, var(--accent-color) 0%, var(--secondary-color) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  letter-spacing: 0.5px;
}

/* 导航 */
.sidebar-nav {
  flex: 1;
  padding: 16px 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 18px;
  border-radius: var(--radius-lg);
  color: var(--text-secondary);
  text-decoration: none;
  transition: background-color 0.2s ease, color 0.2s ease;
  position: relative;
  overflow: hidden;
}

.nav-item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: var(--accent-color);
  transform: scaleY(0);
  transition: transform 0.2s ease;
  border-radius: 0 2px 2px 0;
}

.nav-item:hover {
  color: var(--text-primary);
  background: var(--bg-hover);
}

.nav-item.router-link-active {
  color: var(--accent-color);
  background: var(--accent-bg);
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
  font-size: 14px;
  font-weight: 500;
}

/* 实盘交易导航项特殊样式 */
.nav-item-live {
  position: relative;
}

.live-badge {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  padding: 3px 8px;
  font-size: 9px;
  font-weight: 700;
  background: linear-gradient(135deg, var(--color-danger) 0%, #DC2626 100%);
  color: #fff;
  border-radius: 10px;
  letter-spacing: 0.5px;
  box-shadow: 0 0 10px rgba(239, 68, 68, 0.4);
  animation: pulse 2s ease-in-out infinite;
  will-change: opacity;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}

.nav-item-live.router-link-active .live-badge {
  box-shadow: 0 0 15px rgba(239, 68, 68, 0.6);
}

/* 侧边栏底部 */
.sidebar-footer {
  padding: 20px;
  border-top: 1px solid var(--border-color);
  background: var(--bg-tertiary);
}

.connection-status {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background-color: var(--color-danger);
  box-shadow: 0 0 10px rgba(239, 68, 68, 0.5);
  transition: background-color 0.3s ease, box-shadow 0.3s ease;
}

.status-dot.connected {
  background-color: var(--color-success);
  box-shadow: 0 0 10px rgba(34, 197, 94, 0.5);
  animation: pulse 2s ease-in-out infinite;
  will-change: opacity;
}

.status-text {
  font-size: 12px;
  color: var(--text-secondary);
  font-weight: 500;
}

.mode-badge {
  display: inline-flex;
  align-items: center;
  padding: 6px 12px;
  font-size: 11px;
  font-weight: 600;
  border-radius: 20px;
  background: var(--accent-bg);
  color: var(--accent-color);
  border: 1px solid rgba(245, 158, 11, 0.3);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

/* 主内容区域 */
.app-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.app-main {
  flex: 1;
  overflow: auto;
  padding: 24px;
  contain: layout style;
}

.app-footer {
  display: flex;
  align-items: center;
  gap: 16px;
  height: 32px;
  padding: 0 24px;
  background: var(--bg-secondary);
  border-top: 1px solid var(--border-color);
  font-size: 12px;
  color: var(--text-muted);
  font-family: var(--font-mono);
}

.footer-divider {
  color: var(--border-color);
}
</style>
