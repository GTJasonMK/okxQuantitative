<template>
  <div class="trading-center-view">
    <header class="tc-command-bar">
      <div class="tc-left">
        <h1 class="tc-title">交易中心</h1>
        <nav class="tc-tabs" role="tablist">
          <button
            v-for="tab in tradingTabs"
            :key="tab.key"
            class="tc-tab"
            :class="{ active: activeTab === tab.key }"
            :aria-selected="activeTab === tab.key"
            :title="tab.description"
            @click="setActiveTab(tab.key)"
          >
            {{ tab.label }}
          </button>
        </nav>
      </div>
      <p class="tc-hint">{{ activeTabHint }}</p>
    </header>

    <div class="tc-content">
      <keep-alive include="TradingView">
        <TradingView :key="activeTab" :mode="activeTab" />
      </keep-alive>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import TradingView from './TradingView.vue';
import { useAppStore } from '../stores/app';

defineOptions({
  name: 'TradingCenterView',
});

const route = useRoute();
const router = useRouter();
const appStore = useAppStore();

const TAB_STORAGE_KEY = 'okxquant.trading-center.active-tab';
const VALID_TABS = new Set(['simulated', 'live']);

const tradingTabs = [
  {
    key: 'simulated',
    label: '模拟盘交易',
    description: '优先用于验证下单流程与仓位管理',
  },
  {
    key: 'live',
    label: '实盘交易',
    description: '查看并操作真实账户的委托与持仓',
  },
];

const readStoredTab = () => {
  try {
    const stored = window.localStorage.getItem(TAB_STORAGE_KEY) || '';
    return VALID_TABS.has(stored) ? stored : '';
  } catch (error) {
    console.warn('读取交易中心分页失败:', error);
    return '';
  }
};

const persistActiveTab = (tab) => {
  try {
    window.localStorage.setItem(TAB_STORAGE_KEY, tab);
  } catch (error) {
    console.warn('保存交易中心分页失败:', error);
  }
};

const normalizeTab = (value) => {
  const normalized = String(value || '').trim().toLowerCase();
  return VALID_TABS.has(normalized) ? normalized : '';
};

const getDefaultTab = () => appStore.tradingMode || 'simulated';

const resolvePreferredTab = () => (
  normalizeTab(route.query.tab) || readStoredTab() || getDefaultTab()
);

const activeTab = computed(() => resolvePreferredTab());

const activeTabHint = computed(() => (
  tradingTabs.find(tab => tab.key === activeTab.value)?.description || ''
));

const syncRouteTab = async (tab, replace = true) => {
  const normalizedTab = normalizeTab(tab) || getDefaultTab();
  if (normalizeTab(route.query.tab) === normalizedTab) {
    persistActiveTab(normalizedTab);
    return;
  }

  persistActiveTab(normalizedTab);
  const nextLocation = {
    path: route.path,
    query: {
      ...route.query,
      tab: normalizedTab,
    },
  };

  try {
    if (replace) {
      await router.replace(nextLocation);
    } else {
      await router.push(nextLocation);
    }
  } catch (error) {
    console.warn('同步交易中心分页失败:', error);
  }
};

const setActiveTab = (tab) => {
  void syncRouteTab(tab, false);
};

watch(
  () => route.query.tab,
  (value) => {
    const normalized = normalizeTab(value);
    if (normalized) {
      persistActiveTab(normalized);
    }
  },
);

onMounted(() => {
  if (!normalizeTab(route.query.tab)) {
    void syncRouteTab(resolvePreferredTab(), true);
  }
});
</script>

<style scoped>
.trading-center-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 0;
}

.tc-command-bar {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 6px 14px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.tc-left {
  display: flex;
  align-items: center;
  gap: 20px;
  min-width: 0;
}

.tc-title {
  margin: 0;
  font-family: var(--font-heading);
  font-size: 17px;
  font-weight: 700;
  white-space: nowrap;
  background: linear-gradient(to right, var(--text-primary), var(--accent-color));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.tc-tabs {
  display: inline-flex;
  gap: 4px;
  padding: 3px;
  border-radius: var(--radius-pill);
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.tc-tab {
  padding: 6px 18px;
  font-size: 12px;
  font-weight: 600;
  font-family: var(--font-mono);
  letter-spacing: 0.3px;
  border-radius: var(--radius-pill);
  border: none;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.18s ease;
}

.tc-tab:hover {
  color: var(--text-primary);
  background: rgba(255, 255, 255, 0.06);
}

.tc-tab.active {
  color: #fff;
  background: linear-gradient(135deg, #EA580C, #F7931A);
  box-shadow: 0 0 16px -4px rgba(247, 147, 26, 0.4);
}

.tc-hint {
  margin: 0;
  font-size: 11px;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.tc-content {
  flex: 1;
  min-height: 0;
  overflow: auto;
}

@media (max-width: 768px) {
  .tc-command-bar {
    flex-wrap: wrap;
    padding: 10px 4px;
  }
  .tc-hint { display: none; }
}
</style>
