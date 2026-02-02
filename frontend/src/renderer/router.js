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
    path: '/trading/simulated',
    name: 'TradingSimulated',
    component: () => import('./views/TradingView.vue'),
    props: { mode: 'simulated' },
    meta: { title: '模拟盘交易' },
  },
  {
    path: '/trading/live',
    name: 'TradingLive',
    component: () => import('./views/TradingView.vue'),
    props: { mode: 'live' },
    meta: { title: '实盘交易' },
  },
  {
    // 保留旧路由，重定向到模拟盘
    path: '/trading',
    redirect: '/trading/simulated',
  },
  {
    path: '/backtest',
    name: 'Backtest',
    component: () => import('./views/BacktestView.vue'),
    meta: { title: '回测' },
  },
  {
    path: '/strategy',
    name: 'Strategy',
    component: () => import('./views/StrategyView.vue'),
    meta: { title: '策略' },
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
