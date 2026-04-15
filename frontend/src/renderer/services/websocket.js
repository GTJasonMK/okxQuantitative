// WebSocket 实时数据服务
// 连接后端 WebSocket 获取实时行情、账户、订单、成交推送

import { getBaseURL } from './api.js'

class MarketWebSocket {
  constructor() {
    this.ws = null
    this.url = null  // 动态获取
    this.reconnectAttempts = 0
    this.maxReconnectAttempts = Number.POSITIVE_INFINITY
    this.reconnectDelay = 3000
    this.isConnecting = false
    this.heartbeatInterval = null
    this.watchdogInterval = null
    this.reconnectTimer = null
    this.manualClose = false
    this.connectionState = false
    this.heartbeatIntervalMs = 30000
    this.watchdogIntervalMs = 10000
    this.silentTimeoutMs = 45000
    this.lastMessageAt = 0
    this.lastPongAt = 0
    this.lastHeartbeatAt = 0

    // 订阅状态
    this.subscribedInstruments = new Set()
    this.subscribedCandles = new Set()
    this.subscribedChannels = new Set()
    this.connectionListeners = new Set()

    // 交易模式：用于订阅私有通道时告诉后端应连接 simulated/live 哪套私有 WS
    this.mode = null

    // 回调函数: channel -> Set<callback>
    this.listeners = {
      ticker: new Map(),   // instId -> Set<callback>
      candle: new Map(),   // instId:timeframe -> Set<callback>
      account: new Set(),  // Set<callback>
      order: new Set(),    // Set<callback>
      fill: new Set(),     // Set<callback>
      alert: new Set(),    // Set<callback>
      assistantPatrol: new Set(), // Set<callback>
      trendResearch: new Set(), // Set<callback>
      researchPlatform: new Set(), // Set<callback>
      trendDiagnostics: new Set(), // Set<callback>
    }
    this.trendDiagnosticsConfig = null
  }

  /**
   * 连接 WebSocket
   */
  connect() {
    if (this.ws?.readyState === WebSocket.OPEN) {
      console.log('[WS] 已连接')
      return Promise.resolve()
    }

    if (this.isConnecting) {
      console.log('[WS] 正在连接中...')
      return Promise.resolve()
    }

    this.isConnecting = true
    this.manualClose = false
    this._clearReconnectTimer()

    // 动态获取 WebSocket URL
    const baseUrl = getBaseURL()
    this.url = baseUrl.replace(/^http/, 'ws') + '/ws/market'

    return new Promise((resolve, reject) => {
      try {
        const socket = new WebSocket(this.url)
        this.ws = socket

        socket.onopen = () => {
          if (this.ws !== socket) {
            return
          }

          console.log('[WS] 连接成功')
          this.isConnecting = false
          this.reconnectAttempts = 0
          this._clearReconnectTimer()
          this._markConnectionActive()
          this._notifyConnectionState(true)

          // 重新订阅
          this._resubscribeAll()

          // 启动心跳
          this._startHeartbeat()
          this._startWatchdog()

          resolve()
        }

        socket.onmessage = (event) => {
          if (this.ws !== socket) {
            return
          }

          this._markMessageActive()
          this._handleMessage(event.data)
        }

        socket.onerror = (error) => {
          const wasConnecting = this.isConnecting && this.ws === socket
          console.error('[WS] 连接错误:', error)
          if (this.ws !== socket) {
            return
          }

          this.isConnecting = false
          if (wasConnecting) {
            reject(error)
          }
        }

        socket.onclose = (event) => {
          const isActiveSocket = this.ws === socket
          const wasConnecting = this.isConnecting && isActiveSocket
          const wasManualClose = this.manualClose
          console.log('[WS] 连接关闭:', event.code, event.reason)
          if (!isActiveSocket) {
            return
          }

          this.isConnecting = false
          this.ws = null
          this._stopHeartbeat()
          this._stopWatchdog()
          this._resetLiveness()
          this._notifyConnectionState(false, { reason: event.reason || `close:${event.code}` })

          if (wasConnecting) {
            reject(new Error(`WebSocket 连接在握手阶段关闭: ${event.reason || event.code}`))
          }

          // 自动重连
          if (!wasManualClose) {
            this._scheduleReconnect(event.reason || `close:${event.code}`)
          }
        }
      } catch (error) {
        this.isConnecting = false
        reject(error)
      }
    })
  }

