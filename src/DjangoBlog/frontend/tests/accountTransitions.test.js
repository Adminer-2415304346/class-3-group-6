/** SZX：跨页意图与回退测试，不保存凭据、不连接本机业务数据库。 */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { runInNewContext } from 'node:vm';

const script = readFileSync(new URL('../../blog/static/blog/js/accountTransitions.js', import.meta.url), 'utf8');
const styles = readFileSync(new URL('../src/styles/accountTransitions.css', import.meta.url), 'utf8');
const key = 'account-screen-transition';

test('the site wipe retains the full outgoing screen and matches only the brand symbol', () => {
    assert.match(styles, /html\[data-account-transition='enter-account'\] \.launcher-panel/);
    assert.match(styles, /html\[data-account-transition='enter-account'\] \.launcher-visual/);
    assert.match(styles, /html\[data-account-transition\] \.launcher-brand-mark/);
    assert.doesNotMatch(styles, /html\[data-account-transition\] \.launcher-brand\s*[,\{]/);
    assert.match(styles, /::view-transition-new\(root\)\s*\{\s*animation: account-screen-open/);
    assert.doesNotMatch(styles, /enter-site'\]::view-transition-old\(account-panel\)/);
});

test('the default site reveal stays slow while login starts immediately without a navigation delay', () => {
    assert.match(styles, /--account-screen-duration:\s*900ms/);
    assert.match(styles, /--account-response-duration:\s*220ms/);
    assert.match(styles, /animation: account-screen-open var\(--account-screen-duration\)/);
    assert.match(styles, /animation: account-prepare-login var\(--account-response-duration\)/);
    assert.match(styles, /animation: account-site-arrive var\(--account-screen-duration\)/);
    assert.match(styles, /animation: account-response-open var\(--account-screen-duration\)/);
    assert.match(styles, /clip-path: inset\(0 var\(--account-screen-remaining, 100%\) 0 0\)/);
    assert.match(styles, /html\[data-account-arrival='enter-site'\]\[data-account-response\][\s\S]*?overflow-x: clip/);
    const current = page();
    const event = { target: { id: 'login-form' } };
    current.documentEvent('submit', event);
    assert.equal(current.root.getAttribute('data-login-departure'), 'verify');
    assert.equal(current.timers.size, 0);
    assert.equal(event.defaultPrevented, undefined);
});

function page(path = '/login/', options = {}) {
    const attributes = new Map();
    const properties = new Map();
    const stored = new Map();
    if (options.marker) stored.set(key, JSON.stringify(options.marker));
    if (options.raw) stored.set(key, options.raw);
    const documentEvents = new Map();
    const windowEvents = new Map();
    const timers = new Map();
    const frames = new Map();
    let now = options.now ?? Date.now();
    let frameId = 0;
    class PageDate extends Date { static now() { return now; } }
    const motion = { matches: Boolean(options.reduced), addEventListener(_, callback) { this.change = callback; } };
    const root = {
        style: {
            setProperty: (name, value) => properties.set(name, value),
            getPropertyValue: name => properties.get(name) ?? '',
            removeProperty: name => properties.delete(name),
        },
        setAttribute: (name, value) => attributes.set(name, value),
        getAttribute: name => attributes.get(name),
        hasAttribute: name => attributes.has(name),
        removeAttribute: name => attributes.delete(name),
    };
    const location = new URL(path, 'http://127.0.0.1:8000');
    const storage = {
        getItem(name) { if (options.blockedStorage) throw new Error('Storage unavailable'); return stored.get(name) ?? null; },
        setItem(name, value) { if (options.blockedStorage) throw new Error('Storage unavailable'); stored.set(name, value); },
        removeItem(name) { if (options.blockedStorage) throw new Error('Storage unavailable'); stored.delete(name); },
    };
    const document = {
        documentElement: root,
        hidden: false,
        body: { getAttribute: name => name === 'data-authenticated' ? String(Boolean(options.authenticated)) : null },
        addEventListener: (name, callback) => documentEvents.set(name, callback),
    };
    const window = {
        location, sessionStorage: storage, matchMedia: () => motion,
        navigation: { activation: options.from ? { from: { url: new URL(options.from, location).href } } : null },
        addEventListener: (name, callback) => windowEvents.set(name, callback),
        setTimeout(callback) { const id = timers.size + 1; timers.set(id, callback); return id; },
        clearTimeout: id => timers.delete(id),
        requestAnimationFrame(callback) { const id = ++frameId; frames.set(id, callback); return id; },
        cancelAnimationFrame: id => frames.delete(id),
    };
    runInNewContext(script, { window, document, URL, Date: PageDate, Number, Boolean, JSON });
    return {
        root, stored, motion, timers, frames, document,
        frame(elapsed) {
            now += elapsed;
            const callbacks = [...frames.values()];
            frames.clear();
            for (const callback of callbacks) callback(now);
        },
        documentEvent: (name, event = {}) => documentEvents.get(name)?.(event),
        windowEvent: (name, event = {}) => windowEvents.get(name)?.(event),
        marker: () => stored.has(key) ? JSON.parse(stored.get(key)) : null,
    };
}

function marker(from = 'login', to = 'register', extra = {}) {
    return { from, to, kind: 'link', time: Date.now(), ...extra };
}

function click(href, extra = {}) {
    const link = {
        href: new URL(href, 'http://127.0.0.1:8000').href,
        target: extra.target ?? '',
        hasAttribute: name => name === 'download' && Boolean(extra.download),
    };
    return { button: 0, target: { closest: () => link }, ...extra };
}

function nativeTransition() {
    let finish;
    let readyResolve;
    let readyReject;
    let skips = 0;
    const transition = {
        ready: new Promise((resolve, reject) => { readyResolve = resolve; readyReject = reject; }),
        finished: new Promise(resolve => { finish = resolve; }),
        skipTransition() { skips += 1; readyReject(new Error('Skipped')); finish(); },
    };
    return { transition, finish, ready: () => readyResolve(), reject: readyReject, get skips() { return skips; } };
}

test('account links store only a short-lived screen intent, without intercepting navigation', () => {
    const current = page();
    const event = click('/register/');
    current.documentEvent('click', event);
    const saved = current.marker();
    assert.deepEqual(Object.keys(saved).sort(), ['from', 'kind', 'time', 'to']);
    assert.equal(saved.from, 'login');
    assert.equal(saved.to, 'register');
    assert.equal(saved.kind, 'link');
    assert.equal(event.defaultPrevented, undefined);
});

test('modified, cancelled, download and new-tab links keep native behavior', () => {
    for (const extra of [{ ctrlKey: true }, { metaKey: true }, { shiftKey: true }, { altKey: true },
        { defaultPrevented: true }, { button: 1 }, { target: '_blank' }, { download: true }]) {
        const current = page();
        current.documentEvent('click', click('/register/', extra));
        assert.equal(current.marker(), null);
    }
});

test('ordinary blog, same-screen, admin, logout and external links do not animate', () => {
    for (const [from, to] of [['/', '/article/example/'], ['/login/', '/login/?next=/'],
        ['/login/', 'https://example.org/'], ['/login/', '/admin/'], ['/login/', '/logout/']]) {
        const current = page(from);
        current.documentEvent('click', click(to));
        assert.equal(current.marker(), null);
    }
});

test('a valid arrival consumes its intent immediately and cleans the fallback', () => {
    const current = page('/register/', { marker: marker() });
    assert.equal(current.root.getAttribute('data-account-arrival'), 'reshape');
    assert.equal(current.marker(), null);
    current.documentEvent('DOMContentLoaded');
    for (const callback of [...current.timers.values()]) callback();
    assert.equal(current.root.hasAttribute('data-account-arrival'), false);
});

test('expired, future, malformed, wrong-destination and unknown intents are discarded', () => {
    for (const item of [marker('login', 'register', { time: Date.now() - 31000 }),
        marker('login', 'register', { time: Date.now() + 60000 }), marker('login', 'reset'),
        marker('unknown', 'register'), marker('login', 'register', { kind: 'credentials' }),
        marker('login', 'register', { kind: 'login-submit' })]) {
        const current = page('/register/', { marker: item });
        assert.equal(current.root.hasAttribute('data-account-arrival'), false);
        assert.equal(current.marker(), null);
    }
    assert.equal(page('/register/', { raw: '{broken json' }).marker(), null);
});

test('reduced motion disables recording, native transition and fallback', async () => {
    const current = page('/register/', { reduced: true, marker: marker(), from: '/login/' });
    current.documentEvent('click', click('/login/'));
    const native = nativeTransition();
    current.windowEvent('pagereveal', { viewTransition: native.transition });
    await Promise.resolve();
    assert.equal(native.skips, 1);
    assert.equal(current.marker(), null);
    assert.equal(current.root.hasAttribute('data-account-arrival'), false);
});

test('storage unavailable never prevents a link or a POST', () => {
    const current = page('/login/', { blockedStorage: true });
    assert.doesNotThrow(() => current.documentEvent('click', click('/register/')));
    assert.doesNotThrow(() => current.documentEvent('submit', { target: { id: 'login-form' } }));
});

test('only a non-cancelled login POST records a success destination', () => {
    const current = page();
    current.documentEvent('submit', { target: { id: 'register-form' } });
    assert.equal(current.marker(), null);
    current.documentEvent('submit', { target: { id: 'login-form' }, defaultPrevented: true });
    assert.equal(current.marker(), null);
    current.documentEvent('submit', { target: { id: 'login-form', password: 'NeverReadThis' } });
    assert.equal(current.marker().kind, 'login-submit');
    assert.equal(current.marker().to, 'site');
    assert.equal(JSON.stringify(current.marker()).includes('NeverReadThis'), false);
});

test('failed login stays on its form without a success reveal', () => {
    const current = page('/login/?next=/', { marker: marker('login', 'site', { kind: 'login-submit' }), from: '/login/' });
    assert.equal(current.root.hasAttribute('data-account-arrival'), false);
    current.documentEvent('DOMContentLoaded');
    assert.equal(current.root.hasAttribute('data-account-arrival'), false);
});

test('only an authenticated destination plays the login-success fallback, including next to an article', () => {
    const intent = marker('login', 'site', { kind: 'login-submit' });
    const success = page('/article/example/', { marker: intent, authenticated: true });
    success.documentEvent('DOMContentLoaded');
    assert.equal(success.root.getAttribute('data-account-arrival'), 'enter-site');
    const guest = page('/', { marker: intent });
    guest.documentEvent('DOMContentLoaded');
    assert.equal(guest.root.hasAttribute('data-account-arrival'), false);
    assert.equal(guest.root.hasAttribute('data-account-entered'), false);
});

test('a site reveal keeps its entrance marker after cleanup, so hero text does not enter twice', async () => {
    const current = page('/', { marker: marker('login', 'site'), from: '/login/' });
    assert.equal(current.root.getAttribute('data-account-entered'), 'site');
    const native = nativeTransition();
    current.windowEvent('pagereveal', { viewTransition: native.transition });
    native.ready();
    native.finish();
    await Promise.resolve();
    assert.equal(current.root.hasAttribute('data-account-transition'), false);
    assert.equal(current.root.getAttribute('data-account-entered'), 'site');
    current.windowEvent('pageshow', { persisted: true });
    assert.equal(current.root.getAttribute('data-account-entered'), 'site');
});

test('native entry configures static hero content even when session storage is unavailable', () => {
    const current = page('/', { blockedStorage: true, from: '/login/', authenticated: true });
    const native = nativeTransition();
    current.windowEvent('pagereveal', { viewTransition: native.transition });
    assert.equal(current.root.getAttribute('data-account-entered'), 'site');
    assert.equal(current.root.getAttribute('data-account-transition'), 'enter-site');
    native.ready();
    native.finish();
});

test('normal blog arrivals keep their original entrance animation', () => {
    const current = page('/');
    current.documentEvent('DOMContentLoaded');
    assert.equal(current.root.hasAttribute('data-account-entered'), false);
});

test('native reshape replaces fallback and releases its snapshot names after finishing', async () => {
    const current = page('/register/', { marker: marker(), from: '/login/' });
    const native = nativeTransition();
    current.windowEvent('pagereveal', { viewTransition: native.transition });
    assert.equal(current.root.getAttribute('data-account-transition'), 'reshape');
    assert.equal(current.root.getAttribute('data-account-from'), 'login');
    assert.equal(current.root.getAttribute('data-account-to'), 'register');
    assert.equal(current.root.hasAttribute('data-account-arrival'), false);
    native.ready();
    native.finish();
    await Promise.resolve();
    assert.equal(current.root.hasAttribute('data-account-transition'), false);
});

test('a native timeout or skip falls back to a gentle entrance without a loading curtain', async () => {
    const current = page('/register/', { marker: marker(), from: '/login/' });
    const native = nativeTransition();
    current.windowEvent('pagereveal', { viewTransition: native.transition });
    native.reject(new Error('Timeout'));
    native.finish();
    await Promise.resolve();
    assert.equal(current.root.getAttribute('data-account-arrival'), 'reshape');
    assert.equal(current.root.hasAttribute('data-account-transition'), false);
});

test('login preparation starts in the submit event without delaying or replacing the POST', () => {
    const current = page();
    const event = { target: { id: 'login-form' } };
    current.documentEvent('submit', event);
    assert.equal(current.root.getAttribute('data-login-departure'), 'verify');
    assert.equal(event.defaultPrevented, undefined);
    assert.equal(current.timers.size, 0);
    assert.equal(current.marker().kind, 'login-submit');
});

test('cancelled submissions and reduced motion never start departure effects', () => {
    const current = page();
    current.documentEvent('submit', { target: { id: 'login-form' }, defaultPrevented: true });
    assert.equal(current.root.hasAttribute('data-login-departure'), false);
    const reduced = page('/login/', { reduced: true });
    reduced.documentEvent('submit', { target: { id: 'login-form' } });
    reduced.documentEvent('click', click('/register/'));
    assert.equal(reduced.root.hasAttribute('data-login-departure'), false);
    assert.equal(reduced.root.hasAttribute('data-account-leaving'), false);
});

test('page restoration removes preparing states as well as native snapshots', () => {
    const current = page();
    current.documentEvent('submit', { target: { id: 'login-form' } });
    current.windowEvent('pageshow', { persisted: false });
    assert.equal(current.root.hasAttribute('data-login-departure'), false);
    current.documentEvent('click', click('/register/'));
    assert.equal(current.root.getAttribute('data-account-leaving'), 'reshape');
    current.windowEvent('pageshow', { persisted: true });
    assert.equal(current.root.hasAttribute('data-account-leaving'), false);
});

test('changing motion preference immediately cancels a login preparation', () => {
    const current = page();
    current.documentEvent('submit', { target: { id: 'login-form' } });
    current.motion.matches = true;
    current.motion.change();
    assert.equal(current.root.hasAttribute('data-login-departure'), false);
    assert.equal(current.frames.size, 0);
    assert.equal(current.root.style.getPropertyValue('--account-login-progress'), '');
});

test('waiting screen distance advances monotonically but never completes before a response', () => {
    const current = page();
    current.documentEvent('submit', { target: { id: 'login-form' } });
    let previous = 0;
    for (const elapsed of [100, 300, 800, -100, 5000, 60000]) {
        current.frame(elapsed);
        const progress = Number(current.root.style.getPropertyValue('--account-login-progress'));
        assert.ok(progress >= previous);
        assert.ok(progress <= 0.88);
        assert.ok(progress < 1);
        previous = progress;
    }
    assert.equal(current.root.hasAttribute('data-account-response'), false);
    assert.equal(current.root.hasAttribute('data-account-entered'), false);
    assert.equal(current.frames.size, 0, 'a very slow response stops the cosmetic RAF loop below completion');
});

test('page swap carries the last visible boundary and authentication alone unlocks the remaining reveal', async () => {
    const current = page();
    current.documentEvent('submit', { target: { id: 'login-form' } });
    current.frame(2400);
    const progress = Number(current.root.style.getPropertyValue('--account-login-progress'));
    const outgoing = nativeTransition();
    current.windowEvent('pageswap', {
        activation: { entry: { url: 'http://127.0.0.1:8000/article/example/' } },
        viewTransition: outgoing.transition,
    });
    const intent = current.marker();
    assert.deepEqual(Object.keys(intent).sort(), ['from', 'kind', 'progress', 'time', 'to']);
    assert.equal(intent.progress, progress);
    assert.equal(current.frames.size, 0);
    outgoing.ready();
    outgoing.finish();
    const arrival = page('/article/example/', { marker: intent, now: intent.time, from: '/login/', authenticated: true });
    const incoming = nativeTransition();
    arrival.windowEvent('pagereveal', { viewTransition: incoming.transition });
    assert.equal(arrival.root.getAttribute('data-account-response'), 'ready');
    assert.equal(arrival.root.style.getPropertyValue('--account-screen-start'), (progress * 100).toFixed(3) + 'vw');
    assert.equal(arrival.root.style.getPropertyValue('--account-screen-remaining'), ((1 - progress) * 100).toFixed(3) + '%');
    assert.ok(parseInt(arrival.root.style.getPropertyValue('--account-screen-duration'), 10) < 350);
    incoming.ready();
    incoming.finish();
    await Promise.resolve();
    assert.equal(arrival.root.hasAttribute('data-account-response'), false);
    assert.equal(arrival.root.style.getPropertyValue('--account-screen-duration'), '');
    assert.equal(arrival.root.getAttribute('data-account-entered'), 'site');
});

test('fast responses keep a leisurely reveal, long responses finish only the short remaining segment', () => {
    for (const [progress, duration] of [[0, '900ms'], [0.4, '540ms'], [0.88, '180ms']]) {
        const current = page('/', { authenticated: true,
            marker: marker('login', 'site', { kind: 'login-submit', progress }) });
        current.documentEvent('DOMContentLoaded');
        assert.equal(current.root.style.getPropertyValue('--account-screen-duration'), duration);
        for (const callback of [...current.timers.values()]) callback();
        assert.equal(current.root.hasAttribute('data-account-response'), false);
    }
});

test('failed authentication never resumes or completes a progress-linked reveal', async () => {
    const current = page('/', { marker: marker('login', 'site', { kind: 'login-submit', progress: 0.8 }), from: '/login/' });
    const native = nativeTransition();
    current.windowEvent('pagereveal', { viewTransition: native.transition });
    current.documentEvent('DOMContentLoaded');
    await Promise.resolve();
    assert.equal(native.skips, 1);
    assert.equal(current.root.hasAttribute('data-account-response'), false);
    assert.equal(current.root.style.getPropertyValue('--account-screen-remaining'), '');
});

test('invalid saved progress cannot inject CSS or bypass the incomplete waiting limit', () => {
    for (const progress of [-1, 1, 99, '0; color: red', null]) {
        const current = page('/', { authenticated: true,
            marker: marker('login', 'site', { kind: 'login-submit', progress }) });
        current.documentEvent('DOMContentLoaded');
        assert.match(current.root.style.getPropertyValue('--account-screen-start'), /^\d+\.\d{3}vw$/);
        assert.ok(parseFloat(current.root.style.getPropertyValue('--account-screen-start')) <= 88);
    }
});

test('native failure navigation clears the stored boundary and never intercepts the POST', () => {
    const current = page();
    const submit = { target: { id: 'login-form' } };
    current.documentEvent('submit', submit);
    current.frame(1500);
    current.windowEvent('pageswap', { activation: { entry: { url: 'http://127.0.0.1:8000/login/?next=/' } } });
    assert.equal(submit.defaultPrevented, undefined);
    assert.equal(current.marker(), null);
    assert.equal(current.frames.size, 0);
});

test('hidden tabs suspend animation and resume at the elapsed position without new requests', () => {
    const current = page();
    current.documentEvent('submit', { target: { id: 'login-form' } });
    current.frame(300);
    const before = Number(current.root.style.getPropertyValue('--account-login-progress'));
    current.document.hidden = true;
    current.documentEvent('visibilitychange');
    assert.equal(current.frames.size, 0);
    current.frame(2000);
    current.document.hidden = false;
    current.documentEvent('visibilitychange');
    assert.ok(Number(current.root.style.getPropertyValue('--account-login-progress')) > before);
    current.windowEvent('pagehide');
    assert.equal(current.frames.size, 0);
});

test('another account link and BFCache restoration cancel the previous login movement', () => {
    for (const restore of [false, true]) {
        const current = page();
        current.documentEvent('submit', { target: { id: 'login-form' } });
        current.frame(900);
        if (restore) current.windowEvent('pageshow', { persisted: true });
        else current.documentEvent('click', click('/register/'));
        assert.equal(current.root.hasAttribute('data-login-departure'), false);
        assert.equal(current.root.style.getPropertyValue('--account-wipe-position'), '');
        assert.equal(current.frames.size, 0);
        assert.equal(current.marker()?.kind === 'login-submit', false);
    }
});

test('native same-page validation and ordinary article navigation are skipped', async () => {
    for (const [path, from] of [['/login/', '/login/'], ['/article/example/', '/']]) {
        const current = page(path, { from });
        const native = nativeTransition();
        current.windowEvent('pagereveal', { viewTransition: native.transition });
        await Promise.resolve();
        assert.equal(native.skips, 1);
    }
});

test('outgoing native snapshots are configured before page swap', async () => {
    const current = page('/login/');
    const native = nativeTransition();
    current.windowEvent('pageswap', {
        activation: { entry: { url: 'http://127.0.0.1:8000/forget_password/' } },
        viewTransition: native.transition,
    });
    assert.equal(current.root.getAttribute('data-account-to'), 'reset');
    native.reject(new Error('Old document ready promise'));
    native.finish();
    await Promise.resolve();
    assert.equal(current.root.hasAttribute('data-account-transition'), false);
});

test('BFCache restoration and changing reduced-motion preference clear stale visual state', () => {
    for (const usePreference of [false, true]) {
        const current = page('/register/', { marker: marker() });
        if (usePreference) {
            current.motion.matches = true;
            current.motion.change();
        } else {
            current.windowEvent('pageshow', { persisted: true });
        }
        assert.equal(current.root.hasAttribute('data-account-arrival'), false);
        assert.equal(current.root.hasAttribute('data-account-transition'), false);
        assert.equal(current.marker(), null);
    }
});
