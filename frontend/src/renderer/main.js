// Vue3 入口文件

import { createApp } from 'vue';
import { createPinia } from 'pinia';
import App from './App.vue';
import router from './router';

// 全局样式
import './assets/styles/main.css';

// 创建应用
const app = createApp(App);

// 使用插件
app.use(createPinia());
app.use(router);

// 挂载应用
app.mount('#app');