  /**
   * 断开连接
   */
  disconnect() {
    this._stopHeartbeat()
    this._stopWatchdog()
    this._clearReconnectTimer()
    this._resetLiveness()
    this.manualClose = true
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
    this._notifyConnectionState(false, { reason: 'manual disconnect' })
    this.subscribedInstruments.clear()
    this.subscribedCandles.clear()
    this.subscribedChannels.clear()
    this.listeners.ticker.clear()
    this.listeners.candle.clear()
    this.listeners.account.clear()
    this.listeners.order.clear()
    this.listeners.fill.clear()
    this.listeners.alert.clear()
    this.listeners.assistantPatrol.clear()
    this.listeners.trendResearch.clear()
    this.listeners.researchPlatform.clear()
    this.listeners.trendDiagnostics.clear()
    this.trendDiagnosticsConfig = null
  }

  /**
   * 检查是否已连接
   */
  get isConnected() {
    return this.ws?.readyState === WebSocket.OPEN
  }

  addConnectionListener(callback) {
    this.connectionListeners.add(callback)
  }

  removeConnectionListener(callback) {
    this.connectionListeners.delete(callback)
  }

  _normalizeCandleTimeframe(timeframe) {
    if (typeof timeframe !== 'string') {
      return ''
    }

    const normalized = timeframe.trim()
    if (!normalized) {
      return ''
    }

    let nextTimeframe = normalized
    if (normalized.startsWith('candle')) {
      nextTimeframe = normalized.slice(6)
    }

    return nextTimeframe
  }

  _buildCandleKey(instId, timeframe) {
    return `${instId}:${this._normalizeCandleTimeframe(timeframe)}`
  }

  _parseCandleKey(key) {
    const separatorIndex = key.lastIndexOf(':')
    if (separatorIndex <= 0) {
      return null
    }

    const instId = key.slice(0, separatorIndex)
    const timeframe = this._normalizeCandleTimeframe(key.slice(separatorIndex + 1))
    if (!instId || !timeframe) {
      return null
    }

    return { instId, timeframe }
  }

  /**
   * 设置交易模式（simulated/live）
   * TradingView 会在订阅私有通道前调用，用于避免“WS 连接正常但数据静默”的模式不匹配问题。
   */
  setMode(mode) {
    if (mode === 'simulated' || mode === 'live') {
      this.mode = mode
    } else {
      this.mode = null
    }

    // 模式切换后：重新发送订阅，通知后端将该连接路由到对应环境的私有 WS
    if (this.isConnected) {
      this._resubscribeAll()
    }
  }

  // ==================== 行情订阅 ====================

  /**
   * 订阅交易对的实时行情
   * @param {string} instId - 交易对，如 "BTC-USDT"
   * @param {function} callback - 回调函数
   */
  subscribe(instId, callback) {
    if (!this.listeners.ticker.has(instId)) {
      this.listeners.ticker.set(instId, new Set())
    }
    this.listeners.ticker.get(instId).add(callback)

    if (!this.subscribedInstruments.has(instId)) {
      this.subscribedInstruments.add(instId)
      if (this.isConnected) {
        this._sendSubscribe(['ticker'], [instId])
      }
    }
  }

  /**
   * 取消订阅行情
   */
  unsubscribe(instId, callback) {
    if (this.listeners.ticker.has(instId)) {
      this.listeners.ticker.get(instId).delete(callback)

      if (this.listeners.ticker.get(instId).size === 0) {
        this.listeners.ticker.delete(instId)
        this.subscribedInstruments.delete(instId)
        if (this.isConnected) {
          this._sendUnsubscribe(['ticker'], [instId])
        }
      }
    }
  }

