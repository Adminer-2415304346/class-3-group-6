/* SZX：切屏跟随原生登录请求；只保存动效位置，不接管 POST 或读取账户输入。 */
(function () {
    'use strict';

    var root = document.documentElement;
    var storageKey = 'account-screen-transition';
    var accountScreens = ['login', 'register', 'reset'];
    var motion = window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : null;
    var fallbackTimer = null;
    var pending = null;
    var loginStarted = null;
    var loginFrame = null;
    var loginProgress = 0;
    var waitingLimit = 0.88;

    // 普通 POST 没有后端进度事件：等待段是渐进反馈，不能把它当成真实百分比。
    // 预留最后一段，只有已认证的目标文档准备好时才允许完成揭幕。
    function waitingProgress(elapsed) {
        return waitingLimit * (1 - Math.exp(-Math.max(0, elapsed) / 1500));
    }

    function stopLoginFrame() {
        if (loginFrame !== null && window.cancelAnimationFrame) window.cancelAnimationFrame(loginFrame);
        loginFrame = null;
    }

    function paintLoginProgress() {
        if (loginStarted === null || reducedMotion()) return;
        loginProgress = Math.min(waitingLimit, Math.max(loginProgress, waitingProgress(Date.now() - loginStarted)));
        root.style.setProperty('--account-login-progress', String(loginProgress));
        root.style.setProperty('--account-wipe-position', (loginProgress * 100).toFixed(3) + 'vw');
    }

    function advanceLogin() {
        loginFrame = null;
        if (loginStarted === null || reducedMotion() || document.hidden) return;
        paintLoginProgress();
        if (loginProgress < waitingLimit - 0.001 && window.requestAnimationFrame) {
            loginFrame = window.requestAnimationFrame(advanceLogin);
        }
    }

    function startLogin() {
        if (reducedMotion() || screenFor(window.location.href) !== 'login') return;
        stopLoginFrame();
        loginStarted = Date.now();
        root.setAttribute('data-login-departure', 'verify');
        advanceLogin();
    }

    function clearResponse() {
        root.removeAttribute('data-account-response');
        root.style.removeProperty('--account-screen-start');
        root.style.removeProperty('--account-screen-remaining');
        root.style.removeProperty('--account-screen-duration');
    }

    function resumeResponse() {
        if (!pending || pending.kind !== 'login-submit' || !successfulDestination() || reducedMotion()) return;
        var progress = Number.isFinite(pending.progress) && pending.progress >= 0 && pending.progress <= waitingLimit
            ? pending.progress : Math.min(waitingLimit, waitingProgress(Date.now() - pending.time));
        root.setAttribute('data-account-response', 'ready');
        root.style.setProperty('--account-screen-start', (progress * 100).toFixed(3) + 'vw');
        root.style.setProperty('--account-screen-remaining', ((1 - progress) * 100).toFixed(3) + '%');
        // 快响应保留舒展的切屏；慢响应不再等一整段 900ms，只完成剩余距离。
        root.style.setProperty('--account-screen-duration', Math.round(Math.max(180, 900 * (1 - progress))) + 'ms');
    }

    function reducedMotion() {
        return Boolean(motion && motion.matches);
    }

    function screenFor(href) {
        try {
            var url = new URL(href, window.location.href);
            if (url.origin !== window.location.origin || /^\/(admin|logout)(\/|$)/.test(url.pathname)) return null;
            var path = url.pathname.replace(/\/+$/, '') || '/';
            if (path === '/login') return 'login';
            if (path === '/register') return 'register';
            if (path === '/forget_password') return 'reset';
            return 'site';
        } catch (error) {
            return null;
        }
    }

    function transitionFor(from, to) {
        if (!from || !to || from === to) return null;
        if (accountScreens.includes(from) && accountScreens.includes(to)) return 'reshape';
        if (accountScreens.includes(from) && to === 'site') return 'enter-site';
        if (from === 'site' && accountScreens.includes(to)) return 'enter-account';
        return null;
    }

    function clearStored() {
        try { window.sessionStorage.removeItem(storageKey); } catch (error) { /* 存储禁用不影响导航 */ }
    }

    function remember(from, to, kind, progress) {
        clearStored();
        if (reducedMotion() || !transitionFor(from, to)) return;
        try {
            var intent = { from: from, to: to, kind: kind, time: Date.now() };
            if (kind === 'login-submit' && Number.isFinite(progress)) intent.progress = progress;
            window.sessionStorage.setItem(storageKey, JSON.stringify(intent));
        } catch (error) { /* 原生过渡仍可工作；不阻止链接或提交 */ }
    }

    function clearArrival() {
        root.removeAttribute('data-account-arrival');
        if (fallbackTimer !== null) window.clearTimeout(fallbackTimer);
        fallbackTimer = null;
        if (!root.hasAttribute('data-account-transition')) clearResponse();
    }

    function clearDeparture() {
        stopLoginFrame();
        loginStarted = null;
        loginProgress = 0;
        root.removeAttribute('data-login-departure');
        root.removeAttribute('data-account-leaving');
        root.style.removeProperty('--account-login-progress');
        root.style.removeProperty('--account-wipe-position');
    }

    function markSiteEntry(from, to) {
        if (transitionFor(from, to) !== 'enter-site') return;
        // 本页保留此标记：切屏快照已经负责入场，结束后不能再启动首页文字动画。
        root.setAttribute('data-account-entered', 'site');
    }

    function successfulDestination() {
        // 登录失败留在登录页；还要防止其他错误重定向被当作登录成功。
        return !pending || pending.kind !== 'login-submit' ||
            (document.body && document.body.getAttribute('data-authenticated') === 'true');
    }

    function showFallback() {
        if (!pending || reducedMotion() || !successfulDestination()) return;
        markSiteEntry(pending.from, pending.to);
        resumeResponse();
        root.setAttribute('data-account-arrival', transitionFor(pending.from, pending.to));
        if (fallbackTimer !== null) window.clearTimeout(fallbackTimer);
        fallbackTimer = window.setTimeout(clearArrival, 1100);
    }

    // 只存短期导航意图，并在目标页立即消费；刷新、失败响应和过期记录不重播。
    try {
        var raw = window.sessionStorage.getItem(storageKey);
        clearStored();
        var item = raw ? JSON.parse(raw) : null;
        var age = item ? Date.now() - item.time : -1;
        if (item && Number.isFinite(age) && age >= 0 && age < 30000 &&
            ['link', 'login-submit'].includes(item.kind) &&
            (item.kind !== 'login-submit' || (item.from === 'login' && item.to === 'site')) &&
            item.to === screenFor(window.location.href) && transitionFor(item.from, item.to) &&
            !reducedMotion()) {
            pending = item;
            markSiteEntry(item.from, item.to);
            root.setAttribute('data-account-arrival', transitionFor(item.from, item.to));
        }
    } catch (error) { /* 损坏的记录直接丢弃 */ }

    document.addEventListener('click', function (event) {
        if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey ||
            event.shiftKey || event.altKey) return;
        var link = event.target.closest && event.target.closest('a[href]');
        if (!link || link.hasAttribute('download') ||
            (link.target && link.target !== '_self')) return;
        var from = screenFor(window.location.href);
        var to = screenFor(link.href);
        clearDeparture();
        remember(from, to, 'link');
        if (!reducedMotion() && transitionFor(from, to) === 'reshape') {
            root.setAttribute('data-account-leaving', 'reshape');
        }
    });

    document.addEventListener('submit', function (event) {
        if (event.defaultPrevented || !event.target || event.target.id !== 'login-form') return;
        remember(screenFor(window.location.href), 'site', 'login-submit', 0);
        // 不 preventDefault、不新增请求、不等待动效；CSRF、认证和 next 仍由 Django 处理。
        startLogin();
    });

    function cleanNative() {
        root.removeAttribute('data-account-transition');
        root.removeAttribute('data-account-from');
        root.removeAttribute('data-account-to');
        if (!root.hasAttribute('data-account-arrival')) clearResponse();
    }

    function configureNative(event, from, to, incoming) {
        var transition = event.viewTransition;
        if (!transition) return;
        var mode = transitionFor(from, to);
        if (!mode || reducedMotion() || (incoming && !successfulDestination())) {
            transition.ready.catch(function () {});
            transition.finished.catch(function () {});
            transition.skipTransition();
            clearArrival();
            cleanNative();
            return;
        }
        root.setAttribute('data-account-transition', mode);
        root.setAttribute('data-account-from', from);
        root.setAttribute('data-account-to', to);
        if (incoming) {
            markSiteEntry(from, to);
            resumeResponse();
        }
        clearArrival();
        // ready 在离开页可能拒绝；显式处理，避免跨文档过渡产生控制台错误。
        transition.ready.then(function () {}, function () {
            if (!incoming) return;
            cleanNative();
            showFallback();
        });
        transition.finished.then(cleanNative, cleanNative);
    }

    // 此脚本作为 head 中的普通同步脚本加载，保证 pagereveal 早于首帧注册。
    window.addEventListener('pageswap', function (event) {
        var target = event.activation && event.activation.entry;
        var from = screenFor(window.location.href);
        var to = target ? screenFor(target.url) : null;
        if (loginStarted !== null) {
            // pageswap 在目标文档就绪、旧画面快照之前触发；把真实画面的位置交给目标页。
            paintLoginProgress();
            if (to === 'site') remember(from, to, 'login-submit', loginProgress);
            else clearStored();
            stopLoginFrame();
        }
        configureNative(event, from, to, false);
    });

    window.addEventListener('pagereveal', function (event) {
        var activation = window.navigation && window.navigation.activation;
        var previous = activation && activation.from;
        var from = previous ? screenFor(previous.url) : (pending && pending.from);
        configureNative(event, from, screenFor(window.location.href), true);
    });

    document.addEventListener('DOMContentLoaded', function () {
        if (!successfulDestination()) {
            pending = null;
            clearArrival();
            root.removeAttribute('data-account-entered');
        } else if (root.hasAttribute('data-account-arrival')) {
            resumeResponse();
            fallbackTimer = window.setTimeout(clearArrival, 1100);
        }
    }, { once: true });

    window.addEventListener('pageshow', function (event) {
        clearDeparture();
        if (!event.persisted) return;
        pending = null;
        clearStored();
        clearArrival();
        cleanNative();
    });

    window.addEventListener('pagehide', stopLoginFrame);
    document.addEventListener('visibilitychange', function () {
        stopLoginFrame();
        if (!document.hidden && loginStarted !== null) advanceLogin();
    });

    if (motion && motion.addEventListener) {
        motion.addEventListener('change', function () {
            if (!reducedMotion()) return;
            pending = null;
            clearStored();
            clearArrival();
            clearDeparture();
            cleanNative();
        });
    }
})();
