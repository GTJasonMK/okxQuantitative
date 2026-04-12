<template>
  <section class="trend-diagnostics-shell">
    <div v-if="error" class="trend-diagnostics-inline-error">{{ error }}</div>
    <div class="trend-diagnostics-main">
      <TrendDiagnosticsHealthSummary
        :emitted-at="state.emittedAt"
        :global-health="state.globalHealth"
        :instrument-health="state.instrumentHealth"
        :loading="loading"
      />
      <TrendDiagnosticsTimeline :items="state.timeline" :loading="loading" />
    </div>
    <TrendDiagnosticsDetails
      :details="state.details"
      :emitted-at="state.emittedAt"
      :global-health="state.globalHealth"
      :instrument-health="state.instrumentHealth"
    />
  </section>
</template>

<script setup>
import TrendDiagnosticsDetails from './TrendDiagnosticsDetails.vue';
import TrendDiagnosticsHealthSummary from './TrendDiagnosticsHealthSummary.vue';
import TrendDiagnosticsTimeline from './TrendDiagnosticsTimeline.vue';

defineProps({
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
});
</script>

<style scoped src="./trendDiagnostics.css"></style>
