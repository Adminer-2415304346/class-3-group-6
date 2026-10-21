/** SZX：验证码状态测试用模拟网络，不发送邮件或更改真实账号。 */
import assert from 'node:assert/strict';
import { afterEach, beforeEach, test } from 'node:test';
import launcherAccount from '../src/components/launcherAccount.js';

let originalWindow;
let originalFetch;
let state;
let calls;
let clearedIntervals;
let removedListeners;

beforeEach(() => {
    originalWindow = globalThis.window;
    originalFetch = globalThis.fetch;
    calls = [];
    clearedIntervals = [];
    removedListeners = [];
    globalThis.window = {
        addEventListener() {},
        removeEventListener: (...args) => removedListeners.push(args),
        setTimeout: () => 10,
        clearTimeout() {},
        setInterval: () => 20,
        clearInterval: id => clearedIntervals.push(id),
    };
    globalThis.fetch = async (url, options) => {
        calls.push({ url, options });
        return { ok: true, text: async () => 'ok' };
    };
    state = launcherAccount();
    state.$refs = {
        email: { value: 'reader@example.org', checkValidity: () => true, reportValidity() {}, focus() {} },
        form: {
            dataset: { codeUrl: '/forget_password_code/' },
            querySelector: () => ({ value: 'test-csrf-token' }),
            querySelectorAll: () => [{ validity: { valid: false } }],
        },
    };
    state.$nextTick = callback => callback();
    state.$root = { querySelector: () => null };
});

afterEach(() => {
    globalThis.window = originalWindow;
    globalThis.fetch = originalFetch;
});

test('success posts CSRF to the existing endpoint then starts the cooldown', async () => {
    await state.sendCode();
    assert.equal(calls.length, 1);
    const { url, options } = calls[0];
    assert.equal(url, '/forget_password_code/');
    assert.equal(options.method, 'POST');
    assert.equal(options.credentials, 'same-origin');
    assert.equal(options.headers['X-CSRFToken'], 'test-csrf-token');
    assert.equal(new URLSearchParams(options.body).get('email'), 'reader@example.org');
    assert.equal(new URLSearchParams(options.body).get('csrfmiddlewaretoken'), 'test-csrf-token');
    assert.equal(state.codeRemaining, 60);
    assert.ok(state.codeMessage.includes('已发送'));
    assert.equal(state.codeError, '');
    assert.equal(state.codeSending, false);
    await state.sendCode();
    assert.equal(calls.length, 1);
});

test('invalid email does not send a request or claim success', async () => {
    state.$refs.email.checkValidity = () => false;
    await state.sendCode();
    assert.equal(calls.length, 0);
    assert.ok(state.codeError.includes('有效'));
    assert.equal(state.codeMessage, '');
    assert.equal(state.codeRemaining, 0);
});

test('missing CSRF does not send a request', async () => {
    state.$refs.form.querySelector = () => null;
    await state.sendCode();
    assert.equal(calls.length, 0);
    assert.ok(state.codeError.includes('刷新'));
});

test('HTTP errors and backend validation errors remain retryable', async () => {
    for (const response of [
        { ok: false, text: async () => '<html>403 Forbidden</html>' },
        { ok: true, text: async () => '错误的邮箱' },
    ]) {
        globalThis.fetch = async () => response;
        await state.sendCode();
        assert.notEqual(state.codeError, '');
        assert.equal(state.codeMessage, '');
        assert.equal(state.codeRemaining, 0);
        assert.equal(state.codeSending, false);
    }
    globalThis.fetch = async () => ({ ok: true, text: async () => 'ok' });
    await state.sendCode();
    assert.equal(state.codeError, '');
    assert.equal(state.codeRemaining, 60);
});

test('network failure and timeout show inline errors without a cooldown', async () => {
    for (const name of ['TypeError', 'AbortError']) {
        globalThis.fetch = async () => { throw Object.assign(new Error('test failure'), { name }); };
        await state.sendCode();
        assert.notEqual(state.codeError, '');
        assert.equal(state.codeMessage, '');
        assert.equal(state.codeRemaining, 0);
        assert.equal(state.codeSending, false);
    }
});

test('in-flight duplicate requests are suppressed', async () => {
    let resolveRequest;
    globalThis.fetch = () => {
        calls.push('sent');
        return new Promise(resolve => { resolveRequest = resolve; });
    };
    const request = state.sendCode();
    assert.equal(state.codeSending, true);
    await state.sendCode();
    assert.equal(calls.length, 1);
    resolveRequest({ ok: true, text: async () => 'ok' });
    await request;
    assert.equal(state.codeSending, false);
});

test('expired cooldown clears its timer and permits resending', async () => {
    await state.sendCode();
    state.codeDeadline = Date.now() - 1;
    state.updateCooldown();
    assert.equal(state.codeRemaining, 0);
    assert.equal(state.codeTimer, null);
    assert.deepEqual(clearedIntervals, [20]);
    await state.sendCode();
    assert.equal(calls.length, 2);
});

test('native submission blocks duplicates and bfcache return unlocks it', () => {
    state.init();
    let prevented = 0;
    const event = { preventDefault: () => { prevented += 1; } };
    state.submit(event);
    assert.equal(prevented, 0);
    state.submit(event);
    assert.equal(prevented, 1);
    state.onPageShow();
    assert.equal(state.submitting, false);
    state.$refs.form.querySelectorAll = () => [{ validity: { valid: true } }];
    state.syncFields();
    assert.equal(state.ready, true);
});

test('destroy removes listeners, clears timers and aborts the outstanding request', () => {
    state.init();
    state.codeTimer = 20;
    const controller = new AbortController();
    state.codeController = controller;
    state.destroy();
    assert.equal(controller.signal.aborted, true);
    assert.deepEqual(clearedIntervals, [20]);
    assert.equal(removedListeners[0][0], 'pageshow');
});
