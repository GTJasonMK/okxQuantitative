<template>
  <section class="card trend-research-card">
    <div class="section-header">
      <div>
        <h4>训练发起</h4>
        <p class="section-desc">当前仍为研究占位训练执行，尚未接入真实联合分布训练器。</p>
      </div>
    </div>
    <p>selected_dataset_id: {{ selectedDatasetId || '--' }}</p>
    <label class="trend-form-field">
      <span>candidate_set_ref</span>
      <input v-model.trim="candidateSetRef" type="text" class="trend-form-input">
    </label>
    <label class="trend-form-field">
      <span>model_family</span>
      <select v-model="modelFamily" class="trend-form-input">
        <option v-for="option in modelFamilyOptions" :key="option.value" :value="option.value">
          {{ option.label }}
        </option>
      </select>
    </label>
    <label class="trend-form-field">
      <span>model_spec_ref</span>
      <input v-model.trim="modelSpecRef" type="text" class="trend-form-input">
    </label>
    <label class="trend-form-field">
      <span>training_seed</span>
      <input v-model.number="trainingSeed" type="number" min="0" step="1" class="trend-form-input">
    </label>
    <button
      type="button"
      class="trend-subnav-tab"
      :disabled="actionPending || !selectedDatasetId"
      @click="emitStart"
    >
      开始训练运行
    </button>
    <p v-if="actionError" class="trend-form-error">
      {{ actionError }}
    </p>
  </section>
</template>

<script setup>
import { ref } from 'vue';

import {
  TRAINING_CREATE_DEFAULTS,
  TRAINING_MODEL_FAMILY_OPTIONS,
} from './researchPlatformDefaults.mjs';

const props = defineProps({
  selectedDatasetId: {
    type: String,
    default: '',
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

const emit = defineEmits(['startTraining']);

const candidateSetRef = ref(TRAINING_CREATE_DEFAULTS.candidate_set_ref);
const modelFamily = ref(TRAINING_CREATE_DEFAULTS.model_family);
const modelSpecRef = ref(TRAINING_CREATE_DEFAULTS.model_spec_ref);
const trainingSeed = ref(TRAINING_CREATE_DEFAULTS.training_seed);
const modelFamilyOptions = TRAINING_MODEL_FAMILY_OPTIONS;

function emitStart() {
  emit('startTraining', {
    dataset_id: props.selectedDatasetId,
    candidate_set_ref: candidateSetRef.value,
    model_family: modelFamily.value,
    model_spec_ref: modelSpecRef.value,
    training_seed: Number(trainingSeed.value || 0),
  });
}
</script>

<style scoped src="./trendResearchPanel.css"></style>

<style scoped>
.trend-form-field {
  display: grid;
  gap: 6px;
  margin-bottom: 12px;
}

.trend-form-input {
  min-height: 40px;
  padding: 0 12px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 12px;
  background: rgba(15, 23, 42, 0.16);
  color: var(--text-primary);
}

.trend-form-error {
  margin: 12px 0 0;
  color: #fca5a5;
}
</style>
