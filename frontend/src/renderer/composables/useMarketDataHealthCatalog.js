import { computed, ref } from 'vue';

import { api } from '../services/api';
import { normalizeDataHealthSymbol } from '../utils/dataHealth';

export const useMarketDataHealthCatalog = () => {
  const rows = ref([]);
  const loading = ref(false);
  const error = ref('');
  const loadedKey = ref('');
  let loadPromise = null;

  const rowMap = computed(() => {
    const map = new Map();
    rows.value.forEach((row) => {
      const symbol = normalizeDataHealthSymbol(row?.symbol);
      if (symbol) {
        map.set(symbol, row);
      }
    });
    return map;
  });

  const loadCatalog = async (options = {}) => {
    const includeOrphans = options.includeOrphans ?? true;
    const force = options.force === true;
    const requestKey = includeOrphans ? 'with-orphans' : 'watchlist-only';

    if (!force && loadedKey.value === requestKey && rows.value.length > 0) {
      return rows.value;
    }
    if (loadPromise) {
      return loadPromise;
    }

    loading.value = true;
    error.value = '';
    loadPromise = (async () => {
      try {
        const response = await api.getMarketDataHealth({
          includeOrphans,
        });
        const payload = response?.data || {};
        rows.value = Array.isArray(payload.rows) ? payload.rows : [];
        loadedKey.value = requestKey;
        return rows.value;
      } catch (requestError) {
        error.value = requestError?.response?.data?.detail || requestError?.message || '读取数据健康目录失败';
        rows.value = [];
        return rows.value;
      } finally {
        loading.value = false;
        loadPromise = null;
      }
    })();

    return loadPromise;
  };

  return {
    rows,
    rowMap,
    loading,
    error,
    loadCatalog,
  };
};