  /**
   * 批量订阅行情
   */
  subscribeMany(instIds, callback) {
    const newInstruments = []

    for (const instId of instIds) {
      if (!this.listeners.ticker.has(instId)) {
        this.listeners.ticker.set(instId, new Set())
      }
      this.listeners.ticker.get(instId).add(callback)

      if (!this.subscribedInstruments.has(instId)) {
        this.subscribedInstruments.add(instId)
        newInstruments.push(instId)
      }
    }

    if (newInstruments.length > 0 && this.isConnected) {
      this._sendSubscribe(['ticker'], newInstruments)
    }
  }

  subscribeCandle(instId, timeframe, callback) {
    const normalizedTimeframe = this._normalizeCandleTimeframe(timeframe)
    if (!instId || !normalizedTimeframe) {
      return
    }

    const candleKey = this._buildCandleKey(instId, normalizedTimeframe)
    if (!this.listeners.candle.has(candleKey)) {
      this.listeners.candle.set(candleKey, new Set())
    }
    this.listeners.candle.get(candleKey).add(callback)

    if (!this.subscribedCandles.has(candleKey)) {
      this.subscribedCandles.add(candleKey)
      if (this.isConnected) {
        this._sendSubscribe(['candle'], [instId], { timeframe: normalizedTimeframe })
      }
    }
  }

  unsubscribeCandle(instId, timeframe, callback) {
    const normalizedTimeframe = this._normalizeCandleTimeframe(timeframe)
    if (!instId || !normalizedTimeframe) {
      return
    }

    const candleKey = this._buildCandleKey(instId, normalizedTimeframe)
    if (!this.listeners.candle.has(candleKey)) {
      return
    }

    this.listeners.candle.get(candleKey).delete(callback)
    if (this.listeners.candle.get(candleKey).size > 0) {
      return
    }

    this.listeners.candle.delete(candleKey)
    this.subscribedCandles.delete(candleKey)
    if (this.isConnected) {
      this._sendUnsubscribe(['candle'], [instId], { timeframe: normalizedTimeframe })
    }
  }

  subscribeManyCandles(subscriptions, callback) {
    const groupedSubscriptions = new Map()

    for (const subscription of subscriptions || []) {
      const instId = subscription?.instId
      const timeframe = this._normalizeCandleTimeframe(subscription?.timeframe)
      if (!instId || !timeframe) {
        continue
      }

      const candleKey = this._buildCandleKey(instId, timeframe)
      if (!this.listeners.candle.has(candleKey)) {
        this.listeners.candle.set(candleKey, new Set())
      }
      this.listeners.candle.get(candleKey).add(callback)

      if (this.subscribedCandles.has(candleKey)) {
        continue
      }

      this.subscribedCandles.add(candleKey)
      if (!groupedSubscriptions.has(timeframe)) {
        groupedSubscriptions.set(timeframe, [])
      }
      groupedSubscriptions.get(timeframe).push(instId)
    }

    if (!this.isConnected) {
      return
    }

    for (const [timeframe, instIds] of groupedSubscriptions.entries()) {
      if (instIds.length > 0) {
        this._sendSubscribe(['candle'], instIds, { timeframe })
      }
    }
  }

  // ==================== 账户订阅 ====================

  /**
   * 订阅账户余额更新
   * @param {function} callback - 回调函数，参数: (accountData)
   */
  subscribeAccount(callback) {
    this.listeners.account.add(callback)

    if (!this.subscribedChannels.has('account')) {
      this.subscribedChannels.add('account')
      if (this.isConnected) {
        this._sendSubscribe(['account'])
      }
    }
  }

  /**
   * 取消订阅账户
   */
  unsubscribeAccount(callback) {
    this.listeners.account.delete(callback)

    if (this.listeners.account.size === 0) {
      this.subscribedChannels.delete('account')
      if (this.isConnected) {
        this._sendUnsubscribe(['account'])
      }
    }
  }

  // ==================== 订单订阅 ====================

  /**
   * 订阅订单状态更新
   * @param {function} callback - 回调函数，参数: (orderData)
   */
  subscribeOrders(callback) {
    this.listeners.order.add(callback)

    if (!this.subscribedChannels.has('orders')) {
      this.subscribedChannels.add('orders')
      if (this.isConnected) {
        this._sendSubscribe(['orders'])
      }
    }
  }

