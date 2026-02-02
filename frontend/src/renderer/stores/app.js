// 应用状态管理

import { defineStore } from 'pinia';
import { api } from '../services/api';

export const useAppStore = defineStore('app', {
  state: () => ({
    // 连接状态
    isConnected: false,
    isSimulated: true,

    // 当前选中的交易对
    currentSymbol: 'BTC-USDT',
    currentTimeframe: '1H',

    // 可用的交易对列表
    symbols: [],

    // 加载状态
    loading: false,
    error: null,
  }),

  getters: {
    // 当前交易模式
    tradingMode: (state) => state.isSimulated ? 'simulated' : 'live',
  },

  actions: {
    // 检查后端连接（带重试机制）
    async checkConnection(retries = 5, interval = 1000) {
      for (let i = 0; i < retries; i++) {
        try {
          const response = await api.healthCheck();
          if (response.status === 'healthy') {
            this.isConnected = true;
            // 连接成功后加载 OKX 配置
            await this.loadOKXConfig();
            return true;
          }
        } catch (error) {
          // 连接失败，等待后重试
          if (i < retries - 1) {
            console.log(`[App] 等待后端服务... (${i + 1}/${retries})`);
            await new Promise(resolve => setTimeout(resolve, interval));
          }
        }
      }
      this.isConnected = false;
      return false;
    },

    // 加载 OKX 配置（获取 isSimulated 状态）
    async loadOKXConfig() {
      try {
        const result = await api.getOKXConfig();
        // use_simulated 代表后端“默认模式”（OKX_USE_SIMULATED），即使密钥未配置完整也应更新 UI 显示
        this.isSimulated = result.use_simulated !== false;
        console.log(`[App] 默认模式: ${this.isSimulated ? '模拟盘' : '实盘'}`);
      } catch (e) {
        console.warn('[App] 加载 OKX 配置失败:', e);
      }
    },

    // 设置交易模式
    setSimulated(value) {
      this.isSimulated = value;
    },

    // 设置当前交易对
    setCurrentSymbol(symbol) {
      this.currentSymbol = symbol;
    },

    // 设置当前时间周期
    setCurrentTimeframe(timeframe) {
      this.currentTimeframe = timeframe;
    },

    // 加载可用交易对
    async loadSymbols() {
      try {
        this.loading = true;
        const response = await api.getAvailableSymbols();
        if (response.code === 0) {
          this.symbols = response.data;
        }
      } catch (error) {
        this.error = error.message;
      } finally {
        this.loading = false;
      }
    },

    // 设置错误
    setError(error) {
      this.error = error;
    },

    // 清除错误
    clearError() {
      this.error = null;
    },
  },
});
