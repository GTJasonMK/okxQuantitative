<template>
  <section class="card trend-research-card">
    <div class="collection-control-head">
      <div>
        <h4>数据收集控制</h4>
        <p>手动启动单合约秒级会话，所有协议字段都显式展示，避免口径漂移。</p>
      </div>
      <span class="trend-state-badge" :class="statusTone">
        {{ sessionStatus }}
      </span>
    </div>

    <form class="collection-control-form" @submit.prevent="startCollectionSession">
      <label>
        <span>inst_id</span>
        <input v-model.trim="form.inst_id" type="text" placeholder="BTC-USDT-SWAP" />
      </label>
      <label>
        <span>planned_duration_sec</span>
        <input v-model.number="form.planned_duration_sec" type="number" min="1" step="1" />
      </label>
      <label>
        <span>sampling_policy_id</span>
        <input v-model.trim="form.sampling_policy_id" type="text" />
      </label>
      <label>
        <span>integrity_policy_version</span>
        <input v-model.trim="form.integrity_policy_version" type="text" />
      </label>
      <label>
        <span>collector_version</span>
        <input v-model.trim="form.collector_version" type="text" />
      </label>
      <label>
        <span>feature_recipe_version</span>
        <input v-model.trim="form.feature_recipe_version" type="text" />
      </label>
      <label>
        <span>book_channel</span>
        <select v-model="form.book_channel">
          <option value="books5">books5</option>
        </select>
      </label>
      <label>
        <span>trigger_mode</span>
        <input v-model.trim="form.trigger_mode" type="text" readonly />
      </label>
      <label class="collection-control-note">
        <span>trigger_note</span>
        <textarea v-model.trim="form.trigger_note" rows="3" placeholder="记录本次采集目的"></textarea>
      </label>
    </form>

    <div class="collection-control-actions">
      <button
        type="button"
        class="trend-subnav-tab is-active"
        :disabled="actionPending || !form.inst_id"
        @click="startCollectionSession"
      >
        开始采集
      </button>
      <button
        type="button"
        class="trend-subnav-tab"
        :disabled="actionPending || !canStopSession"
        @click="stopCollectionSession"
      >
        停止当前会话
      </button>
      <button
        type="button"
        class="trend-subnav-tab"
        :disabled="actionPending || !canDeleteSession"
        @click="deleteCollectionSession"
      >
        删除当前会话
      </button>
    </div>

    <p v-if="displayErrorMessage" class="collection-control-error">
      {{ displayErrorMessage }}
    </p>

    <div class="collection-control-summary">
      <p>当前会话：{{ activeSession?.session_id || '暂无' }}</p>
      <p>当前状态：{{ sessionStatus }}</p>
      <p>计划时长：{{ activeSession?.planned_duration_sec || form.planned_duration_sec }} 秒</p>
      <p>census 状态：{{ censusStatus?.census_policy_version || '未加载' }}</p>
      <p>last_error_code：{{ activeSession?.last_error_code || '--' }}</p>
      <p>last_error_message：{{ activeSession?.last_error_message || '--' }}</p>
    </div>
  </section>
</template>

<script setup>
import { computed, reactive } from 'vue';

const DEFAULT_PLANNED_DURATION = 1800;

const emit = defineEmits(['startCollectionSession', 'stopCollectionSession', 'deleteCollectionSession']);

const props = defineProps({
  activeSession: {
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
  censusStatus: {
    type: Object,
    default: null,
  },
});

const form = reactive({
  inst_id: 'BTC-USDT-SWAP',
  planned_duration_sec: DEFAULT_PLANNED_DURATION,
  trigger_mode: 'manual',
  trigger_note: '',
  sampling_policy_id: 'manual_session_v1',
  integrity_policy_version: 'strict_v1',
  collector_version: 'research_collector_v1',
  feature_recipe_version: 'second_state_causal_tensor_v1',
  book_channel: 'books5',
});

const sessionStatus = computed(() => String(props.activeSession?.status || 'idle'));
const canStopSession = computed(() => {
  const status = sessionStatus.value;
  return Boolean(props.activeSession?.session_id) && !['stopped', 'finished', 'failed'].includes(status);
});
const canDeleteSession = computed(() => {
  const status = sessionStatus.value;
  return Boolean(props.activeSession?.session_id) && !['starting', 'running', 'stopping'].includes(status);
});
const statusTone = computed(() => resolveStatusTone(sessionStatus.value));
const displayErrorMessage = computed(() => {
  return String(props.actionError || props.activeSession?.last_error_message || '').trim();
});

function startCollectionSession() {
  if (!String(form.inst_id || '').trim()) {
    return;
  }
  emit('startCollectionSession', buildPayload(form));
}

function stopCollectionSession() {
  if (!props.activeSession?.session_id) {
    return;
  }
  emit('stopCollectionSession', props.activeSession.session_id);
}

function deleteCollectionSession() {
  if (!props.activeSession?.session_id) {
    return;
  }
  emit('deleteCollectionSession', props.activeSession.session_id);
}

function buildPayload(formState) {
  return {
    inst_id: String(formState.inst_id || '').trim(),
    planned_duration_sec: Math.max(Number(formState.planned_duration_sec || DEFAULT_PLANNED_DURATION), 1),
    trigger_mode: String(formState.trigger_mode || 'manual'),
    trigger_note: String(formState.trigger_note || '').trim(),
    sampling_policy_id: String(formState.sampling_policy_id || '').trim(),
    integrity_policy_version: String(formState.integrity_policy_version || '').trim(),
    collector_version: String(formState.collector_version || '').trim(),
    feature_recipe_version: String(formState.feature_recipe_version || '').trim(),
    book_channel: String(formState.book_channel || 'books5').trim(),
  };
}

function resolveStatusTone(status) {
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
.collection-control-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.collection-control-head h4 {
  color: var(--text-primary);
}

.collection-control-head p,
.collection-control-summary p,
.collection-control-form span {
  color: var(--text-muted);
}

.collection-control-form {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.collection-control-form label {
  display: grid;
  gap: 6px;
}

.collection-control-form input,
.collection-control-form select,
.collection-control-form textarea {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 12px;
  background: rgba(15, 23, 42, 0.18);
  color: var(--text-primary);
}

.collection-control-note {
  grid-column: 1 / -1;
}

.collection-control-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin: 14px 0;
}

.collection-control-actions button[disabled] {
  opacity: 0.5;
  cursor: not-allowed;
}

.collection-control-error {
  margin: 0 0 14px;
  padding: 10px 12px;
  border: 1px solid rgba(248, 113, 113, 0.3);
  border-radius: 12px;
  background: rgba(127, 29, 29, 0.18);
  color: #fecaca;
}

.collection-control-summary {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 8px 12px;
}

.collection-control-summary p {
  margin: 0;
}

@media (max-width: 640px) {
  .collection-control-head {
    flex-direction: column;
  }
}
</style>
