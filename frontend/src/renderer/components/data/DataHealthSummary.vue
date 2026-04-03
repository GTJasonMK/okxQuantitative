<template>
  <div class="data-health-summary" :class="[`status-${status}`, compact ? 'is-compact' : '']">
    <div class="data-health-head">
      <span class="data-health-badge">{{ badgeText }}</span>
      <span class="data-health-score">健康 {{ score }}</span>
    </div>
    <div class="data-health-text" :title="summaryText">{{ summaryText }}</div>
    <div v-if="instId" class="data-health-meta">{{ instId }}</div>
  </div>
</template>

<script setup>
import { computed } from 'vue';

import {
  formatDataHealthBadgeText,
  formatDataHealthSummaryText,
  getDataHealthScore,
  resolveDataHealthStatus,
} from '../../utils/dataHealth';

const props = defineProps({
  row: {
    type: Object,
    default: null,
  },
  instType: {
    type: String,
    default: 'SPOT',
  },
  instId: {
    type: String,
    default: '',
  },
  compact: {
    type: Boolean,
    default: false,
  },
});

const status = computed(() => resolveDataHealthStatus(props.row, props.instType));
const score = computed(() => getDataHealthScore(props.row));
const badgeText = computed(() => formatDataHealthBadgeText(props.row, props.instType));
const summaryText = computed(() => formatDataHealthSummaryText(props.row, props.instType));
</script>

<style scoped>
.data-health-summary {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.data-health-summary.is-compact {
  gap: 5px;
}

.data-health-head {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  flex-wrap: wrap;
}

.data-health-badge,
.data-health-score {
  display: inline-flex;
  align-items: center;
  min-height: 22px;
  padding: 0 9px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.04);
  color: var(--text-primary, #e6edf3);
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
}

.data-health-score {
  color: var(--text-secondary, #9aa4b2);
  font-weight: 600;
}

.data-health-text,
.data-health-meta {
  min-width: 0;
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-secondary, #9aa4b2);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.data-health-meta {
  color: var(--text-tertiary, #6f7b8c);
  font-family: var(--font-mono, monospace);
}

.status-healthy .data-health-badge {
  border-color: rgba(37, 198, 133, 0.24);
  background: rgba(37, 198, 133, 0.12);
  color: #80e7bf;
}

.status-degraded .data-health-badge {
  border-color: rgba(255, 196, 102, 0.24);
  background: rgba(255, 196, 102, 0.12);
  color: #ffd28a;
}

.status-stale .data-health-badge {
  border-color: rgba(255, 140, 102, 0.24);
  background: rgba(255, 140, 102, 0.12);
  color: #ffbc9c;
}

.status-missing .data-health-badge {
  border-color: rgba(255, 107, 107, 0.22);
  background: rgba(255, 107, 107, 0.12);
  color: #ffb2b2;
}
</style>
