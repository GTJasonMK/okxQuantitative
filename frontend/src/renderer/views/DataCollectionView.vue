<template>
  <section class="trend-research-layout">
    <header class="section-header">
      <div>
        <h3 class="card-title">秒级采集</h3>
        <p class="section-desc">启动、观察并审查秒级采集会话与质量状态。</p>
      </div>
    </header>
    <ResearchCollectionControlCard
      :active-session="activeSession"
      :action-pending="sessionActionPending"
      :action-error="displaySessionError"
      :census-status="censusStatus"
      @start-collection-session="startCollectionSession"
      @stop-collection-session="stopCollectionSession"
      @delete-collection-session="requestDeleteCollectionSession"
    />
    <ResearchCollectionProgressBoard
      :session="activeSession"
      :coverage="sessionCoverage"
      :progress="sessionProgress"
    />
    <ResearchSessionList :sessions="sessions" :selected-session-id="selectedSessionId" @update:selected-session-id="selectedSessionId = $event" />
    <ResearchSessionDetail
      :session="activeSession"
      :action-pending="sessionActionPending"
      :action-error="displaySessionError"
      @delete-collection-session="requestDeleteCollectionSession"
    />
    <ResearchSessionQualityCards :coverage="sessionCoverage" />
    <ResearchSessionCharts :series="sessionCharts" />
    <ResearchSessionCoveragePanel :coverage="sessionCoverage" />
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, watch } from 'vue';

import ResearchCollectionControlCard from '../components/analytics/ResearchCollectionControlCard.vue';
import ResearchCollectionProgressBoard from '../components/analytics/ResearchCollectionProgressBoard.vue';
import ResearchSessionCharts from '../components/analytics/ResearchSessionCharts.vue';
import ResearchSessionCoveragePanel from '../components/analytics/ResearchSessionCoveragePanel.vue';
import ResearchSessionDetail from '../components/analytics/ResearchSessionDetail.vue';
import ResearchSessionList from '../components/analytics/ResearchSessionList.vue';
import ResearchSessionQualityCards from '../components/analytics/ResearchSessionQualityCards.vue';
import { useDataCollectionWorkspace } from './useDataCollectionWorkspace.mjs';

defineOptions({
  name: 'DataCollectionView',
});

const {
  activeSession,
  attachRealtime,
  censusStatus,
  deleteCollectionSession,
  detachRealtime,
  loadCensusStatus,
  loadSessionDetail,
  loadSessions,
  selectedSessionId,
  sessionActionPending,
  sessionActionError,
  sessionCharts,
  sessionCoverage,
  sessionProgress,
  sessions,
  realtimeError,
  startCollectionSession,
  stopCollectionSession,
} = useDataCollectionWorkspace();

const displaySessionError = computed(() => {
  return realtimeError.value || sessionActionError.value;
});

watch(selectedSessionId, (sessionId) => {
  void loadSessionDetail(sessionId);
});

onMounted(() => {
  void loadInitialState();
  attachRealtime();
});

onBeforeUnmount(() => {
  detachRealtime();
});

async function loadInitialState() {
  const previousSelection = selectedSessionId.value;
  await loadSessions();
  if (selectedSessionId.value && selectedSessionId.value === previousSelection) {
    await loadSessionDetail(selectedSessionId.value);
  }
  await loadCensusStatus();
}

function requestDeleteCollectionSession(sessionId) {
  if (!sessionId) {
    return;
  }
  if (typeof window !== 'undefined' && typeof window.confirm === 'function') {
    const confirmed = window.confirm('确认删除该采集会话及其绑定的秒级数据、样本索引和标签吗？');
    if (!confirmed) {
      return;
    }
  }
  void deleteCollectionSession(sessionId);
}
</script>

<style scoped src="../components/analytics/trendResearchPanel.css"></style>
