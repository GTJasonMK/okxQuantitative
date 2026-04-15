<template>
  <div class="data-center-view">
    <header class="dc-command-bar">
      <div class="dc-left">
        <h1 class="dc-title">数据中心</h1>
        <nav class="dc-tabs" role="tablist">
          <button
            v-for="tab in dataTabs"
            :key="tab.key"
            class="dc-tab"
            :class="{ active: activeTab === tab.key }"
            :aria-selected="activeTab === tab.key"
            :title="tab.description"
            @click="setActiveTab(tab.key)"
          >
            {{ tab.label }}
          </button>
        </nav>
      </div>
      <p class="dc-hint">{{ activeTabHint }}</p>
    </header>

    <div class="dc-content">
      <keep-alive include="WatchlistView,DataCollectionView,InventoryView">
        <component :is="activeComponent" />
      </keep-alive>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import DataCollectionView from './DataCollectionView.vue';
import InventoryView from './InventoryView.vue';
import WatchlistView from './WatchlistView.vue';

defineOptions({
  name: 'DataCenterView',
});

const route = useRoute();
const router = useRouter();

const TAB_STORAGE_KEY = 'okxquant.data-center.active-tab';
const DEFAULT_TAB = 'watchlist';
const VALID_TABS = new Set(['watchlist', 'collection', 'inventory']);

const dataTabs = [
  {
    key: 'watchlist',
    label: '关注币种',
    description: '维护唯一监控币种与全量同步入口',
  },
  {
    key: 'collection',
    label: '秒级采集',
    description: '启动、观察与审查秒级采集会话',
  },
  {
    key: 'inventory',
    label: '数据库库存',
    description: '审查本地数据覆盖、孤儿记录与清理状态',
  },
];

const readStoredTab = () => {
  try {
    const stored = window.localStorage.getItem(TAB_STORAGE_KEY) || '';
    return VALID_TABS.has(stored) ? stored : '';
  } catch (error) {
    console.warn('读取数据中心分页失败:', error);
    return '';
  }
};

const persistActiveTab = (tab) => {
  try {
    window.localStorage.setItem(TAB_STORAGE_KEY, tab);
  } catch (error) {
    console.warn('保存数据中心分页失败:', error);
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

const activeComponent = computed(() => {
  if (activeTab.value === 'collection') {
    return DataCollectionView;
  }
  return activeTab.value === 'inventory' ? InventoryView : WatchlistView;
});

const activeTabHint = computed(() => (
  dataTabs.find(tab => tab.key === activeTab.value)?.description || ''
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
    console.warn('同步数据中心分页失败:', error);
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
.data-center-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 0;
}

/* 顶部命令栏 — 一行紧凑布局 */
.dc-command-bar {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 6px 14px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.dc-left {
  display: flex;
  align-items: center;
  gap: 20px;
  min-width: 0;
}

.dc-title {
  margin: 0;
  font-family: var(--font-heading);
  font-size: 17px;
  font-weight: 700;
  color: var(--text-primary);
  white-space: nowrap;
  background: linear-gradient(to right, var(--text-primary), var(--accent-color));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.dc-tabs {
  display: inline-flex;
  gap: 4px;
  padding: 3px;
  border-radius: var(--radius-pill);
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.dc-tab {
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

.dc-tab:hover {
  color: var(--text-primary);
  background: rgba(255, 255, 255, 0.06);
}

.dc-tab.active {
  color: #fff;
  background: linear-gradient(135deg, #EA580C, #F7931A);
  box-shadow: 0 0 16px -4px rgba(247, 147, 26, 0.4);
}

.dc-hint {
  margin: 0;
  font-size: 11px;
  color: var(--text-muted);
  white-space: nowrap;
  flex-shrink: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 内容区域 — 填满剩余空间 */
.dc-content {
  flex: 1;
  min-height: 0;
  overflow: auto;
}

@media (max-width: 768px) {
  .dc-command-bar {
    flex-wrap: wrap;
    padding: 10px 4px;
  }

  .dc-hint {
    display: none;
  }
}
</style>
