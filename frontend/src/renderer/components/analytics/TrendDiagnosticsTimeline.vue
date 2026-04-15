<template>
  <section class="trend-diagnostics-card trend-diagnostics-timeline">
    <header class="trend-diagnostics-block-header">
      <div>
        <p class="trend-diagnostics-eyebrow">证据回放</p>
        <h4>最近关键事件</h4>
      </div>
      <span class="trend-diagnostics-block-caption">按顺序回放最近发生了什么</span>
    </header>

    <div v-if="timelineItems.length > 0" class="trend-diagnostics-timeline-list">
      <article
        v-for="item in timelineItems"
        :key="resolveTimelineItemKey(item)"
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

import { resolveTrendDiagnosticsTimelineKey } from './trendDiagnosticsTimelineIdentity.mjs';
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

const resolveTimelineItemKey = (item) => {
  return resolveTrendDiagnosticsTimelineKey(item);
};
</script>

<style scoped src="./trendDiagnostics.css"></style>
