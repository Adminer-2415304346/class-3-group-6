/** SZX：登录切屏与右侧共用流动背景，模拟 Canvas 和观察器，不读取凭据或连接网络。 */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { afterEach, beforeEach, test } from 'node:test';
import { createAccountFlow } from '../src/components/accountFlow.js';

const original = {};
const globals = ['window', 'document', 'getComputedStyle', 'ResizeObserver', 'IntersectionObserver', 'MutationObserver'];

beforeEach(() => { for (const name of globals) original[name] = globalThis[name]; });
afterEach(() => {
    for (const name of globals) {
        if (original[name] === undefined) delete globalThis[name];
        else globalThis[name] = original[name];
    }
});

function fakeCanvas() {
    const state = { clears: 0, strokes: [], circles: [], path: [], circle: null, transforms: [] };
    const context = {
        clearRect() { state.clears += 1; state.strokes = []; state.circles = []; },
        beginPath() { state.path = []; state.circle = null; },
        moveTo(x, y) { state.path.push([x, y]); },
        lineTo(x, y) { state.path.push([x, y]); },
        stroke() { state.strokes.push({ points: [...state.path], color: this.strokeStyle }); },
        arc(x, y, radius) { state.circle = [x, y, radius]; },
        fill() { if (state.circle) state.circles.push({ point: state.circle, color: this.fillStyle }); },
        fillRect() {},
        createRadialGradient() { return { addColorStop() {} }; },
        setTransform(...args) { state.transforms.push(args); },
    };
    return { state, context, style: {}, getContext: () => context };
}

function scene({ mobile = false, reduced = false, missingContext = false } = {}) {
    const attrs = new Map([['data-theme', 'light']]);
    const frames = new Map();
    const windowEvents = new Map();
    const documentEvents = new Map();
    const hostEvents = new Map();
    const observers = {};
    let id = 0;
    const root = { hasAttribute: name => attrs.has(name), getAttribute: name => attrs.get(name) ?? null };
    globalThis.document = {
        documentElement: root, hidden: false,
        addEventListener: (name, callback) => documentEvents.set(name, callback),
        removeEventListener: name => documentEvents.delete(name),
    };
    const motion = {
        matches: reduced,
        addEventListener(_, callback) { this.change = callback; },
        removeEventListener() { this.change = null; },
    };
    globalThis.window = {
        innerWidth: mobile ? 390 : 1280, innerHeight: mobile ? 844 : 720, devicePixelRatio: 3,
        requestAnimationFrame(callback) { const next = ++id; frames.set(next, callback); return next; },
        cancelAnimationFrame: frame => frames.delete(frame),
        matchMedia: () => motion,
        addEventListener: (name, callback) => windowEvents.set(name, callback),
        removeEventListener: name => windowEvents.delete(name),
    };
    globalThis.getComputedStyle = () => ({ getPropertyValue: name => ({
        '--primary': '124 58 237', '--foreground': '24 24 27', '--background': '255 255 255',
    })[name] });
    for (const [name, kind] of [['ResizeObserver', 'size'], ['IntersectionObserver', 'intersection'], ['MutationObserver', 'root']]) {
        globalThis[name] = class {
            constructor(callback) { this.callback = callback; observers[kind] = this; }
            observe() { this.connected = true; }
            disconnect() { this.connected = false; }
        };
    }
    const bounds = mobile ? { left: 0, top: 0, width: 0, height: 0 }
        : { left: 384, top: 0, width: 896, height: 720 };
    const host = {
        getBoundingClientRect: () => ({ ...bounds }),
        addEventListener: (name, callback) => hostEvents.set(name, callback),
        removeEventListener: name => hostEvents.delete(name),
    };
    const main = fakeCanvas();
    const wipe = fakeCanvas();
    if (missingContext) wipe.getContext = () => null;
    const controller = createAccountFlow(main, host, wipe);
    if (mobile) observers.intersection.callback([{ isIntersecting: false }]);
    return {
        main, wipe, controller, frames, motion, observers, attrs, windowEvents, documentEvents, hostEvents,
        activate(active) {
            if (active) attrs.set('data-login-departure', 'verify');
            else attrs.delete('data-login-departure');
            observers.root.callback();
        },
        tick(now) {
            const callbacks = [...frames.values()]; frames.clear();
            for (const callback of callbacks) callback(now);
        },
    };
}

test('idle scene leaves the wipe unpainted and uses one animation loop when activated', () => {
    const current = scene();
    assert.equal(current.wipe.state.clears, 0);
    assert.equal(current.frames.size, 1);
    current.activate(true);
    assert.equal(current.frames.size, 1);
    assert.equal(current.wipe.width, 2560, 'retina backing buffer is capped at two times the viewport');
    assert.equal(current.wipe.height, 1440);
    const before = current.wipe.state.clears;
    current.tick(100);
    assert.equal(current.wipe.state.clears, before + 1);
    assert.equal(current.frames.size, 1);
    current.activate(false);
    current.tick(116);
    assert.equal(current.wipe.state.clears, before + 1);
    current.controller.destroy();
});

