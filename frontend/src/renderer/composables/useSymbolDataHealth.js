import { computed, ref, unref, watch } from 'vue';

import { api } from '../services/api';

const STATUS_LABELS = {
  healthy: '良好',
  degraded: '待补齐',
  stale: '陈旧',
  missing: '未入库',
};

const normalizeSymbol = (value) => {
  if (typeof value !== 'string') {
    return '';
  }
  const normalized = value.trim().toUpperCase();
  if (!normalized) {
    return '';
  }
  return normalized.endsWith('-SWAP') ? normalized.slice(0, -5) : normalized;
};

const normalizeInstType = (value) => {
  const normalized = String(value || '').trim().toUpperCase();
  return normalized === 'SWAP' ? 'SWAP' : 'SPOT';
};

const toNumber = (value, fallback = 0) => {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
};

const createEmptyHealthRow = (symbol) => ({
  symbol,
  status: 'missing',
  health_score: 0,
  coverage_ratio: 0,
  missing_timeframes: [],
  watched: false,
  orphan: false,
  has_local_data: false,
  markets: {},
});

export const useSymbolDataHealth = ({
  symbolRef,
  instTypeRef,
}) => {
  const healthRow = ref(null);
  const healthLoading = ref(false);
  const healthError = ref('');
  const lastLoadedKey = ref('');
  const requestVersion = ref(0);

  const normalizedSymbol = computed(() => normalizeSymbol(unref(symbolRef)));
  const normalizedInstType = computed(() => normalizeInstType(unref(instTypeRef)));

  const selectedMarketHealth = computed(() => {
    const row = healthRow.value;
    if (!row || typeof row !== 'object') {
      return null;
    }
    const markets = row.markets && typeof row.markets === 'object' ? row.markets : {};
    return markets[normalizedInstType.value] || null;
  });

  const selectedMissingTimeframes = computed(() => {
    const missing = healthRow.value?.missing_timeframes;
    return Array.isArray(missing) ? missing : [];
  });

  const healthStatus = computed(() => {
    if (healthRow.value?.has_local_data && !selectedMarketHealth.value) {
      return 'missing';
    }
    const raw = String(healthRow.value?.status || 'missing').trim().toLowerCase();
    return STATUS_LABELS[raw] ? raw : 'missing';
  });

  const healthStatusLabel = computed(() => STATUS_LABELS[healthStatus.value] || STATUS_LABELS.missing);
  const healthScore = computed(() => Math.round(toNumber(healthRow.value?.health_score, 0)));

  const healthBadgeText = computed(() => {
    if (!normalizedSymbol.value) {
      return '数据 --';
    }
    if (healthLoading.value && !healthRow.value) {
      return '数据检查中';
    }
    if (healthError.value) {
      return '数据异常';
    }
    if (!selectedMarketHealth.value && healthRow.value?.has_local_data) {
      return `${normalizedInstType.value}缺失`;
    }
    const missing = selectedMissingTimeframes.value;
    if (missing.length > 0) {
      const preview = missing.slice(0, 2).join('/');
      return `缺 ${preview}${missing.length > 2 ? '+' : ''}`;
    }
    return `数据${healthStatusLabel.value}`;
  });

  const healthSummaryText = computed(() => {
    if (!normalizedSymbol.value) {
      return '未选择币种';
    }
    if (healthLoading.value && !healthRow.value) {
      return '正在读取本地数据健康状态';
    }
    if (healthError.value) {
      return healthError.value;
    }
    if (!healthRow.value) {
      return '本地数据库暂无该币种数据';
    }

    const summary = [`${healthStatusLabel.value} ${healthScore.value}`];
    const market = selectedMarketHealth.value;
    if (market) {
      const timeframeCount = Array.isArray(market.timeframes) ? market.timeframes.length : 0;
      summary.push(`${normalizedInstType.value} ${timeframeCount} 个周期`);
      if (selectedMissingTimeframes.value.length > 0) {
        summary.push(`缺 ${selectedMissingTimeframes.value.join('/')}`);
      } else {
        summary.push('关键周期已覆盖');
      }
    } else {
      summary.push(`${normalizedInstType.value} 未入库`);
    }
    return summary.join(' · ');
  });

  const resetHealthState = () => {
    healthRow.value = null;
    healthLoading.value = false;
    healthError.value = '';
    lastLoadedKey.value = '';
  };

  const loadHealth = async (force = false) => {
    const symbol = normalizedSymbol.value;
    const instType = normalizedInstType.value;
    if (!symbol) {
      resetHealthState();
      return null;
    }

    const queryKey = `${symbol}:${instType}`;
    if (!force && lastLoadedKey.value === queryKey && healthRow.value && !healthError.value) {
      return healthRow.value;
    }

    const currentVersion = requestVersion.value + 1;
    requestVersion.value = currentVersion;
    healthLoading.value = true;
    healthError.value = '';

    try {
      const response = await api.getMarketDataHealth({
        symbol,
        includeOrphans: true,
      });
      if (currentVersion !== requestVersion.value) {
        return null;
      }

      const payload = response?.data || {};
      const rows = Array.isArray(payload.rows) ? payload.rows : [];
      const matchedRow = rows.find((item) => normalizeSymbol(item?.symbol) === symbol);
      healthRow.value = matchedRow || createEmptyHealthRow(symbol);
      lastLoadedKey.value = queryKey;
      return healthRow.value;
    } catch (error) {
      if (currentVersion !== requestVersion.value) {
        return null;
      }
      healthRow.value = createEmptyHealthRow(symbol);
      healthError.value = error?.response?.data?.detail || error?.message || '读取数据健康状态失败';
      return null;
    } finally {
      if (currentVersion === requestVersion.value) {
        healthLoading.value = false;
      }
    }
  };

  watch(
    [normalizedSymbol, normalizedInstType],
    ([symbol]) => {
      if (!symbol) {
        resetHealthState();
        return;
      }
      void loadHealth(true);
    },
    { immediate: true },
  );

  return {
    healthRow,
    healthLoading,
    healthError,
    healthStatus,
    healthStatusLabel,
    healthScore,
    healthBadgeText,
    healthSummaryText,
    selectedMarketHealth,
    selectedMissingTimeframes,
    loadHealth,
  };
};
