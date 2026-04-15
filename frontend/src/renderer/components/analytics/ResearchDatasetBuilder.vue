<template>
  <section class="card trend-research-card">
    <div class="section-header">
      <div>
        <h4>数据集构建</h4>
        <p class="section-desc">从数据中心已完成采集会话中挑选样本来源，创建冻结的 dataset_manifest。</p>
      </div>
      <button type="button" class="trend-subnav-tab" @click="$emit('refreshSessions')">
        刷新会话
      </button>
    </div>
    <p>已选会话: {{ selectedSessionIds.length }} / 目标合约: {{ selectedInstId || '--' }}</p>
    <p>sample_filter_rule: single_session_strict_7200x900_v1</p>
    <p>label_definition_version: next_bar_15m_ohlc_reparam_from_session_seconds_v1</p>
    <div v-if="sessions.length" class="trend-builder-list">
      <label
        v-for="session in sessions"
        :key="session.session_id"
        class="trend-builder-item"
        :class="{ 'is-disabled': isSessionDisabled(session) }"
      >
        <input
          type="checkbox"
          :checked="selectedSessionIds.includes(session.session_id)"
          :disabled="isSessionDisabled(session)"
          @change="toggleSession(session.session_id, $event.target.checked)"
        >
        <span>{{ session.session_id }}</span>
        <span>{{ session.inst_id || '--' }}</span>
        <span>{{ session.status || '--' }}</span>
        <span>coverage: {{ formatCoverage(session.coverage_ratio) }}</span>
      </label>
    </div>
    <div v-else class="trend-subpage-placeholder">
      <strong>暂无可用采集会话</strong>
      <p>先到数据中心完成至少一次秒级采集，再回来创建数据集。</p>
    </div>
    <p v-if="createError" class="trend-builder-error">
      {{ createError }}
    </p>
    <button
      type="button"
      class="trend-subnav-tab"
      :disabled="createPending || !selectedSessionIds.length"
      @click="$emit('createDataset')"
    >
      创建数据集
    </button>
  </section>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  sessions: {
    type: Array,
    default: () => [],
  },
  selectedSessionIds: {
    type: Array,
    default: () => [],
  },
  createPending: {
    type: Boolean,
    default: false,
  },
  createError: {
    type: String,
    default: '',
  },
});

const emit = defineEmits(['update:selectedSessionIds', 'createDataset', 'refreshSessions']);

const selectedInstId = computed(() => {
  const selectedSession = props.sessions.find(session => props.selectedSessionIds.includes(session.session_id));
  return selectedSession?.inst_id || '';
});

function toggleSession(sessionId, checked) {
  const nextIds = checked
    ? [...new Set([...props.selectedSessionIds, sessionId])]
    : props.selectedSessionIds.filter(currentId => currentId !== sessionId);
  emit('update:selectedSessionIds', nextIds);
}

function isSessionDisabled(session) {
  if (!['stopped', 'finished'].includes(String(session.status || ''))) {
    return true;
  }
  if (!selectedInstId.value) {
    return false;
  }
  return session.inst_id !== selectedInstId.value && !props.selectedSessionIds.includes(session.session_id);
}

function formatCoverage(value) {
  return Number(value || 0).toFixed(2);
}
</script>

<style scoped src="./trendResearchPanel.css"></style>

<style scoped>
.trend-builder-list {
  display: grid;
  gap: 10px;
  margin-bottom: 12px;
}

.trend-builder-item {
  display: grid;
  grid-template-columns: auto minmax(0, 1.5fr) minmax(0, 1fr) auto auto;
  gap: 10px;
  align-items: center;
  padding: 12px 14px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  border-radius: 14px;
  background: rgba(15, 23, 42, 0.18);
}

.trend-builder-item.is-disabled {
  opacity: 0.6;
}

.trend-builder-error {
  margin: 0 0 12px;
  color: #fca5a5;
}
</style>