  /**
   * 取消订阅订单
   */
  unsubscribeOrders(callback) {
    this.listeners.order.delete(callback)

    if (this.listeners.order.size === 0) {
      this.subscribedChannels.delete('orders')
      if (this.isConnected) {
        this._sendUnsubscribe(['orders'])
      }
    }
  }

  // ==================== 成交订阅 ====================

  /**
   * 订阅成交回报
   * @param {function} callback - 回调函数，参数: (fillData)
   */
  subscribeFills(callback) {
    this.listeners.fill.add(callback)

    if (!this.subscribedChannels.has('fills')) {
      this.subscribedChannels.add('fills')
      if (this.isConnected) {
        this._sendSubscribe(['fills'])
      }
    }
  }

  /**
   * 取消订阅成交
   */
  unsubscribeFills(callback) {
    this.listeners.fill.delete(callback)

    if (this.listeners.fill.size === 0) {
      this.subscribedChannels.delete('fills')
      if (this.isConnected) {
        this._sendUnsubscribe(['fills'])
      }
    }
  }

  // ==================== 提醒订阅 ====================

  subscribeAlerts(callback) {
    this.listeners.alert.add(callback)

    if (!this.subscribedChannels.has('alerts')) {
      this.subscribedChannels.add('alerts')
      if (this.isConnected) {
        this._sendSubscribe(['alerts'])
      }
    }
  }

  unsubscribeAlerts(callback) {
    this.listeners.alert.delete(callback)

    if (this.listeners.alert.size === 0) {
      this.subscribedChannels.delete('alerts')
      if (this.isConnected) {
        this._sendUnsubscribe(['alerts'])
      }
    }
  }

  subscribeAssistantPatrol(callback) {
    this.listeners.assistantPatrol.add(callback)

    if (!this.subscribedChannels.has('assistant_patrol')) {
      this.subscribedChannels.add('assistant_patrol')
      if (this.isConnected) {
        this._sendSubscribe(['assistant_patrol'])
      }
    }
  }

  subscribeTrendResearch(callback) {
    this.listeners.trendResearch.add(callback)

    if (!this.subscribedChannels.has('trend_research')) {
      this.subscribedChannels.add('trend_research')
      if (this.isConnected) {
        this._sendSubscribe(['trend_research'])
      }
    }
  }

  subscribeTrendDiagnostics(config = {}, callback) {
    this.listeners.trendDiagnostics.add(callback)
    this.trendDiagnosticsConfig = {
      instId: config.instId || '',
      timelineLimit: config.timelineLimit || 40,
    }

    if (!this.subscribedChannels.has('trend_diagnostics')) {
      this.subscribedChannels.add('trend_diagnostics')
    }

    if (this.isConnected) {
      this._sendSubscribe(['trend_diagnostics'], [], {
        inst_id: this.trendDiagnosticsConfig.instId,
        timeline_limit: this.trendDiagnosticsConfig.timelineLimit,
      })
    }
  }

  unsubscribeTrendResearch(callback) {
    this.listeners.trendResearch.delete(callback)

    if (this.listeners.trendResearch.size === 0) {
      this.subscribedChannels.delete('trend_research')
      if (this.isConnected) {
        this._sendUnsubscribe(['trend_research'])
      }
    }
  }

  subscribeResearchPlatform(callback) {
    this.listeners.researchPlatform.add(callback)

    if (!this.subscribedChannels.has('research_platform')) {
      this.subscribedChannels.add('research_platform')
      if (this.isConnected) {
        this._sendSubscribe(['research_platform'])
      }
    }
  }

  subscribeDataCenterCollection(callback) {
    this.subscribeResearchPlatform(callback)
  }

  unsubscribeResearchPlatform(callback) {
    this.listeners.researchPlatform.delete(callback)

    if (this.listeners.researchPlatform.size === 0) {
      this.subscribedChannels.delete('research_platform')
      if (this.isConnected) {
        this._sendUnsubscribe(['research_platform'])
      }
    }
  }

  unsubscribeDataCenterCollection(callback) {
    this.unsubscribeResearchPlatform(callback)
  }

