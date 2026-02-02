// WebSocket 实时数据服务
// 连接后端 WebSocket 获取实时行情、账户、订单、成交推送

import { getBaseURL } from './api'

class MarketWebSocket {
  constructor() {
    this.ws = null
    this.url = null  // 动态获取
    this.reconnectAttempts = 0
    this.maxReconnectAttempts = 5
    this.reconnectDelay = 3000
    this.isConnecting = false
    this.heartbeatInterval = null

    // 订阅状态
    this.subscribedInstruments = new Set()
    this.subscribedChannels = new Set()

    // 交易模式：用于订阅私有通道时告诉后端应连接 simulated/live 哪套私有 WS
    this.mode = null

    // 回调函数: channel -> Set<callback>
    this.listeners = {
      ticker: new Map(),   // instId -> Set<callback>
      account: new Set(),  // Set<callback>
      order: new Set(),    // Set<callback>
      fill: new Set(),     // Set<callback>
    }
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

    // 动态获取 WebSocket URL
    const baseUrl = getBaseURL()
    this.url = baseUrl.replace(/^http/, 'ws') + '/ws/market'

    return new Promise((resolve, reject) => {
      try {
        this.ws = new WebSocket(this.url)

        this.ws.onopen = () => {
          console.log('[WS] 连接成功')
          this.isConnecting = false
          this.reconnectAttempts = 0

          // 重新订阅
          this._resubscribeAll()

          // 启动心跳
          this._startHeartbeat()

          resolve()
        }

        this.ws.onmessage = (event) => {
          this._handleMessage(event.data)
        }

        this.ws.onerror = (error) => {
          console.error('[WS] 连接错误:', error)
          this.isConnecting = false
          reject(error)
        }

        this.ws.onclose = (event) => {
          console.log('[WS] 连接关闭:', event.code, event.reason)
          this.isConnecting = false
          this._stopHeartbeat()

          // 自动重连
          if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++
            console.log(`[WS] ${this.reconnectDelay / 1000}秒后尝试重连 (${this.reconnectAttempts}/${this.maxReconnectAttempts})`)
            setTimeout(() => this.connect(), this.reconnectDelay)
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
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
    this.subscribedInstruments.clear()
    this.subscribedChannels.clear()
    this.listeners.ticker.clear()
    this.listeners.account.clear()
    this.listeners.order.clear()
    this.listeners.fill.clear()
  }

  /**
   * 检查是否已连接
   */
  get isConnected() {
    return this.ws?.readyState === WebSocket.OPEN
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

  _sendSubscribe(channels, instruments = []) {
    this._send({
      action: 'subscribe',
      channels: channels,
      instruments: instruments,
      ...(this.mode ? { mode: this.mode } : {}),
    })
  }

  _sendUnsubscribe(channels, instruments = []) {
    this._send({
      action: 'unsubscribe',
      channels: channels,
      instruments: instruments,
      ...(this.mode ? { mode: this.mode } : {}),
    })
  }

  _send(data) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data))
    }
  }

  _resubscribeAll() {
    // 重新订阅行情
    if (this.subscribedInstruments.size > 0) {
      this._sendSubscribe(['ticker'], [...this.subscribedInstruments])
    }

    // 重新订阅私有通道
    const privateChannels = [...this.subscribedChannels].filter(
      ch => ['account', 'orders', 'fills'].includes(ch)
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
        case 'subscribed':
          console.log('[WS] 订阅成功:', message.channels, message.instruments)
          break
        case 'unsubscribed':
          console.log('[WS] 取消订阅成功:', message.channels, message.instruments)
          break
        case 'pong':
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

  _startHeartbeat() {
    this._stopHeartbeat()
    this.heartbeatInterval = setInterval(() => {
      this._send({ action: 'ping' })
    }, 30000)
  }

  _stopHeartbeat() {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval)
      this.heartbeatInterval = null
    }
  }
}

// 单例实例
const marketWS = new MarketWebSocket()

export default marketWS
