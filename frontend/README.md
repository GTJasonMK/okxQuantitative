# OKX量化交易系统 - 前端

基于 Electron + Vue3 的可视化界面。

## 技术栈

- **Electron**: 跨平台桌面应用框架
- **Vue 3**: 前端框架
- **Pinia**: 状态管理
- **ECharts**: K线图表
- **Axios**: HTTP请求

## 开发环境

```bash
# 安装依赖
npm install

# 启动开发服务（需要先启动后端）
npm run dev
```

## 构建

```bash
# 构建生产版本
npm run build
```

## 目录结构

```
frontend/
├── src/
│   ├── main/              # Electron主进程
│   │   └── index.js
│   ├── preload/           # 预加载脚本
│   │   └── index.js
│   └── renderer/          # 渲染进程(Vue)
│       ├── main.js        # Vue入口
│       ├── App.vue        # 根组件
│       ├── router.js      # 路由配置
│       ├── components/    # 公共组件
│       ├── views/         # 页面组件
│       ├── stores/        # 状态管理
│       ├── services/      # API服务
│       └── assets/        # 静态资源
├── index.html
├── package.json
└── vite.config.js
```

## 页面功能

### 行情页面 (/)
- 实时行情显示
- K线图表（支持多周期）
- 技术指标叠加（MA、BOLL等）
- 数据同步功能

### 回测页面 (/backtest)
- 策略选择
- 回测参数配置
- 回测结果展示
- 收益曲线图

### 策略页面 (/strategy)
- 策略列表管理
- 策略参数配置
- 风控参数设置

### 设置页面 (/settings)
- API连接配置
- 数据管理
- 显示设置

## 注意事项

1. 启动前端前需要先启动后端服务
2. 默认连接地址: http://127.0.0.1:8000
3. 开发模式会自动打开DevTools