  unsubscribeTrendDiagnostics(callback) {
    this.listeners.trendDiagnostics.delete(callback)

    if (this.listeners.trendDiagnostics.size === 0) {
      this.subscribedChannels.delete('trend_diagnostics')
      if (this.isConnected) {
        this._sendUnsubscribe(['trend_diagnostics'], [], {
          inst_id: this.trendDiagnosticsConfig?.instId || '',
        })
      }
      this.trendDiagnosticsConfig = null
    }
  }

  unsubscribeAssistantPatrol(callback) {
    this.listeners.assistantPatrol.delete(callback)

    if (this.listeners.assistantPatrol.size === 0) {
      this.subscribedChannels.delete('assistant_patrol')
      if (this.isConnected) {
        this._sendUnsubscribe(['assistant_patrol'])
      }
    }
  }

  // ==================== 便捷方法 ====================

  /**
   * 订阅所有私有通道
   */
  subscribePrivate(callbacks = {}) {
    if (callbacks.account) this.subscribeAccount(callbacks.account)
    if (callbacks.order) this.subscribeOrders(callbacks.order)
    if (callbacks.fill) this.subscribeFills(callbacks.fill)
  }

  /**
   * 取消所有私有通道订阅
   */
  unsubscribePrivate(callbacks = {}) {
    if (callbacks.account) this.unsubscribeAccount(callbacks.account)
    if (callbacks.order) this.unsubscribeOrders(callbacks.order)
    if (callbacks.fill) this.unsubscribeFills(callbacks.fill)
  }

  // ==================== 内部方法 ====================

  _sendSubscribe(channels, instruments = [], extra = {}) {
    this._send({
      action: 'subscribe',
      channels: channels,
      instruments: instruments,
      ...extra,
      ...(this.mode ? { mode: this.mode } : {}),
    })
  }

  _sendUnsubscribe(channels, instruments = [], extra = {}) {
    this._send({
      action: 'unsubscribe',
      channels: channels,
      instruments: instruments,
      ...extra,
      ...(this.mode ? { mode: this.mode } : {}),
    })
  }

