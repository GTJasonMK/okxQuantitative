<template>
  <div class="strategy-center-view">
    <header class="sc-command-bar">
      <div class="sc-left">
        <h1 class="sc-title">策略中心</h1>
        <nav class="sc-tabs" role="tablist">
          <button
            v-for="tab in strategyTabs"
            :key="tab.key"
            class="sc-tab"
            :class="{ active: activeTab === tab.key }"
            :aria-selected="activeTab === tab.key"
            :title="tab.description"
            @click="setActiveTab(tab.key)"
          >
            {{ tab.label }}
          </button>
        </nav>
      </div>
      <p class="sc-hint">{{ activeTabHint }}</p>
    </header>

    <div class="sc-content">
      <keep-alive include="BacktestView,StrategyView">
        <component :is="activeComponent" />
      </keep-alive>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import BacktestView from './BacktestView.vue';
import StrategyView from './StrategyView.vue';

defineOptions({
  name: 'StrategyCenterView',
});

const route = useRoute();
const router = useRouter();

const TAB_STORAGE_KEY = 'okxquant.strategy-center.active-tab';
const DEFAULT_TAB = 'backtest';
const VALID_TABS = new Set(['backtest', 'manage']);

const strategyTabs = [
  {
    key: 'backtest',
    label: '策略回测',
    description: '参数验证与结果分析',
  },
  {
    key: 'manage',
    label: '策略管理',
    description: '源码、IDE、执行与风控',
  },
];

const readStoredTab = () => {
  try {
    const stored = window.localStorage.getItem(TAB_STORAGE_KEY) || '';
    return VALID_TABS.has(stored) ? stored : '';
  } catch (error) {
    console.warn('读取策略中心分页失败:', error);
    return '';
  }
};

const persistActiveTab = (tab) => {
  try {
    window.localStorage.setItem(TAB_STORAGE_KEY, tab);
  } catch (error) {
    console.warn('保存策略中心分页失败:', error);
  }
};

const normalizeTab = (value) => {
  const normalized = String(value || '').trim().toLowerCase();
  return VALID_TABS.has(normalized) ? normalized : '';
};

const resolvePreferredTab = () => (
  normalizeTab(route.query.tab) || readStoredTab() || DEFAULT_TAB
);

const activeTab = computed(() => resolvePreferredTab());

const activeComponent = computed(() => (
  activeTab.value === 'manage' ? StrategyView : BacktestView
));

const activeTabHint = computed(() => (
  strategyTabs.find(tab => tab.key === activeTab.value)?.description || ''
));

const syncRouteTab = async (tab, replace = true) => {
  const normalizedTab = normalizeTab(tab) || DEFAULT_TAB;
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
    console.warn('同步策略中心分页失败:', error);
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
.strategy-center-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 0;
}

.sc-command-bar {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 6px 14px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.sc-left {
  display: flex;
  align-items: center;
  gap: 20px;
  min-width: 0;
}

.sc-title {
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

.sc-tabs {
  display: inline-flex;
  gap: 4px;
  padding: 3px;
  border-radius: var(--radius-pill);
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.sc-tab {
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

.sc-tab:hover {
  color: var(--text-primary);
  background: rgba(255, 255, 255, 0.06);
}

.sc-tab.active {
  color: #fff;
  background: linear-gradient(135deg, #EA580C, #F7931A);
  box-shadow: 0 0 16px -4px rgba(247, 147, 26, 0.4);
}

.sc-hint {
  margin: 0;
  font-size: 11px;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sc-content {
  flex: 1;
  min-height: 0;
  overflow: auto;
}

@media (max-width: 768px) {
  .sc-command-bar {
    flex-wrap: wrap;
    padding: 10px 4px;
  }
  .sc-hint { display: none; }
}
</style>
