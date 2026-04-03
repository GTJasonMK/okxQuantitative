import { onActivated, onDeactivated, onMounted, onUnmounted, watch } from 'vue';

export function useTradingViewRuntime(deps) {
  const {
    api,
    marketWS,
    props,
    appStore,
    selectedSymbol,
    availableSymbols,
    settingsLoaded,
    symbolDropdownOpen,
    symbolSearch,
    newSymbolInput,
    holdingSymbols,
    loading,
    orderLoading,
    cancelingOrderId,
    currentPrice,
    priceLoading,
    wsConnected,
    maxTradeSize,
    showConfirmDialog,
    pendingOrder,
    showContractConfirmDialog,
    pendingContractOrder,
    currentSide,
    tradeType,
    contractSide,
    contractSettings,
    contractPosMode,
    contractPositions,
    tradingStatus,
    accountBalance,
    spotHoldings,
    totalValueUsdt,
    totalValueWithCost,
    totalCostUsdt,
    totalFeeUsdt,
    totalPnlUsdt,
    totalPnlPercent,
    holdingsBase,
    holdingPrices,
    syncingFills,
    showEditCostDialog,
    editingCcy,
    editCostValue,
    savingCost,
    pendingOrders,
    fills,
    orderResult,
    orderForm,
    defaultModeText,
    isModeLocked,
    buildModeLockMessage,
    getErrorDetail,
    recalcHoldings,
    isHoldingSymbol,
    estimatedAmount,
    priceChange24h,
    contractInstId,
    baseCurrency,
    contractSideClass,
    contractSideText,
  } = deps;

  // ========== 方法 ==========

  // ========== 方法 ==========

  // 格式化数字（至少6位小数）
  const formatNumber = (val) => {
    const num = parseFloat(val)
    if (isNaN(num)) return '0.000000'
    if (Math.abs(num) >= 1000) return num.toLocaleString('en-US', { minimumFractionDigits: 6, maximumFractionDigits: 6 })
    return num.toFixed(6)
  }

  // 格式化价格（至少6位小数）
  const formatPrice = (val) => {
    const num = parseFloat(val)
    if (isNaN(num) || num === 0) return '-'
    return num.toLocaleString('en-US', { minimumFractionDigits: 6, maximumFractionDigits: 6 })
  }

  // 格式化百分比
  const formatPercent = (val) => {
    const num = parseFloat(val) * 100
    if (isNaN(num)) return '0.00%'
    return (num >= 0 ? '+' : '') + num.toFixed(2) + '%'
  }

  // 格式化时间
  const formatTime = (ts) => {
    if (!ts) return '-'
    const date = new Date(parseInt(ts))
    return date.toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  }

  // 获取盈亏样式类
  const getPlClass = (val) => {
    const num = parseFloat(val)
    if (num > 0) return 'profit'
    if (num < 0) return 'loss'
    return ''
  }

  // 获取涨跌样式类
  const getChangeClass = (val) => {
    if (val === '-' || val === '0') return ''
    const num = parseFloat(val)
    if (num > 0) return 'profit'
    if (num < 0) return 'loss'
    return ''
  }

  // 格式化涨跌幅
  const formatChange = (val) => {
    if (val === '-' || val === '0') return '-'
    const num = parseFloat(val)
    if (isNaN(num)) return '-'
    return (num >= 0 ? '+' : '') + num.toFixed(2) + '%'
  }

  // 获取订单状态文本
  const getOrderStateText = (state) => {
    const stateMap = {
      'live': '等待成交',
      'partially_filled': '部分成交',
      'filled': '完全成交',
      'canceled': '已撤销',
      'mmp_canceled': '做市商撤销'
    }
    return stateMap[state] || state
  }

  // 切换交易对下拉框
  const toggleSymbolDropdown = () => {
    symbolDropdownOpen.value = !symbolDropdownOpen.value
  }

  // 选择交易对
  const selectSymbol = (symbol) => {
    selectedSymbol.value = symbol
    symbolDropdownOpen.value = false
    symbolSearch.value = ''
  }

  // 添加自定义交易对
  const addCustomSymbol = () => {
    let symbol = newSymbolInput.value.trim().toUpperCase()
    if (!symbol) return

    // 自动补全 -USDT 后缀
    if (!symbol.includes('-')) {
      symbol = `${symbol}-USDT`
    }

    // 检查是否已存在
    if (availableSymbols.value.includes(symbol)) {
      newSymbolInput.value = ''
      return
    }

    availableSymbols.value.push(symbol)
    newSymbolInput.value = ''
  }

  // 删除交易对（持仓币种不可删除）
  const removeSymbol = (symbol) => {
    if (isHoldingSymbol(symbol)) return

    const idx = availableSymbols.value.indexOf(symbol)
    if (idx > -1) {
      availableSymbols.value.splice(idx, 1)
    }

    // 如果删除的是当前选中的，切换到第一个
    if (selectedSymbol.value === symbol && availableSymbols.value.length > 0) {
      selectedSymbol.value = availableSymbols.value[0]
    }
  }

  const getMarketInstType = (type = tradeType.value) => {
    if (type === 'swap') return 'SWAP'
    if (type === 'futures') return 'FUTURES'
    return 'SPOT'
  }

  const getMarketInstId = (symbol = selectedSymbol.value, type = tradeType.value) => {
    if (!symbol) return ''
    if (type === 'swap') return `${symbol}-SWAP`
    if (type === 'futures') return ''
    return symbol
  }

  // 获取当前交易对价格
  const fetchCurrentPrice = async () => {
    const instId = getMarketInstId()
    if (!instId) {
      currentPrice.value = null
      return
    }

    priceLoading.value = true
    try {
      const res = await api.getTicker(instId, {
        instType: getMarketInstType(),
      })
      if (res && res.data) {
        // 后端返回 snake_case 字段，转换为与 WebSocket 一致的 camelCase 格式
        const d = res.data
        currentPrice.value = {
          last: d.last,
          askPx: d.ask_px,
          bidPx: d.bid_px,
          open24h: d.open_24h,
          high24h: d.high_24h,
          low24h: d.low_24h,
          vol24h: d.vol_24h,
          change24h: d.change_24h,
          timestamp: d.timestamp,
        }
      }
    } catch (e) {
      console.error('获取价格失败:', e)
      currentPrice.value = null
    } finally {
      priceLoading.value = false
    }
  }

  // 获取最大可交易数量
  const fetchMaxSize = async () => {
    try {
      if (tradeType.value === 'spot') {
        // 现货
        const res = await api.getMaxSize(selectedSymbol.value, 'cash', props.mode)
        maxTradeSize.maxBuy = res.max_buy || '0'
        maxTradeSize.maxSell = res.max_sell || '0'
      } else {
        // 合约（axios拦截器已返回response.data，res即后端JSON）
        const res = await api.getContractMaxSize(contractInstId.value, contractSettings.marginMode, props.mode)
        maxTradeSize.maxBuy = res.max_buy || '0'
        maxTradeSize.maxSell = res.max_sell || '0'
      }
    } catch (e) {
      console.error('获取最大数量失败:', e)
      maxTradeSize.maxBuy = '0'
      maxTradeSize.maxSell = '0'
    }
  }

  // 快速设置数量百分比
  const setQuickAmount = (percent) => {
    if (tradeType.value !== 'spot') {
      // 合约模式下根据方向设置
      const isLong = contractSide.value === 'open_long' || contractSide.value === 'close_short'
      const max = parseFloat(isLong ? maxTradeSize.maxBuy : maxTradeSize.maxSell) || 0
      orderForm.size = max > 0 ? Math.floor(max * percent).toString() : ''
      return
    }
    // 现货模式：根据当前方向计算数量
    if (currentSide.value === 'buy') {
      const maxBuy = parseFloat(maxTradeSize.maxBuy) || 0
      orderForm.size = maxBuy > 0 ? (maxBuy * percent).toFixed(6) : ''
    } else {
      const maxSell = parseFloat(maxTradeSize.maxSell) || 0
      orderForm.size = maxSell > 0 ? (maxSell * percent).toFixed(6) : ''
    }
  }

  // 刷新所有数据
  const refreshAll = async () => {
    loading.value = true
    try {
      await Promise.all([
        fetchTradingStatus(),
        fetchAccountBalance(),
        fetchSpotHoldings(),
        fetchPendingOrders(),
        fetchFills()
      ])
    } finally {
      loading.value = false
    }
  }

  // 获取交易状态
  const fetchTradingStatus = async () => {
    try {
      const res = await api.getTradingStatus(props.mode)
      Object.assign(tradingStatus, res)
    } catch (e) {
      console.error('获取交易状态失败:', e)
    }
  }

  // 获取账户余额
  const fetchAccountBalance = async () => {
    try {
      const res = await api.getAccount(props.mode)
      accountBalance.total_equity = res.total_equity || '0'
      accountBalance.details = res.details || []
    } catch (e) {
      console.error('获取账户余额失败:', e)
    }
  }

  // 持仓币种的 WebSocket 价格回调
  const onHoldingPriceUpdate = (data) => {
    // data.instId 格式为 'BTC-USDT'，提取币种
    const ccy = data.instId.split('-')[0]
    const price = parseFloat(data.last) || 0
    if (price > 0) {
      holdingPrices[ccy] = price
      // 价格更新后重新计算持仓
      recalcHoldings()
    }
  }

  // 订阅所有持仓币种的价格
  const subscribeHoldingPrices = () => {
    if (!marketWS.isConnected) return

    for (const h of holdingsBase.value) {
      if (!h.is_stablecoin) {
        const instId = `${h.ccy}-USDT`
        // 避免重复订阅当前选中的交易对
        if (instId !== selectedSymbol.value) {
          marketWS.subscribe(instId, onHoldingPriceUpdate)
        }
      }
    }
  }

  // 取消订阅持仓币种价格
  const unsubscribeHoldingPrices = () => {
    if (!marketWS.isConnected) return

    for (const h of holdingsBase.value) {
      if (!h.is_stablecoin) {
        const instId = `${h.ccy}-USDT`
        if (instId !== selectedSymbol.value) {
          marketWS.unsubscribe(instId, onHoldingPriceUpdate)
        }
      }
    }
  }

  // 获取现货持仓（优化版：使用轻量API + WebSocket实时价格）
  const fetchSpotHoldings = async () => {
    try {
      // 使用轻量版 API（不查行情）
      const res = await api.getHoldingsBase(props.mode)
      const oldHoldings = holdingsBase.value

      holdingsBase.value = res.holdings || []

      // 如果持仓币种变化，重新订阅 WebSocket
      const oldCcys = new Set(oldHoldings.filter(h => !h.is_stablecoin).map(h => h.ccy))
      const newCcys = new Set(holdingsBase.value.filter(h => !h.is_stablecoin).map(h => h.ccy))
      const hasChange = oldCcys.size !== newCcys.size || [...newCcys].some(c => !oldCcys.has(c))

      if (hasChange && marketWS.isConnected) {
        // 取消旧订阅
        for (const ccy of oldCcys) {
          const instId = `${ccy}-USDT`
          if (instId !== selectedSymbol.value) {
            marketWS.unsubscribe(instId, onHoldingPriceUpdate)
          }
        }
        // 添加新订阅
        subscribeHoldingPrices()
      }

      // 立即计算一次（使用已缓存的价格）
      recalcHoldings()
    } catch (e) {
      console.error('获取现货持仓失败:', e)
      holdingsBase.value = []
      spotHoldings.value = []
      totalValueUsdt.value = '0'
      totalValueWithCost.value = '0'
      totalCostUsdt.value = '0'
      totalFeeUsdt.value = '0'
      totalPnlUsdt.value = '0'
      totalPnlPercent.value = '0'
    }
  }

  // 获取当前委托（根据交易类型请求对应的inst_type）
  const fetchPendingOrders = async () => {
    try {
      const instType = getMarketInstType()
      const res = await api.getOrders(instType, '', props.mode)
      pendingOrders.value = res.orders || []
    } catch (e) {
      console.error('获取委托失败:', e)
      pendingOrders.value = []
    }
  }

  // 获取成交记录（根据交易类型请求对应的inst_type）
  const fetchFills = async () => {
    try {
      const instType = getMarketInstType()
      const res = await api.getFills(instType, '', 50, props.mode)
      fills.value = res.fills || []
    } catch (e) {
      console.error('获取成交记录失败:', e)
      fills.value = []
    }
  }

  // 下单
  const placeOrder = async (side) => {
    if (isModeLocked.value) {
      orderResult.value = { success: false, message: buildModeLockMessage() }
      return
    }
    if (!orderForm.size) {
      orderResult.value = { success: false, message: '请输入数量' }
      return
    }

    if (orderForm.order_type === 'limit' && !orderForm.price) {
      orderResult.value = { success: false, message: '限价单请输入价格' }
      return
    }

    orderLoading.value = true
    orderResult.value = null

    try {
      const res = await api.placeOrder({
        inst_id: selectedSymbol.value,
        side: side,
        order_type: orderForm.order_type,
        size: orderForm.size,
        price: orderForm.price || '',
        mode: props.mode
      })

      if (res.success) {
        orderResult.value = {
          success: true,
          message: `${side === 'buy' ? '买入' : '卖出'}订单已提交，订单号: ${res.order_id}`
        }
        // 清空表单
        orderForm.size = ''
        orderForm.price = ''
        // WebSocket 会自动推送订单和账户更新
        // 备用：如果 WebSocket 未连接，手动刷新
        if (!wsConnected.value) {
          setTimeout(() => {
            fetchPendingOrders()
            fetchAccountBalance()
          }, 1000)
        }
      } else {
        orderResult.value = {
          success: false,
          message: `下单失败: ${res.error_message || '未知错误'}`
        }
      }
    } catch (e) {
      orderResult.value = {
        success: false,
        message: `下单失败: ${getErrorDetail(e)}`
      }
    } finally {
      orderLoading.value = false
    }
  }

  // 撤单
  const cancelOrder = async (order) => {
    if (isModeLocked.value) {
      alert(buildModeLockMessage())
      return
    }
    cancelingOrderId.value = order.ord_id

    try {
      const res = await api.cancelOrder(order.ord_id, order.inst_id, props.mode)
      if (res.success) {
        // WebSocket 会自动推送订单状态更新
        // 备用：如果 WebSocket 未连接，手动刷新
        if (!wsConnected.value) {
          await fetchPendingOrders()
        }
      } else {
        alert(`撤单失败: ${res.error_message || '未知错误'}`)
      }
    } catch (e) {
      alert(`撤单失败: ${getErrorDetail(e)}`)
    } finally {
      cancelingOrderId.value = null
    }
  }

  // 下单前确认
  const confirmOrder = (side) => {
    if (isModeLocked.value) {
      orderResult.value = { success: false, message: buildModeLockMessage() }
      return
    }
    if (!orderForm.size) {
      orderResult.value = { success: false, message: '请输入数量' }
      return
    }

    if (orderForm.order_type === 'limit' && !orderForm.price) {
      orderResult.value = { success: false, message: '限价单请输入价格' }
      return
    }

    // 设置待确认订单信息
    pendingOrder.value = {
      inst_id: selectedSymbol.value,
      side,
      order_type: orderForm.order_type,
      size: orderForm.size,
      price: orderForm.price || (currentPrice.value?.last || ''),
      estimated: estimatedAmount.value
    }
    showConfirmDialog.value = true
  }

  // 确认后执行下单
  const executeOrder = async () => {
    showConfirmDialog.value = false
    if (pendingOrder.value) {
      if (isModeLocked.value) {
        orderResult.value = { success: false, message: buildModeLockMessage() }
        pendingOrder.value = null
        return
      }
      await placeOrder(pendingOrder.value.side)
      pendingOrder.value = null
      // 刷新最大可交易数量
      fetchMaxSize()
    }
  }

  // 取消确认
  const cancelConfirm = () => {
    showConfirmDialog.value = false
    pendingOrder.value = null
  }

  // ========== 合约交易方法 ==========

  // 切换交易类型
  const switchTradeType = (type) => {
    if (tradeType.value === type) return
    const previousInstId = getMarketInstId()
    tradeType.value = type
    const nextInstId = getMarketInstId(selectedSymbol.value, type)
    if (marketWS.isConnected && previousInstId && previousInstId !== nextInstId) {
      marketWS.unsubscribe(previousInstId, onPriceUpdate)
      if (nextInstId) {
        marketWS.subscribe(nextInstId, onPriceUpdate)
      }
    }
    fetchCurrentPrice()
    // 切换交易类型时刷新最大可交易量
    fetchMaxSize()
    // 切换交易类型时刷新委托和成交记录（不同交易类型有不同的订单）
    fetchPendingOrders()
    fetchFills()
    // 如果切换到合约，获取杠杆设置
    if (type !== 'spot') {
      fetchContractAccountConfig()
      fetchContractLeverage()
      fetchContractPositions()
    }
  }

  // 获取合约账户配置（持仓模式等）
  const fetchContractAccountConfig = async () => {
    try {
      const res = await api.getContractAccountConfig(props.mode)
      if (res && res.pos_mode) {
        contractPosMode.value = res.pos_mode
      }
    } catch (e) {
      console.error('获取账户配置失败:', e)
    }
  }

  // 根据当前页面的合约方向/持仓模式，推导下单/杠杆接口所需的 posSide
  const getDesiredContractPosSide = () => {
    if (contractPosMode.value === 'net_mode') return 'net'
    // open_long/close_long -> long；open_short/close_short -> short
    return contractSide.value.endsWith('long') ? 'long' : 'short'
  }

  // 设置杠杆
  const setLeverage = async (lever) => {
    if (isModeLocked.value) {
      orderResult.value = { success: false, message: buildModeLockMessage() }
      return
    }
    try {
      const posSide = contractSettings.marginMode === 'isolated' ? getDesiredContractPosSide() : ''
      const res = await api.setContractLeverage(
        contractInstId.value,
        String(lever),
        contractSettings.marginMode,
        posSide,
        props.mode
      )
      if (res.success) {
        contractSettings.leverage = lever
        orderResult.value = { success: true, message: `杠杆已设置为 ${lever}x` }
        // 刷新最大可开仓量
        fetchMaxSize()
      } else {
        orderResult.value = { success: false, message: res.message || '设置杠杆失败' }
      }
    } catch (e) {
      console.error('设置杠杆失败:', e)
      orderResult.value = { success: false, message: '设置杠杆失败: ' + getErrorDetail(e) }
    }
  }

  // 获取合约杠杆设置
  const fetchContractLeverage = async () => {
    try {
      const res = await api.getContractLeverage(contractInstId.value, contractSettings.marginMode, props.mode)
      if (res.success && res.data?.length > 0) {
        const desiredPosSide = getDesiredContractPosSide()
        const leverData = res.data.find(d => (d.posSide || '').toLowerCase() === desiredPosSide) || res.data[0]
        contractSettings.leverage = parseInt(leverData.lever) || 10
      }
    } catch (e) {
      console.error('获取杠杆设置失败:', e)
    }
  }

  // 获取合约持仓
  const fetchContractPositions = async () => {
    try {
      const instType = getMarketInstType()
      const res = await api.getContractPositions(instType, '', props.mode)
      if (res.positions) {
        contractPositions.value = res.positions
      }
    } catch (e) {
      console.error('获取合约持仓失败:', e)
    }
  }

  // 合约下单确认
  const confirmContractOrder = () => {
    if (isModeLocked.value) {
      orderResult.value = { success: false, message: buildModeLockMessage() }
      return
    }
    if (!orderForm.size) {
      orderResult.value = { success: false, message: '请输入数量' }
      return
    }

    if (orderForm.order_type === 'limit' && !orderForm.price) {
      orderResult.value = { success: false, message: '限价单请输入价格' }
      return
    }

    // 显示确认弹窗
    pendingContractOrder.value = {
      inst_id: contractInstId.value,
      side: contractSide.value,
      sideText: contractSideText.value,
      order_type: orderForm.order_type,
      size: orderForm.size,
      price: orderForm.price || (currentPrice.value?.last || ''),
      leverage: contractSettings.leverage,
      marginMode: contractSettings.marginMode === 'cross' ? '全仓' : '逐仓'
    }
    showContractConfirmDialog.value = true
  }

  // 取消合约下单确认
  const cancelContractConfirm = () => {
    showContractConfirmDialog.value = false
    pendingContractOrder.value = null
  }

  // 执行合约下单
  const executeContractOrder = async () => {
    showContractConfirmDialog.value = false
    if (isModeLocked.value) {
      orderResult.value = { success: false, message: buildModeLockMessage() }
      return
    }
    orderLoading.value = true
    orderResult.value = null

    // 解析合约方向
    let side
    const posSide = getDesiredContractPosSide()
    switch (contractSide.value) {
      case 'open_long':
        side = 'buy'
        break
      case 'open_short':
        side = 'sell'
        break
      case 'close_long':
        side = 'sell'
        break
      case 'close_short':
        side = 'buy'
        break
      default:
        orderResult.value = { success: false, message: '无效的操作方向' }
        orderLoading.value = false
        return
    }

    const isClose = contractSide.value.startsWith('close')

    try {
      const res = await api.placeContractOrder({
        instId: contractInstId.value,
        side,
        posSide,
        orderType: orderForm.order_type,
        size: orderForm.size,
        price: orderForm.price,
        tdMode: contractSettings.marginMode,
        reduceOnly: isClose,
        mode: props.mode
      })

      if (res.success) {
        orderResult.value = {
          success: true,
          message: `${contractSideText.value}成功，订单号: ${res.order_id}`
        }
        // 清空表单
        orderForm.size = ''
        orderForm.price = ''
        // 刷新数据
        fetchMaxSize()
        fetchContractPositions()
        fetchPendingOrders()
      } else {
        orderResult.value = {
          success: false,
          message: res.error_message || '下单失败'
        }
      }
    } catch (e) {
      console.error('合约下单失败:', e)
      orderResult.value = {
        success: false,
        message: '下单失败: ' + getErrorDetail(e)
      }
    } finally {
      orderLoading.value = false
    }
  }

  // 持仓快捷卖出
  const quickSell = (holding) => {
    // 切换到对应交易对
    selectedSymbol.value = `${holding.ccy}-USDT`
    // 设置为卖出方向
    currentSide.value = 'sell'
    // 填入可用数量
    orderForm.size = holding.available
    orderForm.order_type = 'market'
    orderForm.price = ''
    // 滚动到下单区域
    document.querySelector('.order-card')?.scrollIntoView({ behavior: 'smooth' })
  }

  // 同步成交记录到本地
  const syncFills = async () => {
    syncingFills.value = true
    try {
      const res = await api.syncFillsToLocal(props.mode)
      if (res.synced_count !== undefined) {
        alert(`同步成功: ${res.message || `共${res.synced_count}条记录，新增${res.new_count}条`}`)
        // 刷新持仓数据以更新成本
        await fetchSpotHoldings()
      }
    } catch (e) {
      console.error('同步成交记录失败:', e)
      alert('同步失败: ' + getErrorDetail(e))
    } finally {
      syncingFills.value = false
    }
  }

  // 打开编辑成本弹窗
  const openEditCostDialog = (holding) => {
    editingCcy.value = holding.ccy
    // 如果已有成本价，预填到输入框
    editCostValue.value = holding.avg_cost !== '-' ? holding.avg_cost : ''
    showEditCostDialog.value = true
  }

  // 关闭编辑成本弹窗
  const closeEditCostDialog = () => {
    showEditCostDialog.value = false
    editingCcy.value = ''
    editCostValue.value = ''
  }

  // 保存成本基础
  const saveCostBasis = async () => {
    if (!editCostValue.value || parseFloat(editCostValue.value) <= 0) {
      alert('请输入有效的成本价')
      return
    }

    savingCost.value = true
    try {
      await api.updateCostBasis({
        ccy: editingCcy.value,
        avgCost: parseFloat(editCostValue.value),
        mode: props.mode
      })
      closeEditCostDialog()
      // 刷新持仓数据以更新盈亏
      await fetchSpotHoldings()
    } catch (e) {
      console.error('保存成本失败:', e)
      alert('保存失败: ' + (e.message || '网络错误'))
    } finally {
      savingCost.value = false
    }
  }

  // 获取盈亏样式类
  const getPnlClass = (val) => {
    if (val === '-' || val === '0' || val === null || val === undefined) return ''
    const num = parseFloat(val)
    if (isNaN(num)) return ''
    if (num > 0) return 'profit'
    if (num < 0) return 'loss'
    return ''
  }

  // 格式化盈亏百分比
  const formatPnl = (val) => {
    if (val === '-' || val === '0' || val === null || val === undefined) return '-'
    const num = parseFloat(val)
    if (isNaN(num)) return '-'
    return (num >= 0 ? '+' : '') + num.toFixed(2) + '%'
  }

  // 点击外部关闭下拉框
  const handleClickOutside = (e) => {
    const dropdown = document.querySelector('.dropdown-select')
    if (dropdown && !dropdown.contains(e.target)) {
      symbolDropdownOpen.value = false
    }
  }

  // 自动刷新定时器
  let refreshTimer = null
  let priceRefreshTimer = null

  // WebSocket 价格更新回调
  const onPriceUpdate = (data) => {
    if (data.instId === getMarketInstId()) {
      currentPrice.value = {
        last: data.last,
        askPx: data.askPx,
        bidPx: data.bidPx,
        open24h: data.open24h,
        high24h: data.high24h,
        low24h: data.low24h,
        vol24h: data.vol24h,
        change24h: data.change24h,
        timestamp: data.timestamp,
      }
      // 同时更新 holdingPrices 缓存（如果是持仓币种）
      const ccy = data.instId.split('-')[0]
      const price = parseFloat(data.last) || 0
      if (price > 0 && holdingsBase.value.some(h => h.ccy === ccy)) {
        holdingPrices[ccy] = price
        recalcHoldings()
      }
    }
  }

  // WebSocket 账户更新回调
  const onAccountUpdate = (accountData, wsMode) => {
    // 过滤：只处理与当前页面模式匹配的推送
    if (wsMode && wsMode !== props.mode) {
      console.log(`[WS] 忽略账户更新 (模式不匹配: ws=${wsMode}, page=${props.mode})`)
      return
    }
    console.log('[WS] 收到账户更新:', accountData)
    // accountData 是 { ccy: { ccy, cashBal, availBal, frozenBal, eqUsd, uTime } } 格式
    // 转换为 accountBalance 所需格式
    const details = []
    let totalEquity = 0

    for (const ccy in accountData) {
      const item = accountData[ccy]
      const eqUsd = parseFloat(item.eqUsd) || 0
      totalEquity += eqUsd
      details.push({
        ccy: item.ccy,
        avail_bal: item.availBal || '0',
        frozen_bal: item.frozenBal || '0',
        cash_bal: item.cashBal || '0',
        eq_usd: item.eqUsd || '0',
      })
    }

    accountBalance.total_equity = totalEquity.toFixed(2)
    accountBalance.details = details

    // 优化：本地更新 holdingsBase 的余额部分，而非重新调用 API
    let holdingsChanged = false
    for (const ccy in accountData) {
      const item = accountData[ccy]
      const existingHolding = holdingsBase.value.find(h => h.ccy === ccy)
      if (existingHolding) {
        // 更新已有持仓的余额
        existingHolding.available = item.availBal || '0'
        existingHolding.frozen = item.frozenBal || '0'
        existingHolding.total = String(
          (parseFloat(item.availBal) || 0) + (parseFloat(item.frozenBal) || 0)
        )
        holdingsChanged = true
      } else {
        // 新增币种，需要调用 API 获取完整数据（包含成本）
        holdingsChanged = true
        fetchSpotHoldings()
        return
      }
    }

    if (holdingsChanged) {
      recalcHoldings()
    }

    // 刷新最大可交易量
    fetchMaxSize()
  }

  // 根据 OKX 推送的 instType 映射到页面 tradeType
  const mapInstTypeToTradeType = (instType) => {
    const t = (instType || '').toUpperCase()
    if (t === 'SPOT') return 'spot'
    if (t === 'SWAP') return 'swap'
    if (t === 'FUTURES') return 'futures'
    return null
  }

  // WebSocket 订单更新回调
  const onOrderUpdate = (orderData, wsMode) => {
    // 过滤：只处理与当前页面模式匹配的推送
    if (wsMode && wsMode !== props.mode) {
      console.log(`[WS] 忽略订单更新 (模式不匹配: ws=${wsMode}, page=${props.mode})`)
      return
    }

    const instType = orderData.instType
    const orderTradeType = mapInstTypeToTradeType(instType)
    // 过滤：只处理当前页面交易类型对应的订单推送，避免现货/合约互相污染列表
    if (orderTradeType && orderTradeType !== tradeType.value) {
      console.log(`[WS] 忽略订单更新 (instType=${instType}, tradeType=${tradeType.value})`)
      return
    }

    console.log('[WS] 收到订单更新:', orderData)
    // orderData 是单个订单对象
    const existingIndex = pendingOrders.value.findIndex(o => o.ord_id === orderData.ordId)

    // 转换字段名
    const order = {
      ord_id: orderData.ordId,
      inst_id: orderData.instId,
      side: orderData.side,
      ord_type: orderData.ordType,
      px: orderData.px,
      sz: orderData.sz,
      fill_sz: orderData.fillSz || orderData.accFillSz || '0',
      state: orderData.state,
      c_time: orderData.cTime,
      u_time: orderData.uTime,
    }

    // 如果是完全成交或已撤销，从当前委托中移除
    if (['filled', 'canceled', 'mmp_canceled'].includes(order.state)) {
      if (existingIndex >= 0) {
        pendingOrders.value.splice(existingIndex, 1)
      }
      // 订单完成后刷新对应持仓（现货/合约），避免“成交了但仓位不更新”的误判
      if (orderTradeType === 'spot') {
        Promise.all([fetchSpotHoldings(), fetchAccountBalance()])
      } else {
        Promise.all([fetchContractPositions(), fetchMaxSize()])
      }
    } else {
      // 更新或添加到当前委托
      if (existingIndex >= 0) {
        pendingOrders.value[existingIndex] = order
      } else {
        pendingOrders.value.unshift(order)
      }
    }
  }

  // WebSocket 成交更新回调
  const onFillUpdate = (fillData, wsMode) => {
    // 过滤：只处理与当前页面模式匹配的推送
    if (wsMode && wsMode !== props.mode) {
      console.log(`[WS] 忽略成交更新 (模式不匹配: ws=${wsMode}, page=${props.mode})`)
      return
    }

    const instType = fillData.instType
    const fillTradeType = mapInstTypeToTradeType(instType)
    // 过滤：只处理当前页面交易类型对应的成交推送
    if (fillTradeType && fillTradeType !== tradeType.value) {
      console.log(`[WS] 忽略成交更新 (instType=${instType}, tradeType=${tradeType.value})`)
      return
    }

    console.log('[WS] 收到成交更新:', fillData)
    // fillData 是单个成交对象
    const fill = {
      trade_id: fillData.tradeId,
      inst_id: fillData.instId,
      side: fillData.side,
      fill_px: fillData.fillPx,
      fill_sz: fillData.fillSz,
      fee: fillData.fee,
      fee_ccy: fillData.feeCcy,
      ts: fillData.ts,
    }

    // 检查是否已存在
    const exists = fills.value.some(f => f.trade_id === fill.trade_id)
    if (!exists) {
      fills.value.unshift(fill)
      // 保留最近 50 条
      if (fills.value.length > 50) {
        fills.value = fills.value.slice(0, 50)
      }
      // 成交后刷新对应持仓（现货/合约）
      if (fillTradeType === 'spot') {
        fetchSpotHoldings()
      } else {
        fetchContractPositions()
        fetchMaxSize()
      }
    }
  }

  // 初始化 WebSocket 连接
  const initWebSocket = async () => {
    try {
      // 重要：私有通道订阅需要携带 mode，避免模拟盘/实盘页面收不到对应推送
      marketWS.setMode(props.mode)
      await marketWS.connect()
      wsConnected.value = marketWS.isConnected

      // 订阅当前交易对行情
      const currentInstId = getMarketInstId()
      if (currentInstId) {
        marketWS.subscribe(currentInstId, onPriceUpdate)
      }

      // 订阅所有持仓币种的价格
      subscribeHoldingPrices()

      // 订阅私有通道（账户、订单、成交）
      marketWS.subscribeAccount(onAccountUpdate)
      marketWS.subscribeOrders(onOrderUpdate)
      marketWS.subscribeFills(onFillUpdate)

      console.log('[WS] 已订阅所有通道: ticker, holdings-tickers, account, orders, fills')
    } catch (e) {
      console.error('WebSocket 连接失败:', e)
      wsConnected.value = false
    }
  }

  // 清理 WebSocket 订阅
  const cleanupWebSocket = () => {
    if (marketWS.isConnected) {
      const currentInstId = getMarketInstId()
      if (currentInstId) {
        marketWS.unsubscribe(currentInstId, onPriceUpdate)
      }
      unsubscribeHoldingPrices()
      marketWS.unsubscribeAccount(onAccountUpdate)
      marketWS.unsubscribeOrders(onOrderUpdate)
      marketWS.unsubscribeFills(onFillUpdate)
    }
  }

  // 监听交易对变化
  watch(selectedSymbol, (newSymbol, oldSymbol) => {
    const oldInstId = getMarketInstId(oldSymbol)
    const newInstId = getMarketInstId(newSymbol)
    // 取消旧交易对订阅
    if (marketWS.isConnected && oldInstId) {
      marketWS.unsubscribe(oldInstId, onPriceUpdate)
    }
    // 订阅新交易对
    if (marketWS.isConnected && newInstId) {
      marketWS.subscribe(newInstId, onPriceUpdate)
    }
    // 同时获取一次 HTTP 价格（作为初始值）
    fetchCurrentPrice()
    fetchMaxSize()
    // 持久化保存
    if (settingsLoaded.value) debouncedSave()
  })

  // 合约保证金模式切换：需要刷新杠杆与最大可开仓量，避免 UI 显示旧数据
  watch(() => contractSettings.marginMode, () => {
    if (tradeType.value !== 'spot') {
      fetchContractLeverage()
      fetchMaxSize()
    }
  })

  // 合约方向切换：逐仓/双向持仓可能多空杠杆不同；同时 max size 也依赖方向
  watch(contractSide, () => {
    if (tradeType.value !== 'spot') {
      fetchContractLeverage()
      fetchMaxSize()
    }
  })

  // 监听可用交易对变化（用户添加/删除时持久化）
  watch(availableSymbols, () => {
    if (settingsLoaded.value) debouncedSave()
  }, { deep: true })

  // 监听交易模式变化（模拟盘/实盘切换时重载数据）
  watch(() => props.mode, async (newMode, oldMode) => {
    if (!isInitialized || newMode === oldMode) return

    console.log(`[TradingView] 模式切换: ${oldMode} -> ${newMode}`)
    marketWS.setMode(newMode)

    // 重置状态
    spotHoldings.value = []
    holdingsBase.value = []
    pendingOrders.value = []
    fills.value = []
    Object.keys(holdingPrices).forEach(k => delete holdingPrices[k])

    // 重新加载所有数据
    await refreshAll()

    // 更新持仓币种列表
    const holdingPairs = spotHoldings.value
      .filter(h => !h.is_stablecoin && parseFloat(h.total || '0') > 0)
      .map(h => `${h.ccy}-USDT`)
    holdingSymbols.value = [...holdingPairs]

    // 重新订阅 WebSocket（私有通道会根据新模式获取数据）
    if (marketWS.isConnected) {
      subscribeHoldingPrices()
    }

    // 刷新当前价格和最大交易量
    fetchCurrentPrice()
    fetchMaxSize()
  })

  // 是否已初始化（用于区分首次挂载和从缓存激活）
  let isInitialized = false

  onMounted(async () => {
    // 先加载用户设置（交易对列表等）
    await loadSettings()

    // 初次加载数据 - 刷新持仓
    await refreshAll()

    // 从持仓中提取非稳定币
    const holdingPairs = []
    if (spotHoldings.value && spotHoldings.value.length > 0) {
      spotHoldings.value
        .filter(h => !h.is_stablecoin && parseFloat(h.total || '0') > 0)
        .forEach(h => holdingPairs.push(`${h.ccy}-USDT`))
    }

    // 记录持仓币种（用于锁定，不可删除）
    holdingSymbols.value = [...holdingPairs]

    // 将持仓币种加入可选列表（确保可选，但不强制覆盖用户设置）
    const existing = new Set(availableSymbols.value)
    holdingPairs.forEach(s => {
      if (!existing.has(s)) {
        availableSymbols.value.push(s)
      }
    })

    // 如果可选列表仍为空（首次使用），从持仓初始化
    if (availableSymbols.value.length === 0 && holdingPairs.length > 0) {
      availableSymbols.value = [...holdingPairs]
    }

    // 如果没有加载到有效的 selectedSymbol，使用第一个持仓或第一个可选
    if (!availableSymbols.value.includes(selectedSymbol.value)) {
      if (holdingPairs.length > 0) {
        selectedSymbol.value = holdingPairs[0]
      } else if (availableSymbols.value.length > 0) {
        selectedSymbol.value = availableSymbols.value[0]
      }
    }

    // 并行加载价格和最大可交易数量
    Promise.all([
      fetchCurrentPrice(),
      fetchMaxSize()
    ])
    document.addEventListener('click', handleClickOutside)

    // 初始化 WebSocket（行情 + 账户 + 订单 + 成交）
    initWebSocket()

    // 备用定时器：仅在 WebSocket 未连接时通过 HTTP 刷新
    // 价格每 10 秒刷新，订单每 30 秒刷新
    // 持仓和余额通过 WebSocket 账户推送实时更新，无需轮询
    priceRefreshTimer = setInterval(() => {
      if (tradingStatus.api_configured && !wsConnected.value) {
        fetchCurrentPrice()
      }
    }, 10000)

    refreshTimer = setInterval(() => {
      if (tradingStatus.api_configured && !wsConnected.value) {
        Promise.all([fetchPendingOrders(), fetchAccountBalance(), fetchSpotHoldings()])
      }
    }, 30000)

    isInitialized = true
  })

  // keep-alive 激活时调用（从其他页面切换回来）
  onActivated(() => {
    // 首次挂载时 onMounted 已经处理，跳过
    if (!isInitialized) return

    // 从设置页返回后，这里必须重新拉状态。
    // 否则 keep-alive 会保留旧的 api_configured，导致“设置里已配置、交易页仍显示未配置”。
    fetchTradingStatus()

    // 重新添加事件监听
    document.addEventListener('click', handleClickOutside)

    // 重新订阅 WebSocket（订阅使用 Set，重复调用是安全的）
    if (wsConnected.value) {
      const currentInstId = getMarketInstId()
      if (currentInstId) {
        marketWS.subscribe(currentInstId, onPriceUpdate)
      }
      subscribeHoldingPrices()
      marketWS.subscribeAccount(onAccountUpdate)
      marketWS.subscribeOrders(onOrderUpdate)
      marketWS.subscribeFills(onFillUpdate)
    } else {
      initWebSocket()
    }

    // 重新启动定时器（仅在 WebSocket 断连时作为备用）
    if (!priceRefreshTimer) {
      priceRefreshTimer = setInterval(() => {
        if (tradingStatus.api_configured && !wsConnected.value) {
          fetchCurrentPrice()
        }
      }, 10000)
    }

    if (!refreshTimer) {
      refreshTimer = setInterval(() => {
        if (tradingStatus.api_configured && !wsConnected.value) {
          Promise.all([fetchPendingOrders(), fetchAccountBalance(), fetchSpotHoldings()])
        }
      }, 30000)
    }

    // 仅刷新实时价格（其他数据通过 WebSocket 推送，保持缓存）
    fetchCurrentPrice()
  })

  // keep-alive 停用时调用（切换到其他页面）
  onDeactivated(() => {
    // 移除事件监听
    document.removeEventListener('click', handleClickOutside)

    // 清理定时器（节省资源）
    if (refreshTimer) {
      clearInterval(refreshTimer)
      refreshTimer = null
    }
    if (priceRefreshTimer) {
      clearInterval(priceRefreshTimer)
      priceRefreshTimer = null
    }

    // 清理 WebSocket 订阅（避免后台组件响应更新导致错误）
    cleanupWebSocket()
  })

  onUnmounted(() => {
    document.removeEventListener('click', handleClickOutside)
    if (refreshTimer) {
      clearInterval(refreshTimer)
    }
    if (priceRefreshTimer) {
      clearInterval(priceRefreshTimer)
    }
    // 清理 WebSocket 订阅
    cleanupWebSocket()
  })

  return {
    formatNumber,
    formatPrice,
    formatPercent,
    formatTime,
    getPlClass,
    getChangeClass,
    formatChange,
    getOrderStateText,
    toggleSymbolDropdown,
    selectSymbol,
    addCustomSymbol,
    removeSymbol,
    fetchCurrentPrice,
    fetchMaxSize,
    setQuickAmount,
    refreshAll,
    fetchTradingStatus,
    fetchAccountBalance,
    onHoldingPriceUpdate,
    subscribeHoldingPrices,
    unsubscribeHoldingPrices,
    fetchSpotHoldings,
    fetchPendingOrders,
    fetchFills,
    placeOrder,
    cancelOrder,
    confirmOrder,
    executeOrder,
    cancelConfirm,
    switchTradeType,
    fetchContractAccountConfig,
    getDesiredContractPosSide,
    setLeverage,
    fetchContractLeverage,
    fetchContractPositions,
    confirmContractOrder,
    cancelContractConfirm,
    executeContractOrder,
    quickSell,
    syncFills,
    openEditCostDialog,
    closeEditCostDialog,
    saveCostBasis,
    getPnlClass,
    formatPnl,
    handleClickOutside,
    refreshTimer,
    priceRefreshTimer,
    onPriceUpdate,
    onAccountUpdate,
    mapInstTypeToTradeType,
    onOrderUpdate,
    onFillUpdate,
    initWebSocket,
    cleanupWebSocket,
    isInitialized,
  };
}