test('extended paths line up with the right-hand paths in the same frame rather than stretching a bitmap', () => {
    const current = scene();
    current.activate(true);
    current.tick(100);
    for (let index = 0; index < current.main.state.strokes.length; index += 1) {
        const source = current.main.state.strokes[index];
        const extended = current.wipe.state.strokes[index];
        assert.equal(source.color, extended.color);
        for (const [x, y] of source.points) {
            const match = extended.points.find(point => point[0] === x + 384);
            assert.ok(match);
            assert.ok(Math.abs(match[1] - y) < 0.00001);
        }
        assert.ok(extended.points.some(point => point[0] < 384), 'new left region contains actual paths');
    }
    for (const marker of current.main.state.circles) {
        const [x, y, radius] = marker.point;
        assert.ok(current.wipe.state.circles.some(({ point, color }) =>
            Math.abs(point[0] - x - 384) < 0.00001 && point[1] === y && point[2] === radius && color === marker.color));
    }
    assert.ok(current.wipe.state.circles.some(({ point }) => point[0] >= 0 && point[0] < 384));
    current.controller.destroy();
});

test('flowing points keep moving after the waiting screen reaches its cosmetic limit', () => {
    const current = scene();
    current.activate(true);
    current.tick(100);
    const previous = current.wipe.state.circles[0].point[0];
    current.tick(116);
    assert.notEqual(current.wipe.state.circles[0].point[0], previous);
    assert.equal(current.frames.size, 1);
    current.controller.destroy();
});

test('mobile draws the waiting background even though the original scene is hidden', () => {
    const current = scene({ mobile: true });
    assert.equal(current.frames.size, 0);
    current.activate(true);
    current.tick(100);
    assert.equal(current.frames.size, 1);
    assert.equal(current.wipe.width, 780);
    assert.equal(current.wipe.height, 1688);
    assert.ok(current.wipe.state.strokes.length >= 7);
    assert.ok(current.wipe.state.circles.length >= 10);
    current.activate(false);
    assert.equal(current.frames.size, 0);
    current.controller.destroy();
});

test('pause and reduced-motion settings affect both surfaces together', () => {
    const current = scene();
    current.activate(true);
    assert.equal(current.controller.setPaused(true), true);
    assert.equal(current.frames.size, 0);
    assert.equal(current.controller.setPaused(false), false);
    assert.equal(current.frames.size, 1);
    current.motion.change({ matches: true });
    assert.equal(current.frames.size, 0);
    current.activate(false);
    current.activate(true);
    assert.equal(current.frames.size, 0);
    current.motion.change({ matches: false });
    assert.equal(current.frames.size, 1);
    current.controller.destroy();
});

test('hidden tabs suspend rendering, resizing updates the active viewport and destroy releases observers', () => {
    const current = scene({ mobile: true });
    current.activate(true);
    document.hidden = true;
    current.documentEvents.get('visibilitychange')();
    assert.equal(current.frames.size, 0);
    document.hidden = false;
    current.documentEvents.get('visibilitychange')();
    assert.equal(current.frames.size, 1);
    window.innerWidth = 375; window.innerHeight = 812;
    current.windowEvents.get('resize')();
    assert.equal(current.wipe.width, 750);
    assert.equal(current.wipe.height, 1624);
    current.controller.destroy();
    assert.equal(current.frames.size, 0);
    assert.equal(current.windowEvents.size, 0);
    assert.equal(current.documentEvents.size, 0);
    assert.equal(current.hostEvents.size, 0);
    assert.ok(Object.values(current.observers).every(observer => !observer.connected));
    const before = current.wipe.state.clears;
    current.observers.root.callback();
    assert.equal(current.wipe.state.clears, before);
});

test('missing optional Canvas support never prevents the original scene from rendering', () => {
    const current = scene({ missingContext: true });
    current.activate(true);
    current.tick(100);
    assert.ok(current.main.state.strokes.length >= 7);
    assert.equal(current.wipe.state.clears, 0);
    current.controller.destroy();
});

test('the swept surface is opaque and its canvas cancels the boundary movement', () => {
    const css = readFileSync(new URL('../src/styles/accountTransitions.css', import.meta.url), 'utf8');
    assert.match(css, /\.account-entry-fold\s*\{[^}]*background: rgb\(var\(--muted\)\);/);
    assert.doesNotMatch(css, /\.account-entry-fold\s*\{[^}]*background: rgb\(var\(--background\) \/ 0\.9\)/);
    assert.match(css, /\.account-entry-flow\s*\{[^}]*translateX\(calc\(100% - var\(--account-wipe-position, 0vw\)\)\)/);
    assert.doesNotMatch(css, /animation: account-scene-focus/);
});
