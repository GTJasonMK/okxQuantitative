<template>
  <section class="card trend-research-card">
    <h4>会话详情</h4>
    <template v-if="session">
      <div class="collection-session-detail-grid">
        <p>session_id: {{ session.session_id || '--' }}</p>
        <p>inst_id: {{ session.inst_id || '--' }}</p>
        <p>status: {{ session.status || '--' }}</p>
        <p>planned_duration_sec: {{ session.planned_duration_sec || 0 }}</p>
        <p>stop_reason: {{ session.stop_reason || '--' }}</p>
        <p>started_at: {{ formatTimestamp(session.started_at) }}</p>
        <p>ended_at: {{ formatTimestamp(session.ended_at) }}</p>
        <p>last_error_code: {{ session.last_error_code || '--' }}</p>
        <p>last_error_message: {{ session.last_error_message || '--' }}</p>
      </div>
      <div class="collection-session-actions">
        <button
          type="button"
          class="trend-subnav-tab"
          :disabled="actionPending || !canDeleteSession(session.status)"
          @click="$emit('deleteCollectionSession', session.session_id)"
        >
          删除会话
        </button>
      </div>
      <p v-if="actionError" class="collection-session-error">
        {{ actionError }}
      </p>
    </template>
    <div v-else class="trend-subpage-placeholder empty-state">
      <strong>未选择会话</strong>
      <p>从上方会话列表选择一次采集，即可查看协议字段和错误元数据。</p>
    </div>
  </section>
</template>

<script setup>
defineProps({
  session: {
    type: Object,
    default: null,
  },
  actionPending: {
    type: Boolean,
    default: false,
  },
  actionError: {
    type: String,
    default: '',
  },
});

defineEmits(['deleteCollectionSession']);

function formatTimestamp(value) {
  if (!value) {
    return '--';
  }
  return new Date(Number(value) * 1000).toLocaleString('zh-CN', { hour12: false });
}

function canDeleteSession(status) {
  return !['starting', 'running', 'stopping'].includes(String(status || ''));
}
</script>

<style scoped src="./trendResearchPanel.css"></style>

<style scoped>
.collection-session-detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 10px 14px;
}

.collection-session-detail-grid p {
  margin: 0;
  color: var(--text-secondary);
}

.collection-session-detail-grid p:nth-child(8),
.collection-session-detail-grid p:nth-child(9) {
  color: var(--text-primary);
}

.collection-session-actions {
  margin-top: 14px;
}

.collection-session-error {
  margin: 12px 0 0;
  color: #fecaca;
}
</style>
