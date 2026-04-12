<template>
  <section class="trend-diagnostics-card trend-diagnostics-timeline">
    <header class="trend-diagnostics-block-header">
      <div>
        <p class="trend-diagnostics-eyebrow">实时事件</p>
        <h4>诊断时间线</h4>
      </div>
      <span class="trend-diagnostics-block-caption">按事件顺序解释“为什么不刷新”</span>
    </header>

    <div v-if="timelineItems.length > 0" class="trend-diagnostics-timeline-list">
      <article
        v-for="item in timelineItems"
        :key="item.sequence || `${item.kind}-${item.emitted_at}`"
        class="trend-diagnostics-timeline-item"
      >
        <span class="trend-diagnostics-timeline-dot" :class="`tone-${resolveTimelineTone(item.kind)}`"></span>
        <div class="trend-diagnostics-timeline-copy">
          <div class="trend-diagnostics-timeline-topline">
            <strong>{{ item.label || item.kind || '事件' }}</strong>
            <span>{{ formatUnixSeconds(item.emitted_at) }}</span>
          </div>
          <p>{{ resolveTimelineCaption(item) }}</p>
        </div>
      </article>
    </div>

    <div v-else class="trend-diagnostics-inline-empty">
      {{ loading ? '等待第一批实时事件...' : '当前没有可展示的诊断事件。' }}
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue';

import {
  formatUnixSeconds,
  resolveTimelineCaption,
  resolveTimelineTone,
} from './trendDiagnosticsView.mjs';

const props = defineProps({
  items: {
    type: Array,
    default: () => [],
  },
  loading: {
    type: Boolean,
    default: false,
  },
});

const timelineItems = computed(() => {
  return [...props.items].reverse();
});
</script>

<style scoped src="./trendDiagnostics.css"></style>
