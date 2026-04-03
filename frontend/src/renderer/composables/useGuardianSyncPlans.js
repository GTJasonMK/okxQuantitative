import { computed, ref } from 'vue';

import { api } from '../services/api';

const DEFAULT_TIMEFRAMES = ['1m', '5m', '1H', '4H', '1D'];
const TIMEFRAME_ORDER = {
  '1m': 1,
  '3m': 2,
  '5m': 3,
  '15m': 4,
  '30m': 5,
  '1H': 6,
  '2H': 7,
  '4H': 8,
  '6H': 9,
  '12H': 10,
  '1D': 11,
  '1W': 12,
  '1M': 13,
};

const normalizeTimeframe = (value) => String(value || '').trim();

export const sortGuardianTimeframes = (values) => (
  [...new Set((values || []).map(normalizeTimeframe).filter(Boolean))]
    .sort((left, right) => {
      const leftOrder = TIMEFRAME_ORDER[left] || 999;
      const rightOrder = TIMEFRAME_ORDER[right] || 999;
      if (leftOrder !== rightOrder) {
        return leftOrder - rightOrder;
      }
      return left.localeCompare(right, 'en');
    })
);

export const useGuardianSyncPlans = () => {
  const plans = ref([]);
  const loading = ref(false);
  const error = ref('');
  let loadPromise = null;

  const enabledPlans = computed(() => (
    plans.value
      .filter((plan) => plan.enabled !== false && plan.timeframe)
      .slice()
      .sort((left, right) => {
        const leftTimeframe = normalizeTimeframe(left.timeframe);
        const rightTimeframe = normalizeTimeframe(right.timeframe);
        const leftOrder = TIMEFRAME_ORDER[leftTimeframe] || 999;
        const rightOrder = TIMEFRAME_ORDER[rightTimeframe] || 999;
        if (leftOrder !== rightOrder) {
          return leftOrder - rightOrder;
        }
        return leftTimeframe.localeCompare(rightTimeframe, 'en');
      })
  ));

  const enabledTimeframes = computed(() => {
    const timeframes = sortGuardianTimeframes(
      enabledPlans.value.map((plan) => String(plan.timeframe || '').trim()).filter(Boolean),
    );
    return timeframes.length > 0 ? timeframes : DEFAULT_TIMEFRAMES;
  });

  const planMap = computed(() => {
    const map = new Map();
    enabledPlans.value.forEach((plan) => {
      const timeframe = String(plan.timeframe || '').trim();
      if (timeframe) {
        map.set(timeframe, {
          timeframe,
          archive_mode: plan.archive_mode || 'rolling',
          bootstrap_days: Number(plan.bootstrap_days) || 30,
          enabled: plan.enabled !== false,
        });
      }
    });
    if (map.size === 0) {
      DEFAULT_TIMEFRAMES.forEach((timeframe) => {
        map.set(timeframe, {
          timeframe,
          archive_mode: timeframe === '1D' ? 'full' : 'rolling',
          bootstrap_days: timeframe === '1m' ? 7 : 30,
          enabled: true,
        });
      });
    }
    return map;
  });

  const loadPlans = async (force = false) => {
    if (!force && plans.value.length > 0) {
      return plans.value;
    }
    if (loadPromise) {
      return loadPromise;
    }

    loading.value = true;
    error.value = '';
    loadPromise = (async () => {
      try {
        const response = await api.getDataGuardianConfig();
        const nextPlans = Array.isArray(response?.data?.settings?.plans)
          ? response.data.settings.plans
          : [];
        plans.value = nextPlans;
        return plans.value;
      } catch (requestError) {
        error.value = requestError?.response?.data?.detail || requestError?.message || '读取数据守护器配置失败';
        plans.value = [];
        return plans.value;
      } finally {
        loading.value = false;
        loadPromise = null;
      }
    })();

    return loadPromise;
  };

  return {
    plans,
    planMap,
    enabledPlans,
    enabledTimeframes,
    loading,
    error,
    loadPlans,
  };
};
