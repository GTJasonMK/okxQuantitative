<template>
  <section class="trend-diagnostics-shell">
    <div v-if="error" class="trend-diagnostics-inline-error">{{ error }}</div>
    <TrendProgressOverviewStrip :items="dashboard.overviewItems" />
    <div class="trend-diagnostics-main">
      <TrendProgressConclusionCard :conclusion="dashboard.conclusion" :loading="loading" />
      <TrendProgressPipeline :steps="dashboard.pipelineSteps" />
    </div>
    <TrendProgressEvidenceCards :cards="dashboard.evidenceCards" />
    <TrendDiagnosticsTimeline :items="dashboard.timelineItems" :loading="loading" />
    <TrendDiagnosticsDetails
      :details="state.details"
      :emitted-at="state.emittedAt"
      :global-health="state.globalHealth"
      :instrument-health="state.instrumentHealth"
    />
  </section>
</template>

<script setup>
import { computed } from 'vue';

import TrendDiagnosticsDetails from './TrendDiagnosticsDetails.vue';
import TrendDiagnosticsTimeline from './TrendDiagnosticsTimeline.vue';
import TrendProgressConclusionCard from './TrendProgressConclusionCard.vue';
import TrendProgressEvidenceCards from './TrendProgressEvidenceCards.vue';
import TrendProgressOverviewStrip from './TrendProgressOverviewStrip.vue';
import TrendProgressPipeline from './TrendProgressPipeline.vue';
import { buildTrendProgressDashboardModel } from './trendProgressDashboardViewModel.mjs';

const props = defineProps({
  error: {
    type: String,
    default: '',
  },
  loading: {
    type: Boolean,
    default: false,
  },
  state: {
    type: Object,
    default: () => ({
      selectedInstId: '',
      instruments: [],
      globalHealth: {},
      instrumentHealth: {},
      timeline: [],
      details: {},
    }),
  },
  processSummary: {
    type: Object,
    default: () => ({}),
  },
  selectedProcessInstrument: {
    type: Object,
    default: () => ({}),
  },
});

const dashboard = computed(() => {
  return buildTrendProgressDashboardModel({
    processSummary: props.processSummary,
    processInstrument: props.selectedProcessInstrument,
    diagnosticsState: props.state,
    loading: props.loading,
  });
});
</script>

<style scoped src="./trendDiagnostics.css"></style>
