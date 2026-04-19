<template>
  <div class="guardian-view">
    <AnalyticsDataInventoryCard mode="guardian-only" />
  </div>
</template>

<script setup>
import AnalyticsDataInventoryCard from '../components/analytics/AnalyticsDataInventoryCard.vue';

defineOptions({
  name: 'GuardianView',
});
</script>

<style scoped>
.guardian-view {
  height: 100%;
  padding: 14px 6px;
  overflow: auto;
}
</style>
