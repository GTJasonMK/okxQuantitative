// Vue Router 配置

import { createRouter, createWebHashHistory } from 'vue-router';

const routes = [
  {
    path: '/',
    name: 'Market',
    component: () => import('./views/MarketView.vue'),
    meta: { title: '行情' },
  },
  {
    path: '/watchlist',
    redirect: to => ({
      path: '/data',
      query: {
        ...to.query,
        tab: 'watchlist',
      },
    }),
  },
  {
    path: '/inventory',
    redirect: to => ({
      path: '/data',
      query: {
        ...to.query,
        tab: 'inventory',
      },
    }),
  },
  {
    path: '/data',
    name: 'DataCenter',
    component: () => import('./views/DataCenterView.vue'),
    meta: { title: '数据中心' },
  },
  {
    path: '/trading/simulated',
    redirect: to => ({
      path: '/trading',
      query: {
        ...to.query,
        tab: 'simulated',
      },
    }),
  },
  {
    path: '/trading/live',
    redirect: to => ({
      path: '/trading',
      query: {
        ...to.query,
        tab: 'live',
      },
    }),
  },
  {
    path: '/trading',
    name: 'TradingCenter',
    component: () => import('./views/TradingCenterView.vue'),
    meta: { title: '交易中心' },
  },
  {
    path: '/backtest',
    redirect: to => ({
      path: '/strategy',
      query: {
        ...to.query,
        tab: 'backtest',
      },
    }),
  },
  {
    path: '/analytics',
    name: 'Analytics',
    component: () => import('./views/AnalyticsView.vue'),
    meta: { title: '分析中心' },
  },
  {
    path: '/journal',
    name: 'Journal',
    component: () => import('./views/JournalView.vue'),
    meta: { title: '交易日志' },
  },
  {
    path: '/strategy',
    name: 'StrategyCenter',
    component: () => import('./views/StrategyCenterView.vue'),
    meta: { title: '策略中心' },
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('./views/SettingsView.vue'),
    meta: { title: '设置' },
  },
];

const router = createRouter({
  history: createWebHashHistory(),
  routes,
});

// 路由守卫：更新页面标题
router.beforeEach((to, from, next) => {
  document.title = `${to.meta.title || '首页'} - OKX量化交易系统`;
  next();
});

export default router;
