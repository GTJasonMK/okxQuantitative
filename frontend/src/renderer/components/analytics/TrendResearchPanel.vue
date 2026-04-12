<template>
  <section class="card trend-research-card">
    <div class="section-header">
      <div>
        <h3 class="card-title">趋势研究</h3>
        <p class="section-desc">按任务查看趋势结论、因子变化、训练状态与过程诊断。</p>
      </div>
      <div class="toolbar">
        <select v-model.number="selectedLookbackSeconds" class="input trend-lookback-select">
          <option v-for="option in TREND_LOOKBACK_OPTIONS" :key="option.seconds" :value="option.seconds">
            {{ option.label }}
          </option>
        </select>
        <button class="btn btn-secondary btn-sm" @click="loadSharedData" :disabled="loading">
          {{ loading ? '刷新中...' : '刷新' }}
        </button>
      </div>
    </div>

    <div class="trend-research-content">
      <div v-if="error" class="error-message">{{ error }}</div>
      <div v-if="loading && rows.length === 0" class="empty-state">加载中...</div>
      <div v-else-if="hasRenderableWorkspace" class="trend-research-layout">
        <div
          v-if="switcherRows.length > 0"
          class="trend-instrument-switcher"
          role="tablist"
          aria-label="趋势研究合约切换"
        >
          <button
            v-for="row in switcherRows"
            :key="row.instId"
            type="button"
            class="trend-switcher-chip"
            :class="{ 'is-active': selectedInstId === row.instId }"
            :aria-selected="selectedInstId === row.instId"
            @click="selectInstrument(row.instId)"
          >
            <strong class="trend-switcher-inst">{{ row.instId }}</strong>
            <span class="trend-state-badge" :class="`tone-${row.trendStateTone}`">{{ row.trendStateLabel }}</span>
            <span class="trend-switcher-confidence">{{ row.confidencePct }}</span>
          </button>
        </div>

        <TrendResearchSubnav v-model="activeTrendPage" />

        <div class="trend-subpage-host">
          <TrendResearchOverviewPage
            v-if="activeTrendPage === 'overview'"
            :model-status="modelStatus"
            :panel-state="panelState"
            :selected-process-instrument="selectedProcessInstrument"
            :selected-trend-row="selectedTrendRow"
          />
          <TrendResearchFactorsPage
            v-else-if="activeTrendPage === 'factors'"
            :inst-id="selectedInstId"
            :is-active="activeTrendPage === 'factors'"
            :lookback-label="lookbackLabel"
            :lookback-seconds="selectedLookbackSeconds"
            :refresh-token="refreshVersion"
            :selected-row="selectedTrendRow"
          />
          <TrendResearchTrainingPage
            v-else-if="activeTrendPage === 'training'"
            :key="`training-${refreshVersion}`"
            :is-active="activeTrendPage === 'training'"
            :lookback-seconds="selectedLookbackSeconds"
            :model-status="modelStatus"
            :training-run-payload="trainingRunPayload"
          />
          <TrendResearchDiagnosticsPage
            v-else-if="activeTrendPage === 'diagnostics'"
            :inst-id="selectedInstId"
            @select-inst="selectInstrument"
          />
          <div v-else class="trend-subpage-placeholder">
            <strong>{{ activePageTitle }}</strong>
            <p>子页面拆分进行中，当前先保留共享壳组件与导航。</p>
          </div>
        </div>
      </div>
      <div
        v-else
        class="empty-state"
        :class="panelState.tone === 'warning' ? 'trend-empty-warning' : 'trend-empty-info'"
      >
        <TrendResearchModelStatus class="trend-summary-model" :model-status="modelStatus" />
        <strong>{{ panelState.title || '暂无趋势研究数据' }}</strong>
        <p>{{ panelState.description || '后端暂时没有可展示的趋势研究结果。' }}</p>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue';

import TrendResearchDiagnosticsPage from './TrendResearchDiagnosticsPage.vue';
import TrendResearchFactorsPage from './TrendResearchFactorsPage.vue';
import TrendResearchModelStatus from './TrendResearchModelStatus.vue';
import TrendResearchOverviewPage from './TrendResearchOverviewPage.vue';
import TrendResearchSubnav from './TrendResearchSubnav.vue';
import TrendResearchTrainingPage from './TrendResearchTrainingPage.vue';
import { TREND_LOOKBACK_OPTIONS } from './trendResearchLookback.mjs';
import { useTrendResearchWorkspace } from './useTrendResearchWorkspace.mjs';

const workspace = useTrendResearchWorkspace();
const {
  activeTrendPage,
  error,
  loading,
  loadSharedData,
  lookbackLabel,
  modelStatus,
  panelState,
  recentProcess,
  refreshVersion,
  rows,
  selectedInstId,
  selectedProcessInstrument,
  selectedLookbackSeconds,
  selectedTrendRow,
  selectInstrument,
  trainingRunPayload,
} = workspace;

const PAGE_TITLES = Object.freeze({
  overview: '结论总览',
  factors: '因子分析',
  training: '训练模型',
  diagnostics: '过程诊断',
});

const activePageTitle = computed(() => PAGE_TITLES[activeTrendPage.value] || '趋势研究');
const hasRenderableWorkspace = computed(() => {
  return activeTrendPage.value === 'diagnostics'
    || rows.value.length > 0
    || recentProcess.value.instruments.length > 0
    || recentProcess.value.summaryCards.length > 0
    || !!trainingRunPayload.value;
});
const switcherRows = computed(() => {
  if (rows.value.length > 0) {
    return rows.value;
  }
  return recentProcess.value.instruments.map((item) => ({
    instId: item.instId,
    trendStateLabel: item.displayState,
    trendStateTone: 'neutral',
    confidencePct: '--',
  }));
});
</script>

<style scoped src="./trendResearchPanel.css"></style>
