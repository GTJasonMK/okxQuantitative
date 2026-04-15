<template>
  <section class="card trend-research-card">
    <div class="collection-session-head">
      <div>
        <h4>会话列表</h4>
        <p>按状态、覆盖率和停止原因筛查历史会话，避免只看到一串 session_id。</p>
      </div>
    </div>

    <div v-if="sessions.length > 0" class="collection-session-list">
      <button
        v-for="session in sessions"
        :key="session.session_id"
        type="button"
        class="collection-session-item"
        :class="{ 'is-active': session.session_id === selectedSessionId }"
        @click="$emit('update:selectedSessionId', session.session_id)"
      >
        <div class="collection-session-row">
          <strong>{{ session.session_id }}</strong>
          <span class="trend-state-badge" :class="resolveTone(session.status)">
            {{ session.status || '--' }}
          </span>
        </div>
        <div class="collection-session-meta">
          <span>coverage_ratio: {{ formatCoverage(session.coverage_ratio ?? session.coverageRatio) }}</span>
          <span>stop_reason: {{ session.stop_reason ?? session.stopReason ?? '--' }}</span>
        </div>
      </button>
    </div>

    <div v-else class="trend-subpage-placeholder empty-state">
      <strong>暂无采集会话</strong>
      <p>启动一次秒级采集后，这里会显示历史会话及其质量摘要。</p>
    </div>
  </section>
</template>

<script setup>
defineProps({
  sessions: {
    type: Array,
    default: () => [],
  },
  selectedSessionId: {
    type: String,
    default: '',
  },
});

defineEmits(['update:selectedSessionId']);

function formatCoverage(value) {
  return `${(Number(value || 0) * 100).toFixed(2)}%`;
}

function resolveTone(status) {
  if (status === 'running' || status === 'finished') {
    return 'tone-up';
  }
  if (status === 'failed') {
    return 'tone-down';
  }
  return 'tone-warning';
}
</script>

<style scoped src="./trendResearchPanel.css"></style>

<style scoped>
.collection-session-head {
  margin-bottom: 14px;
}

.collection-session-head h4 {
  color: var(--text-primary);
}

.collection-session-head p,
.collection-session-meta span {
  color: var(--text-muted);
}

.collection-session-list {
  display: grid;
  gap: 10px;
}

.collection-session-item {
  display: grid;
  gap: 8px;
  padding: 14px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 14px;
  background: rgba(15, 23, 42, 0.16);
  text-align: left;
}

.collection-session-item.is-active {
  border-color: rgba(247, 147, 26, 0.36);
  background: rgba(247, 147, 26, 0.08);
  box-shadow: inset 0 0 0 1px rgba(247, 147, 26, 0.18);
}

.collection-session-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  color: var(--text-primary);
}

.collection-session-meta {
  display: grid;
  gap: 4px;
  font-size: 13px;
}

@media (max-width: 640px) {
  .collection-session-row {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