  _send(data) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data))
    }
  }

  _markConnectionActive() {
    const now = Date.now()
    this.lastMessageAt = now
    this.lastPongAt = now
    this.lastHeartbeatAt = 0
  }

  _markMessageActive() {
    this.lastMessageAt = Date.now()
  }

  _markPongActive() {
    const now = Date.now()
    this.lastMessageAt = now
    this.lastPongAt = now
  }

  _resetLiveness() {
    this.lastMessageAt = 0
    this.lastPongAt = 0
    this.lastHeartbeatAt = 0
  }

  _clearReconnectTimer() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
  }

  _scheduleReconnect(reason = '') {
    if (this.reconnectTimer || this.manualClose) {
      return
    }

    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.warn('[WS] 已达到最大重连次数，停止自动重连')
      return
    }

    this.reconnectAttempts++
    const detail = reason ? `，原因: ${reason}` : ''
    console.log(`[WS] ${this.reconnectDelay / 1000}秒后尝试重连 (${this.reconnectAttempts})${detail}`)
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null
      this.connect().catch((error) => {
        console.warn('[WS] 自动重连失败:', error)
      })
    }, this.reconnectDelay)
  }

  _forceReconnect(reason = 'silent timeout') {
    if (!this.ws || this.manualClose) {
      return
    }

    console.warn(`[WS] 检测到连接静默，准备强制重连: ${reason}`)
    this._notifyConnectionState(false, { reason })

    const socket = this.ws
    this.ws = null
    this._stopHeartbeat()
    this._stopWatchdog()
    this._resetLiveness()

    try {
      socket.close(4000, reason)
      this._scheduleReconnect(reason)
    } catch (error) {
      console.warn('[WS] 强制关闭连接失败，改为直接重连:', error)
      this._scheduleReconnect(reason)
    }
  }

  _resubscribeAll() {
    // 重新订阅行情
    if (this.subscribedInstruments.size > 0) {
      this._sendSubscribe(['ticker'], [...this.subscribedInstruments])
    }

    if (this.subscribedCandles.size > 0) {
      const groupedCandles = new Map()
      for (const candleKey of this.subscribedCandles) {
        const parsed = this._parseCandleKey(candleKey)
        if (!parsed) {
          continue
        }

        if (!groupedCandles.has(parsed.timeframe)) {
          groupedCandles.set(parsed.timeframe, [])
        }
        groupedCandles.get(parsed.timeframe).push(parsed.instId)
      }

      for (const [timeframe, instIds] of groupedCandles.entries()) {
        if (instIds.length > 0) {
          this._sendSubscribe(['candle'], instIds, { timeframe })
        }
      }
    }

    if (this.subscribedChannels.has('trend_diagnostics') && this.trendDiagnosticsConfig) {
      this._sendSubscribe(['trend_diagnostics'], [], {
        inst_id: this.trendDiagnosticsConfig.instId,
        timeline_limit: this.trendDiagnosticsConfig.timelineLimit,
      })
    }

    // 重新订阅私有通道
    const privateChannels = [...this.subscribedChannels].filter(
      ch => ['account', 'orders', 'fills', 'alerts', 'assistant_patrol', 'trend_research', 'research_platform'].includes(ch)
    )
    if (privateChannels.length > 0) {
      this._sendSubscribe(privateChannels)
    }
  }

  _handleMessage(data) {
    try {
      const message = JSON.parse(data)

      switch (message.type) {
        case 'ticker':
          this._handleTicker(message.data)
          break
        case 'candle':
          this._handleCandle(message.data)
          break
        case 'account':
          // 传递 mode，让回调可以判断是否处理
          this._handleAccount(message.data, message.mode)
          break
        case 'order':
          this._handleOrder(message.data, message.mode)
          break
        case 'fill':
          this._handleFill(message.data, message.mode)
          break
        case 'alert':
          this._handleAlert(message.data)
          break
        case 'assistant_patrol':
          this._handleAssistantPatrol(message.data)
          break
        case 'trend_research':
          this._handleTrendResearch(message.data)
          break
        case 'research_platform':
          this._handleResearchPlatform(message.data)
          break
        case 'trend_diagnostics':
          this._handleTrendDiagnostics(message.data)
          break
        case 'subscribed':
          console.log('[WS] 订阅成功:', message.channels, message.instruments)
          break
        case 'unsubscribed':
          console.log('[WS] 取消订阅成功:', message.channels, message.instruments)
          break
        case 'pong':
          this._markPongActive()
          break
        case 'error':
          console.error('[WS] 错误:', message.message)
          break
      }
    } catch (error) {
      console.error('[WS] 解析消息失败:', error)
    }
  }

  _handleTicker(ticker) {
    const instId = ticker.instId
    const callbacks = this.listeners.ticker.get(instId)

    if (callbacks) {
      const data = {
        instId: ticker.instId,
        last: parseFloat(ticker.last),
        lastSz: parseFloat(ticker.lastSz || 0),
        askPx: parseFloat(ticker.askPx),
        bidPx: parseFloat(ticker.bidPx),
        open24h: parseFloat(ticker.open24h),
        high24h: parseFloat(ticker.high24h),
        low24h: parseFloat(ticker.low24h),
        vol24h: parseFloat(ticker.vol24h),
        change24h: parseFloat(ticker.change24h),
        timestamp: parseInt(ticker.ts),
      }

      for (const callback of callbacks) {
        try {
          callback(data)
        } catch (error) {
          console.error('[WS] 行情回调执行错误:', error)
        }
      }
    }
  }

  _handleAccount(accountData, mode) {
    for (const callback of this.listeners.account) {
      try {
        callback(accountData, mode)
      } catch (error) {
        console.error('[WS] 账户回调执行错误:', error)
      }
    }
  }

  _handleOrder(orderData, mode) {
    for (const callback of this.listeners.order) {
      try {
        callback(orderData, mode)
      } catch (error) {
        console.error('[WS] 订单回调执行错误:', error)
      }
    }
  }

  _handleFill(fillData, mode) {
    for (const callback of this.listeners.fill) {
      try {
        callback(fillData, mode)
      } catch (error) {
        console.error('[WS] 成交回调执行错误:', error)
      }
    }
  }

  _handleCandle(candle) {
    const instId = candle.instId
    const timeframe = this._normalizeCandleTimeframe(candle.timeframe)
    const candleKey = this._buildCandleKey(instId, timeframe)
    const callbacks = this.listeners.candle.get(candleKey)

    if (!callbacks) {
      return
    }

    const data = {
      instId,
      timeframe,
      timestamp: parseInt(candle.ts),
      open: parseFloat(candle.open),
      high: parseFloat(candle.high),
      low: parseFloat(candle.low),
      close: parseFloat(candle.close),
      volume: parseFloat(candle.vol || 0),
      volumeCcy: parseFloat(candle.volCcy || 0),
      volumeQuote: parseFloat(candle.volCcyQuote || 0),
      confirm: parseInt(candle.confirm || 0),
    }

    for (const callback of callbacks) {
      try {
        callback(data)
      } catch (error) {
        console.error('[WS] K线回调执行错误:', error)
      }
    }
  }

  _handleAlert(alertData) {
    for (const callback of this.listeners.alert) {
      try {
        callback(alertData)
      } catch (error) {
        console.error('[WS] 提醒回调执行错误:', error)
      }
    }
  }

  _handleAssistantPatrol(payload) {
    for (const callback of this.listeners.assistantPatrol) {
      try {
        callback(payload)
      } catch (error) {
        console.error('[WS] 主动巡检回调执行错误:', error)
      }
    }
  }

  _handleTrendResearch(payload) {
    for (const callback of this.listeners.trendResearch) {
      try {
        callback(payload)
      } catch (error) {
        console.error('[WS] 趋势研究回调执行错误:', error)
      }
    }
  }

  _handleResearchPlatform(payload) {
    const knownEvents = new Set([
      'session_updated',
      'session_started',
      'session_running',
      'session_stopping',
      'session_stopped',
      'session_finished',
      'session_failed',
      'second_flushed',
      'session_quality_updated',
      'census_updated',
      'dataset_manifest_created',
      'dataset_preview_updated',
      'training_run_updated',
    ])
    if (!payload || !knownEvents.has(payload.event)) {
      return
    }

    for (const callback of this.listeners.researchPlatform) {
      try {
        callback(payload)
      } catch (error) {
        console.error('[WS] 研究平台回调执行错误:', error)
      }
    }
  }

  _handleTrendDiagnostics(payload) {
    for (const callback of this.listeners.trendDiagnostics) {
      try {
        callback(payload)
      } catch (error) {
        console.error('[WS] 趋势诊断回调执行错误:', error)
      }
    }
  }

  _startHeartbeat() {
    this._stopHeartbeat()
    this.heartbeatInterval = setInterval(() => {
      this.lastHeartbeatAt = Date.now()
      this._send({ action: 'ping' })
    }, this.heartbeatIntervalMs)
  }

  _stopHeartbeat() {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval)
      this.heartbeatInterval = null
    }
  }

  _startWatchdog() {
    this._stopWatchdog()
    this.watchdogInterval = setInterval(() => {
      if (!this.isConnected || !this.ws) {
        return
      }

      const now = Date.now()
      const lastAliveAt = Math.max(this.lastMessageAt, this.lastPongAt, 0)
      if (lastAliveAt <= 0) {
        return
      }

      if (now - lastAliveAt <= this.silentTimeoutMs) {
        return
      }

      this._forceReconnect(`silent timeout ${Math.round((now - lastAliveAt) / 1000)}s`)
    }, this.watchdogIntervalMs)
  }

  _stopWatchdog() {
    if (this.watchdogInterval) {
      clearInterval(this.watchdogInterval)
      this.watchdogInterval = null
    }
  }

  _notifyConnectionState(connected, meta = {}) {
    if (this.connectionState === connected) {
      return
    }

    this.connectionState = connected
    for (const callback of this.connectionListeners) {
      try {
        callback({ connected, ...meta })
      } catch (error) {
        console.error('[WS] 连接状态回调执行错误:', error)
      }
    }
  }
}

// 单例实例
const marketWS = new MarketWebSocket()

export default marketWS
