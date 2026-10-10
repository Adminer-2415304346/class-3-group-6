/**
 * DjangoBlog 前端主入口文件
 * 使用 Alpine.js + HTMX 实现现代化服务端渲染
 */

// 导入样式文件（Vite开发模式必需）
import './styles/main.css';
import './styles/launcherLogin.css';
import './styles/registration.css';
import './styles/accountTransitions.css';

import Alpine from 'alpinejs';
import focus from '@alpinejs/focus';
import intersect from '@alpinejs/intersect';
import collapse from '@alpinejs/collapse';
import htmx from 'htmx.org';

// 导入Dark Mode（会自动初始化防闪烁）
import { initDarkMode } from './features/darkMode.js';
import { initCodeCopyFeature } from './components/codeCopy.js';
import { initLegacyCommentsFeature } from './components/legacyComments.js';

// 注册Alpine插件
Alpine.plugin(focus);
Alpine.plugin(intersect);
Alpine.plugin(collapse);

// 导入组件
import commentSystem from './components/commentSystem.js';
import backToTop from './components/backToTop.js';
import navigation from './components/navigation.js';
import imageLightbox from './components/imageLightbox.js';
import reactionPicker from './components/reactionPicker.js';
import accountFlow from './components/accountFlow.js';
import launcherLogin from './components/launcherLogin.js';
import launcherAccount from './components/launcherAccount.js';

// 注册全局Alpine数据
Alpine.data('commentSystem', commentSystem);
Alpine.data('backToTop', backToTop);
Alpine.data('navigation', navigation);
Alpine.data('imageLightbox', imageLightbox);
Alpine.data('reactionPicker', reactionPicker);
Alpine.data('accountFlow', accountFlow);
Alpine.data('launcherLogin', launcherLogin);
Alpine.data('launcherAccount', launcherAccount);

// 全局工具函数
window.Alpine = Alpine;
window.htmx = htmx;

// 启动Alpine
Alpine.start();

// 初始化Dark Mode
initDarkMode();

// 初始化代码复制按钮
initCodeCopyFeature();

// 初始化旧版评论回复功能
initLegacyCommentsFeature();

// HTMX 配置
htmx.config.defaultSwapStyle = 'innerHTML';
htmx.config.defaultSwapDelay = 0;
htmx.config.defaultSettleDelay = 20;

// HTMX boost 配置：自动提取 #main 内容
document.body.addEventListener('htmx:beforeSwap', function(evt) {
    // 对于 boost 的请求，确保正确提取内容
    if (evt.detail.boosted && evt.detail.target.id === 'main') {
        console.log('HTMX boost navigation:', evt.detail.pathInfo.requestPath);
    }
});

// HTMX 加载完成后重新初始化 Alpine 组件
document.body.addEventListener('htmx:afterSwap', function(evt) {
    // Alpine 会自动检测新的 DOM 元素并初始化
    console.log('Content swapped, Alpine auto-initializing new components');

    // 滚动到顶部（可选）
    if (evt.detail.boosted) {
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }
});

// NProgress页面加载进度条（保留原有功能）
import NProgress from './utils/nprogress.js';
NProgress.configure({ showSpinner: false });

// SZX：登录切屏已经反馈请求状态；避免同时出现另一条、不同步的进度条。
const responseLinkedArrival = document.documentElement.getAttribute('data-account-arrival') === 'enter-site' ||
    document.documentElement.getAttribute('data-account-transition') === 'enter-site' ||
    document.documentElement.getAttribute('data-account-entered') === 'site';
if (!responseLinkedArrival) {
    NProgress.start();
    NProgress.set(0.4);
    const interval = setInterval(() => NProgress.inc(), 1000);
    const finishPageProgress = () => {
        NProgress.done();
        clearInterval(interval);
    };
    if (document.readyState === 'complete') finishPageProgress();
    else window.addEventListener('DOMContentLoaded', finishPageProgress, { once: true });
} else {
    NProgress.done();
}

// 页面导航时的进度条
window.addEventListener('beforeunload', () => {
    if (!document.documentElement.hasAttribute('data-login-departure')) NProgress.start();
});

// HTMX 事件监听 - 配合 NProgress
document.body.addEventListener('htmx:beforeRequest', () => {
  NProgress.start();
});

document.body.addEventListener('htmx:afterRequest', () => {
  NProgress.done();
});

console.log('✨ DjangoBlog Frontend Loaded (Alpine.js + HTMX + Tailwind CSS)');
