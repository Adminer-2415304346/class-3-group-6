/**
 * Dark Mode：键盘快捷键 + 系统主题跟随
 *
 * 重要：真正的主题状态由 base.html 里的内联防闪烁脚本持有（window.themeManager）。
 * 这个模块不要再自己 setAttribute 改主题——两套实现并存时会出现
 *  - 页面加载时重复 applyTheme，可能和用户的 localStorage 偏好不一致；
 *  - 绕过了 html 上的 data-theme-anim 过渡标记，切换时样式会"跳"一下；
 *  - 连点时两套状态互相覆盖，表现为"有时卡样式"。
 * 所以这里只负责触发，统一走 window.themeManager。
 */

const STORAGE_KEY = 'dark-mode-enabled';
const ENABLE_SYSTEM = true;

/** 读取当前主题：以 DOM 上的真实状态为准，避免两套缓存不一致 */
function getCurrentTheme() {
    return document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
}

/** 设置主题（转发给内联脚本的实现，带过渡标记） */
function setTheme(theme) {
    const next = theme === 'dark' ? 'dark' : 'light';
    if (window.themeManager && typeof window.themeManager.apply === 'function') {
        return window.themeManager.apply(next);
    }
    // 兜底：内联脚本尚未执行时（几乎不会发生）直接改 DOM
    const root = document.documentElement;
    if (next === 'dark') {
        root.setAttribute('data-theme', 'dark');
        root.classList.add('dark');
    } else {
        root.removeAttribute('data-theme');
        root.classList.remove('dark');
    }
    try { localStorage.setItem(STORAGE_KEY, next); } catch (e) { /* 隐私模式忽略 */ }
    window.__THEME__ = next;
    return next;
}

/** 切换：每次都按 DOM 当前状态重新判定，连点不会错位 */
function toggleTheme() {
    return setTheme(getCurrentTheme() === 'dark' ? 'light' : 'dark');
}

/** Ctrl/Cmd + Shift + D */
function setupKeyboardShortcut() {
    document.addEventListener('keydown', function(e) {
        if ((e.ctrlKey || e.metaKey) && e.shiftKey && (e.key === 'D' || e.key === 'd')) {
            e.preventDefault();
            toggleTheme();
        }
    });
}

/** 跟随系统：仅在用户没有手动选择过时生效 */
function setupSystemThemeListener() {
    if (!ENABLE_SYSTEM || !window.matchMedia) return;
    const query = window.matchMedia('(prefers-color-scheme: dark)');
    const listener = function(e) {
        let saved = null;
        try { saved = localStorage.getItem(STORAGE_KEY); } catch (err) { /* ignore */ }
        if (saved === null) setTheme(e.matches ? 'dark' : 'light');
    };
    if (query.addEventListener) query.addEventListener('change', listener);
    else if (query.addListener) query.addListener(listener);
}

export function initDarkMode() {
    window.DarkMode = {
        getCurrentTheme,
        setTheme,
        toggle: toggleTheme,
    };
    setupKeyboardShortcut();
    setupSystemThemeListener();
}
