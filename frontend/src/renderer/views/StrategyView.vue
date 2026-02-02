<template>
  <div class="strategy-view">
    <div class="page-header">
      <h1>策略管理</h1>
      <p>查看和管理交易策略源代码</p>
    </div>

    <div class="strategy-layout">
      <!-- 策略列表 -->
      <div class="strategy-list card">
        <div class="card-header">
          <h3 class="card-title">可用策略</h3>
          <button class="btn btn-sm" @click="reloadStrategies" :disabled="reloading">
            {{ reloading ? '加载中...' : '热加载' }}
          </button>
        </div>

        <div class="strategy-items">
          <div
            v-for="strategy in strategies"
            :key="strategy.id"
            class="strategy-item"
            :class="{ active: selectedStrategy === strategy.id }"
            @click="selectStrategy(strategy.id)"
          >
            <div class="strategy-icon">
              <span v-if="strategy.id === 'dual_ma'">MA</span>
              <span v-else-if="strategy.id === 'grid'">#</span>
              <span v-else>S</span>
            </div>
            <div class="strategy-info">
              <div class="strategy-name">{{ strategy.name }}</div>
              <div class="strategy-desc">{{ strategy.description }}</div>
            </div>
          </div>
        </div>

        <div v-if="strategies.length === 0" class="empty-list">
          暂无策略
        </div>
      </div>

      <!-- 策略源代码 -->
      <div class="strategy-detail card">
        <template v-if="selectedStrategy && currentStrategy">
          <div class="card-header">
            <h3 class="card-title">
              {{ currentStrategy.name }}
              <span class="filename">{{ sourceInfo.filename }}</span>
            </h3>
          </div>

          <div class="source-container">
            <div v-if="loadingSource" class="loading">
              加载源代码中...
            </div>
            <pre v-else class="source-code"><code>{{ sourceInfo.source }}</code></pre>
          </div>
        </template>

        <div v-else class="empty">
          <div class="empty-icon">{ }</div>
          <div class="empty-text">请选择一个策略查看源代码</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { api } from '../services/api';

// 策略列表
const strategies = ref([]);
const loading = ref(false);
const reloading = ref(false);

// 选中的策略
const selectedStrategy = ref(null);
const sourceInfo = ref({ filename: '', source: '' });
const loadingSource = ref(false);

// 当前选中的策略信息
const currentStrategy = computed(() => {
  return strategies.value.find(s => s.id === selectedStrategy.value);
});

// 加载策略列表
const loadStrategies = async () => {
  loading.value = true;
  try {
    const res = await api.getStrategies();
    if (res.code === 0 && res.data) {
      strategies.value = res.data;
      // 默认选中第一个
      if (strategies.value.length > 0 && !selectedStrategy.value) {
        selectStrategy(strategies.value[0].id);
      }
    }
  } catch (e) {
    console.error('加载策略列表失败:', e);
  } finally {
    loading.value = false;
  }
};

// 热加载策略
const reloadStrategies = async () => {
  reloading.value = true;
  try {
    const res = await api.reloadStrategies();
    if (res.code === 0) {
      // 重新加载列表
      await loadStrategies();
      // 如果当前有选中策略，重新加载源码
      if (selectedStrategy.value) {
        await loadStrategySource(selectedStrategy.value);
      }
      alert(res.message);
    }
  } catch (e) {
    console.error('热加载失败:', e);
    alert('热加载失败: ' + e.message);
  } finally {
    reloading.value = false;
  }
};

// 选择策略
const selectStrategy = (id) => {
  selectedStrategy.value = id;
};

// 加载策略源代码
const loadStrategySource = async (strategyId) => {
  loadingSource.value = true;
  try {
    const res = await api.getStrategySource(strategyId);
    if (res.code === 0 && res.data) {
      sourceInfo.value = res.data;
    }
  } catch (e) {
    console.error('加载策略源代码失败:', e);
    sourceInfo.value = { filename: '', source: '// 加载失败: ' + e.message };
  } finally {
    loadingSource.value = false;
  }
};

// 监听策略选择变化
watch(selectedStrategy, (newId) => {
  if (newId) {
    loadStrategySource(newId);
  }
});

onMounted(() => {
  loadStrategies();
});
</script>

<style scoped>
.strategy-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-header h1 {
  font-size: 20px;
  font-weight: 600;
  margin-bottom: 4px;
}

.page-header p {
  font-size: 13px;
  color: var(--text-secondary);
}

.strategy-layout {
  flex: 1;
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 16px;
  min-height: 0;
}

.strategy-list {
  height: fit-content;
  max-height: 100%;
  display: flex;
  flex-direction: column;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.btn-sm {
  padding: 4px 12px;
  font-size: 12px;
}

.strategy-items {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.strategy-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  cursor: pointer;
  transition: border-color 0.2s ease;
}

.strategy-item:hover {
  border-color: var(--accent-color);
}

.strategy-item.active {
  border-color: var(--accent-color);
  background-color: var(--accent-bg);
}

.strategy-icon {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  background-color: var(--bg-tertiary);
  border-radius: 8px;
  color: var(--accent-color);
}

.strategy-info {
  flex: 1;
  min-width: 0;
}

.strategy-name {
  font-weight: 500;
  margin-bottom: 2px;
}

.strategy-desc {
  font-size: 12px;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.empty-list {
  padding: 20px;
  text-align: center;
  color: var(--text-secondary);
}

.strategy-detail {
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.strategy-detail .card-header {
  flex-shrink: 0;
}

.filename {
  font-size: 12px;
  font-weight: normal;
  color: var(--text-secondary);
  margin-left: 8px;
}

.source-container {
  flex: 1;
  overflow: auto;
  background-color: var(--bg-tertiary);
  border-radius: 6px;
}

.source-code {
  margin: 0;
  padding: 16px;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.5;
  white-space: pre;
  color: var(--text-primary);
  overflow: visible;
}

.source-code code {
  font-family: inherit;
}

.loading {
  padding: 40px;
  text-align: center;
  color: var(--text-secondary);
}

.empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 12px;
  opacity: 0.5;
}

.empty-text {
  font-size: 14px;
}
</style>
