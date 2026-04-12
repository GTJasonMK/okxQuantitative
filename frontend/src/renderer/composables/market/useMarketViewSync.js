import { nextTick, onActivated, onDeactivated, onMounted, onUnmounted, watch } from 'vue';

const TERMINAL_SYNC_JOB_STATUSES = ['completed', 'failed', 'cancelled'];

export function useMarketViewSync(deps) {
  const {
    api,
    waitForBackend,
    marketWS,
    marketViewActive,
    activeSyncJobs,
    settingsLoaded,
    selectedSymbols,
    activeSymbol,
    holdingSymbols,
    availableSymbols,
    marketInstType,
    currentTimeframe,
    syncMode,
    syncDays,
    syncJobs,
    syncJobsList,
    chartErrors,
    chartLoading,
    loading,
    autoRefresh,
    refreshInterval,
    indicators,
    wsConnected,
    connectionError,
    chartInstances,
    chartRefs,
    candlesData,
    candleVersions,
    tickers,
    realtimePriceMoves,
    recentTradesData,
    recentTradesLoading,
    recentTradesPanelActive,
    orderBookData,
    orderBookLoading,
    orderBookError,
    orderBookPanelActive,
    fillsData,
    recentTradesLooping,
    loadSettings,
    loadHoldingSymbols,
    ensureActiveSymbol,
    loadExecutionPanelData,
    resolveMarketInstId,
    normalizeMonitorSymbol,
    normalizeSymbolList,
    clampSyncDays,
    throttle,
    debouncedSave,
    clearSaveTimer,
    loadChartData,
    refreshActiveChart,
    refreshAllCharts,
    refreshAllTickers,
    initChart,
    updateChart,
    cleanupSymbolState,
    disposeChartInstance,
    clearChartViewportState,
    clearRealtimeChartUpdate,
    clearAllRealtimeChartUpdates,
    clearRealtimePriceMove,
    clearAllRealtimePriceMoves,
    clearRealtimeTickerEvent,
    clearAllRealtimeTickerEvents,
    clearDisplayPriceMoveState,
    applyRealtimeTickerToCandles,
    startRecentTradesPolling,
    stopRecentTradesPolling,
    stopRecentTradesAutoScroll,
    syncRecentTradesAutoScroll,
    startActiveTickerWatchdog,
    stopActiveTickerWatchdog,
    startOrderBookPolling,
    stopOrderBookPolling,
    clearRealtimeTickerSubscriptions,
    syncRealtimeTickerSubscriptions,
    handleWsConnectionChange,
    handleClickOutside,
    flushBufferedTickerForSymbol,
  } = deps;
  let refreshTimer = null;
  let syncJobsTimer = null;
  const handledFinishedSyncJobs = new Set();

  const pruneSyncJobs = () => {
    const finishedJobs = syncJobsList.value.filter(job => TERMINAL_SYNC_JOB_STATUSES.includes(job.status));
    if (finishedJobs.length <= 8) {
      return;
    }

    finishedJobs.slice(8).forEach(job => {
      delete syncJobs[job.task_id];
      handledFinishedSyncJobs.delete(job.task_id);
    });
  };

  const stopSyncJobsPolling = () => {
    if (syncJobsTimer) {
      window.clearInterval(syncJobsTimer);
      syncJobsTimer = null;
    }
  };

  const handleSyncJobFinished = async (job, previousStatus = '') => {
    if (!job?.task_id || handledFinishedSyncJobs.has(job.task_id)) {
      return;
    }
    if (!TERMINAL_SYNC_JOB_STATUSES.includes(job.status) || previousStatus === job.status) {
      return;
    }

    handledFinishedSyncJobs.add(job.task_id);
    const symbol = normalizeMonitorSymbol(job.inst_id);

    if (job.status === 'completed') {
      if (job.inst_type === marketInstType.value && selectedSymbols.value.includes(symbol)) {
        try {
          await loadChartData(symbol);
        } catch (error) {
          console.warn(`同步完成后刷新 ${symbol} 图表失败:`, error);
        }
      }

      try {
        await loadAvailableSymbols();
      } catch (error) {
        console.warn('同步完成后刷新可用币种失败:', error);
      }
      return;
    }

    if (job.inst_type === marketInstType.value && selectedSymbols.value.includes(symbol)) {
      chartErrors[symbol] = job.error || '同步任务失败';
    }
  };

  const applySyncJobUpdate = async (job) => {
    if (!job?.task_id) return;
    const previousJob = syncJobs[job.task_id];
    const previousStatus = previousJob?.status || '';
    syncJobs[job.task_id] = job;
    await handleSyncJobFinished(job, previousStatus);
  };

  const pollSyncJobs = async ({ activeOnly = false } = {}) => {
    try {
      const taskIds = Object.keys(syncJobs);
      const params = taskIds.length > 0
        ? {
            taskIds: taskIds.join(','),
            limit: Math.max(taskIds.length, 20),
          }
        : {
            activeOnly,
            limit: 20,
          };

      const res = await api.getSyncJobs(params);
      if (res.code !== 0 || !Array.isArray(res.data)) {
        return;
      }

      for (const job of res.data) {
        // eslint-disable-next-line no-await-in-loop
        await applySyncJobUpdate(job);
      }

      pruneSyncJobs();

      if (activeSyncJobs.value.length === 0) {
        stopSyncJobsPolling();
      }
    } catch (error) {
      console.warn('轮询后台同步任务失败:', error);
    }
  };

  const startSyncJobsPolling = () => {
    if (syncJobsTimer) {
      return;
    }
    void pollSyncJobs();
    syncJobsTimer = window.setInterval(() => {
      void pollSyncJobs();
    }, 2000);
  };

  const recoverActiveSyncJobs = async () => {
    await pollSyncJobs({ activeOnly: true });
    if (activeSyncJobs.value.length > 0) {
      startSyncJobsPolling();
    }
  };

  const reconcileSelectedSymbols = (nextAvailableSymbols) => {
    const allowedSymbols = new Set(nextAvailableSymbols);
    const removedSymbols = selectedSymbols.value.filter(symbol => !allowedSymbols.has(symbol));

    removedSymbols.forEach(symbol => {
      cleanupSymbolState(symbol);
    });

    selectedSymbols.value = selectedSymbols.value.filter(symbol => allowedSymbols.has(symbol));
    if (selectedSymbols.value.length === 0 && nextAvailableSymbols.length > 0) {
      selectedSymbols.value = [nextAvailableSymbols[0]];
    }
    if (activeSymbol.value && !allowedSymbols.has(activeSymbol.value)) {
      activeSymbol.value = '';
    }
    ensureActiveSymbol();
  };

  // 初始化所有图表
  const initAllCharts = () => {
    if (activeSymbol.value) {
      initChart(activeSymbol.value);
    }
  };

  const resetMarketDisplayState = () => {
    selectedSymbols.value.forEach(symbol => {
      clearRealtimeChartUpdate(symbol);
      clearRealtimePriceMove(symbol);
      clearRealtimeTickerEvent(symbol);
      clearChartViewportState(symbol);
      disposeChartInstance(symbol);
      delete tickers[symbol];
      delete candlesData[symbol];
      delete candleVersions[symbol];
      delete realtimePriceMoves[symbol];
      delete recentTradesData[symbol];
      delete recentTradesLoading[symbol];
      delete orderBookData[symbol];
      delete orderBookLoading[symbol];
      delete orderBookError[symbol];
      delete chartLoading[symbol];
      delete chartErrors[symbol];
      delete fillsData[symbol];
    });
  };

  // 自动刷新控制
  const startAutoRefresh = () => {
    stopAutoRefresh();
    if (autoRefresh.value && refreshInterval.value > 0 && !wsConnected.value) {
      refreshTimer = setInterval(() => {
        refreshAllTickers();
      }, refreshInterval.value * 1000);
    }
  };

  const stopAutoRefresh = () => {
    if (refreshTimer) {
      clearInterval(refreshTimer);
      refreshTimer = null;
    }
  };

  const toggleAutoRefresh = () => {
    if (autoRefresh.value) {
      startAutoRefresh();
    } else {
      stopAutoRefresh();
    }
  };

  const restartAutoRefresh = () => {
    if (autoRefresh.value) {
      startAutoRefresh();
    }
  };

  // 窗口大小变化时调整图表
  // 图表 resize 处理（内部实现）
  const doResize = () => {
    Object.values(chartInstances).forEach(chart => {
      chart?.resize();
    });
    syncRecentTradesAutoScroll({ preservePosition: true });
  };

  // 节流后的 resize 处理函数（每 100ms 最多执行一次）
  const handleResize = throttle(doResize, 100);

  // 检查后端连接
  const checkConnection = async () => {
    try {
      const res = await api.healthCheck();
      if (res.status === 'healthy') {
        connectionError.value = null;

        // 如果尚未初始化（首次连接失败导致中断），执行完整初始化
        if (!isInitialized) {
          await initializeRuntime();
        } else {
          if (runtimeAttached) {
            await syncRealtimeTickerSubscriptions();
            await refreshActiveChart();
            await startRecentTradesPolling();
          } else {
            await activateRuntime();
          }
          await loadExecutionPanelData(activeSymbol.value);
        }
      }
    } catch (error) {
      connectionError.value = '无法连接到后端服务，请确保后端已启动';
    }
  };

  // 加载可用币种
  const loadAvailableSymbols = async () => {
    try {
      const res = await api.getWatchedSymbols();
      const symbols = res.code === 0 && Array.isArray(res.data)
        ? normalizeSymbolList(
            res.data
              .map(item => item.symbol || item)
          )
        : [];
      availableSymbols.value = symbols;
      reconcileSelectedSymbols(symbols);
    } catch (e) {
      console.error('获取关注币种失败:', e);
    }
  };

  // ========== 设置变更监听（自动保存） ==========
  // 监听选中的币种变化（合并设置保存与运行时同步为单个 watcher）
  watch(selectedSymbols, () => {
    if (settingsLoaded.value) debouncedSave();
    ensureActiveSymbol();
    if (isInitialized) {
      syncRealtimeTickerSubscriptions();
    }
  }, { deep: true });

  watch(activeSymbol, async (symbol, previousSymbol) => {
    if (previousSymbol && previousSymbol !== symbol) {
      clearRealtimeChartUpdate(previousSymbol);
      clearDisplayPriceMoveState(previousSymbol);
      disposeChartInstance(previousSymbol);
      delete chartRefs[previousSymbol];
    }

    if (settingsLoaded.value) debouncedSave();
    if (!symbol) {
      stopActiveTickerWatchdog();
      stopRecentTradesPolling();
      stopRecentTradesAutoScroll({ resetPause: true, resetPosition: true });
      recentTradesLooping.value = false;
      return;
    }
    if (!isInitialized) return;

    await syncRealtimeTickerSubscriptions();
    startActiveTickerWatchdog();
    flushBufferedTickerForSymbol(symbol);
    await nextTick();
    initChart(symbol);

    if (candlesData[symbol]?.length > 0) {
      if (tickers[symbol]) {
        applyRealtimeTickerToCandles(symbol, tickers[symbol]);
      }
      updateChart(symbol);
      // LWC 通过 ResizeObserver 自动 resize，ECharts 需手动调用
      if (typeof chartInstances[symbol]?.resize === 'function') {
        chartInstances[symbol].resize();
      }
    } else {
      loadChartData(symbol);
    }

    if (marketViewActive.value && recentTradesPanelActive.value) {
      startRecentTradesPolling();
    } else {
      stopRecentTradesPolling();
      stopRecentTradesAutoScroll({ resetPause: false, resetPosition: true });
    }
    if (marketViewActive.value && orderBookPanelActive.value) {
      startOrderBookPolling();
    } else {
      stopOrderBookPolling();
    }
    syncRecentTradesAutoScroll({ preservePosition: false });
    loadExecutionPanelData(symbol);
  });

  watch(marketInstType, async () => {
    if (settingsLoaded.value) debouncedSave();
    if (!isInitialized) return;

    clearAllRealtimeChartUpdates();
    clearAllRealtimePriceMoves();
    clearAllRealtimeTickerEvents();
    resetMarketDisplayState();
    clearRealtimeTickerSubscriptions();
    stopRecentTradesPolling();
    stopRecentTradesAutoScroll({ resetPause: true });
    stopOrderBookPolling();

    await nextTick();
    initAllCharts();
    await refreshActiveChart();
    await syncRealtimeTickerSubscriptions();
    startActiveTickerWatchdog();
    if (marketViewActive.value) {
      await startRecentTradesPolling();
      await startOrderBookPolling();
    }
    await loadExecutionPanelData(activeSymbol.value);
  });

  watch(recentTradesPanelActive, (active) => {
    if (!isInitialized || !marketViewActive.value || !activeSymbol.value) {
      return;
    }

    if (active) {
      startRecentTradesPolling();
      syncRecentTradesAutoScroll({ preservePosition: false });
      return;
    }

    stopRecentTradesPolling();
    stopRecentTradesAutoScroll({ resetPause: false, resetPosition: true });
  });

  watch(orderBookPanelActive, (active) => {
    if (!isInitialized || !marketViewActive.value || !activeSymbol.value) {
      return;
    }

    if (active) {
      startOrderBookPolling();
      return;
    }

    stopOrderBookPolling();
  });

  // 监听自动刷新设置
  watch([autoRefresh, refreshInterval], () => {
    if (settingsLoaded.value) debouncedSave();
  });

  watch([syncMode, syncDays, currentTimeframe], () => {
    clampSyncDays();
    if (settingsLoaded.value) debouncedSave();
  });

  // 监听指标设置变化
  watch(indicators, () => {
    if (settingsLoaded.value) debouncedSave();
  }, { deep: true });

  // 是否已初始化
  let isInitialized = false
  let runtimeAttached = false
  let initializationPromise = null
  let activationPromise = null

  const bindRuntimeListeners = () => {
    if (runtimeAttached) {
      return;
    }
    runtimeAttached = true;
    window.addEventListener('resize', handleResize);
    document.addEventListener('click', handleClickOutside);
  };

  const unbindRuntimeListeners = () => {
    if (!runtimeAttached) {
      return;
    }
    runtimeAttached = false;
    window.removeEventListener('resize', handleResize);
    document.removeEventListener('click', handleClickOutside);
  };

  const activateRuntime = async (options = {}) => {
    if (!isInitialized) {
      return;
    }

    if (activationPromise) {
      return activationPromise;
    }

    const {
      refreshCharts = true,
      recoverSyncState = true,
      resizeCharts = true,
    } = options;

    activationPromise = (async () => {
      marketViewActive.value = true;

      if (!runtimeAttached) {
        bindRuntimeListeners();
      }

      await syncRealtimeTickerSubscriptions();
      startActiveTickerWatchdog();

      if (recoverSyncState) {
        await recoverActiveSyncJobs();
      }

      if (refreshCharts) {
        await refreshActiveChart();
      }

      await startRecentTradesPolling();
      await startOrderBookPolling();
      startAutoRefresh();

      if (resizeCharts) {
        await nextTick();
        Object.values(chartInstances).forEach(chart => {
          chart?.resize();
        });
      }
    })();

    try {
      await activationPromise;
    } finally {
      activationPromise = null;
    }
  };

  const deactivateRuntime = () => {
    activationPromise = null;
    marketViewActive.value = false
    clearAllRealtimeChartUpdates()
    clearAllRealtimePriceMoves()
    stopRecentTradesPolling()
    stopSyncJobsPolling()
    stopRecentTradesAutoScroll({ resetPause: true })
    stopActiveTickerWatchdog()
    stopOrderBookPolling()
    clearRealtimeTickerSubscriptions()
    stopAutoRefresh();
    unbindRuntimeListeners();
  };

  const initializeRuntime = async () => {
    if (isInitialized) {
      return;
    }

    if (initializationPromise) {
      return initializationPromise;
    }

    initializationPromise = (async () => {
      await loadSettings();
      await loadHoldingSymbols();
      ensureActiveSymbol();
      await loadAvailableSymbols();
      await recoverActiveSyncJobs();
      await nextTick();
      initAllCharts();
      await refreshActiveChart();
      isInitialized = true;
      await activateRuntime({
        refreshCharts: false,
        recoverSyncState: false,
        resizeCharts: false,
      });
      await loadExecutionPanelData(activeSymbol.value);
    })();

    try {
      await initializationPromise;
    } finally {
      initializationPromise = null;
    }
  };

  // 生命周期
  onMounted(async () => {
    marketWS.addConnectionListener(handleWsConnectionChange);

    // 等待后端服务启动（最多重试 10 次，每次间隔 1 秒）
    const connected = await waitForBackend(10, 1000);
    if (!connected) {
      connectionError.value = '无法连接到后端服务，请确保后端已启动 (http://127.0.0.1:8000)';
      return; // 连接失败，中断初始化
    }

    connectionError.value = null;
    await initializeRuntime();
  });

  // keep-alive 激活时调用
  onActivated(async () => {
    if (!isInitialized) return

    await loadAvailableSymbols();
    await activateRuntime();
  });

  // keep-alive 停用时调用
  onDeactivated(() => {
    deactivateRuntime();
  });

  onUnmounted(() => {
    deactivateRuntime();
    clearAllRealtimeTickerEvents();
    clearSaveTimer();
    marketWS.removeConnectionListener(handleWsConnectionChange);
    Object.keys(chartInstances).forEach(disposeChartInstance);
  });

  return {
    startSyncJobsPolling,
    startAutoRefresh,
    toggleAutoRefresh,
    restartAutoRefresh,
    checkConnection,
    loadAvailableSymbols,
  };
}
