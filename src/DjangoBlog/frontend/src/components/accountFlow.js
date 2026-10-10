const TAU = Math.PI * 2;

function parseColor(value, fallback) {
    const channels = String(value || '')
        .trim()
        .split(/\s+/)
        .map(Number)
        .filter(Number.isFinite);

    return channels.length >= 3 ? channels.slice(0, 3) : fallback;
}

function rgba(channels, alpha) {
    return `rgba(${channels[0]}, ${channels[1]}, ${channels[2]}, ${alpha})`;
}

/** SZX：登录页和已扫过的区域共用时间、曲线、光点及暂停状态；不新建第二条动画循环。 */
export function createAccountFlow(canvas, host, wipeCanvas = null) {
    const context = canvas.getContext('2d', { alpha: true, desynchronized: true });
    if (!context) return { destroy() {} };

    const motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    let prefersReducedMotion = motionQuery.matches;
    let width = 1;
    let height = 1;
    let frameId = 0;
    let visible = true;
    let destroyed = false;
    let manuallyPaused = false;
    let elapsed = 0;
    let lastFrame = 0;
    let bounds = null;
    const wipeContext = wipeCanvas?.getContext('2d', { alpha: true, desynchronized: true });
    let wipeActive = false;
    let wipeWidth = 1;
    let wipeHeight = 1;
    let palette = {
        primary: [124, 58, 237],
        foreground: [24, 24, 27],
        surface: [255, 255, 255],
        dark: false,
    };
    const pointer = { x: 0.58, y: 0.48, targetX: 0.58, targetY: 0.48, active: false };

    function updatePalette() {
        const styles = getComputedStyle(host);
        palette = {
            primary: parseColor(styles.getPropertyValue('--primary'), [124, 58, 237]),
            foreground: parseColor(styles.getPropertyValue('--foreground'), [24, 24, 27]),
            surface: parseColor(styles.getPropertyValue('--background'), [255, 255, 255]),
            dark: document.documentElement.getAttribute('data-theme') === 'dark',
        };
    }

    function streamY(index, x, time, streamCount) {
        const base = ((index + 1) / (streamCount + 1)) * height;
        const amplitude = Math.max(15, Math.min(42, height * (0.035 + (index % 3) * 0.008)));
        const phase = index * 0.73;
        const wave = Math.sin(x * 0.007 + time * 0.00034 + phase) * amplitude
            + Math.sin(x * 0.0028 - time * 0.00017 + phase * 1.8) * amplitude * 0.42;
        let y = base + wave;

        if (pointer.active && !prefersReducedMotion) {
            const pointerX = pointer.x * width;
            const pointerY = pointer.y * height;
            const distanceX = x - pointerX;
            const influence = Math.exp(-(distanceX * distanceX) / Math.max(1, width * width * 0.035));
            y += (pointerY - y) * influence * 0.18;
        }

        return y;
    }

    function drawSurface(target, targetWidth, targetHeight, time, extended = false) {
        target.clearRect(0, 0, targetWidth, targetHeight);
        // 右侧曲线向左延伸，而不是把一张小画布拉伸或平铺；边界两侧的线条处在同一坐标和相位。
        const offsetX = extended && bounds?.width > 0 ? -bounds.left : 0;
        const offsetY = extended && bounds?.height > 0 ? bounds.top : 0;

        if (pointer.active && !prefersReducedMotion) {
            const halo = target.createRadialGradient(
                pointer.x * width - offsetX,
                pointer.y * height + offsetY,
                0,
                pointer.x * width - offsetX,
                pointer.y * height + offsetY,
                Math.max(width, height) * 0.28,
            );
            halo.addColorStop(0, rgba(palette.primary, palette.dark ? 0.13 : 0.09));
            halo.addColorStop(1, rgba(palette.primary, 0));
            target.fillStyle = halo;
            target.fillRect(0, 0, targetWidth, targetHeight);
        }

        const streamCount = Math.max(7, Math.min(12, Math.round(height / 76)));
        const step = Math.max(18, Math.round(width / 52));
        target.lineCap = 'round';
        target.lineJoin = 'round';

        for (let index = 0; index < streamCount; index += 1) {
            const isAccent = index % 4 === 1;
            target.beginPath();
            // 采样网格也沿用源画布的原点，避免两侧折线在接缝处产生可见错位。
            const firstX = Math.floor(offsetX / step) * step - step;
            for (let sourceX = firstX; sourceX <= targetWidth + offsetX + step; sourceX += step) {
                const x = sourceX - offsetX;
                const y = streamY(index, sourceX, time, streamCount) + offsetY;
                if (sourceX === firstX) target.moveTo(x, y);
                else target.lineTo(x, y);
            }
            target.strokeStyle = isAccent
                ? rgba(palette.primary, palette.dark ? 0.24 : 0.18)
                : rgba(palette.foreground, palette.dark ? 0.10 : 0.075);
            target.lineWidth = isAccent ? 1.35 : 1;
            target.stroke();
        }

        const markerCount = Math.max(10, Math.min(22, Math.round(width / 45)));
        for (let marker = 0; marker < markerCount; marker += 1) {
            const streamIndex = marker % streamCount;
            const speed = 0.000012 + (marker % 5) * 0.0000025;
            const progress = (time * speed + marker * 0.117) % 1;
            const radius = 1.4 + (marker % 3) * 0.7;
            // 左侧延伸同一组光点轨迹；右侧范围内的光点与源画布完全一致。
            const firstCycle = extended ? -Math.ceil(Math.max(0, -offsetX) / (width + 80)) : 0;
            for (let cycle = firstCycle; cycle <= 0; cycle += 1) {
                const sourceX = progress * (width + 80) - 40 + cycle * (width + 80);
                const x = sourceX - offsetX;
                if (x < -40 || x > targetWidth + 40) continue;
                const y = streamY(streamIndex, sourceX, time, streamCount) + offsetY;
                target.beginPath();
                target.arc(x, y, radius, 0, TAU);
                target.fillStyle = rgba(
                    marker % 3 === 0 ? palette.primary : palette.foreground,
                    marker % 3 === 0 ? (palette.dark ? 0.78 : 0.66) : (palette.dark ? 0.34 : 0.24),
                );
                target.fill();
            }
        }
    }

    function draw(time) {
        if (destroyed) return;
        pointer.x += (pointer.targetX - pointer.x) * 0.075;
        pointer.y += (pointer.targetY - pointer.y) * 0.075;
        if (visible) drawSurface(context, width, height, time);
        if (wipeActive && wipeContext) drawSurface(wipeContext, wipeWidth, wipeHeight, time, true);
    }

    function scheduleFrame() {
        if (destroyed || frameId || (!visible && !wipeActive) || manuallyPaused || prefersReducedMotion || document.hidden) return;
        frameId = window.requestAnimationFrame(renderFrame);
    }

    function renderFrame(now) {
        frameId = 0;
        if (destroyed || (!visible && !wipeActive) || manuallyPaused || prefersReducedMotion || document.hidden) return;
        const delta = lastFrame ? Math.min(40, now - lastFrame) : 16;
        lastFrame = now;
        elapsed += delta;
        draw(elapsed);
        scheduleFrame();
    }

    function resize() {
        if (destroyed) return;
        bounds = host.getBoundingClientRect();
        // 手机版默认隐藏右侧场景，但登录推进时仍要画出相同的流动背景。
        width = Math.max(1, Math.round(bounds.width || window.innerWidth));
        height = Math.max(1, Math.round(bounds.height || window.innerHeight));
        const pixelRatio = Math.min(2, window.devicePixelRatio || 1);
        canvas.width = Math.round(width * pixelRatio);
        canvas.height = Math.round(height * pixelRatio);
        canvas.style.width = `${width}px`;
        canvas.style.height = `${height}px`;
        context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
        updatePalette();
        if (wipeActive) resizeWipe();
        draw(prefersReducedMotion ? 0 : elapsed);
        scheduleFrame();
    }

    function resizeWipe() {
        if (!wipeContext) return;
        wipeWidth = Math.max(1, window.innerWidth);
        wipeHeight = Math.max(1, window.innerHeight);
        const pixelRatio = Math.min(2, window.devicePixelRatio || 1);
        wipeCanvas.width = Math.round(wipeWidth * pixelRatio);
        wipeCanvas.height = Math.round(wipeHeight * pixelRatio);
        wipeContext.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
    }

    function handleWindowResize() {
        if (!wipeActive) return;
        resize();
    }

    function handleRootChange() {
        if (destroyed) return;
        const nextActive = Boolean(wipeContext && document.documentElement.hasAttribute('data-login-departure'));
        if (nextActive && !wipeActive) resizeWipe();
        wipeActive = nextActive;
        updatePalette();
        draw(prefersReducedMotion ? 0 : elapsed);
        if (!visible && !wipeActive && frameId) {
            window.cancelAnimationFrame(frameId);
            frameId = 0;
        }
        scheduleFrame();
    }

    function handlePointerMove(event) {
        if (event.pointerType === 'touch' || prefersReducedMotion || !bounds) return;
        pointer.active = true;
        pointer.targetX = Math.max(0, Math.min(1, (event.clientX - bounds.left) / width));
        pointer.targetY = Math.max(0, Math.min(1, (event.clientY - bounds.top) / height));
    }

    function handlePointerLeave() {
        pointer.active = false;
        pointer.targetX = 0.58;
        pointer.targetY = 0.48;
    }

    function handleMotionChange(event) {
        prefersReducedMotion = event.matches;
        if (frameId) {
            window.cancelAnimationFrame(frameId);
            frameId = 0;
        }
        lastFrame = 0;
        draw(prefersReducedMotion ? 0 : elapsed);
        scheduleFrame();
    }

    function handleVisibilityChange() {
        if (document.hidden && frameId) {
            window.cancelAnimationFrame(frameId);
            frameId = 0;
        } else {
            lastFrame = 0;
            scheduleFrame();
        }
    }

    const resizeObserver = new ResizeObserver(resize);
    const intersectionObserver = new IntersectionObserver(([entry]) => {
        visible = entry?.isIntersecting ?? true;
        if (!visible && !wipeActive && frameId) {
            window.cancelAnimationFrame(frameId);
            frameId = 0;
        }
        scheduleFrame();
    });
    const themeObserver = new MutationObserver(handleRootChange);

    resizeObserver.observe(host);
    intersectionObserver.observe(host);
    themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme', 'data-login-departure'] });
    host.addEventListener('pointermove', handlePointerMove, { passive: true });
    host.addEventListener('pointerleave', handlePointerLeave, { passive: true });
    document.addEventListener('visibilitychange', handleVisibilityChange);
    window.addEventListener('resize', handleWindowResize, { passive: true });
    if (motionQuery.addEventListener) motionQuery.addEventListener('change', handleMotionChange);
    else motionQuery.addListener(handleMotionChange);
    resize();
    handleRootChange();

    return {
        setPaused(paused) {
            manuallyPaused = Boolean(paused);
            if (manuallyPaused && frameId) {
                window.cancelAnimationFrame(frameId);
                frameId = 0;
            }
            if (!manuallyPaused) {
                lastFrame = 0;
                scheduleFrame();
            }
            return manuallyPaused;
        },
        destroy() {
            destroyed = true;
            if (frameId) window.cancelAnimationFrame(frameId);
            resizeObserver.disconnect();
            intersectionObserver.disconnect();
            themeObserver.disconnect();
            host.removeEventListener('pointermove', handlePointerMove);
            host.removeEventListener('pointerleave', handlePointerLeave);
            document.removeEventListener('visibilitychange', handleVisibilityChange);
            window.removeEventListener('resize', handleWindowResize);
            if (motionQuery.removeEventListener) motionQuery.removeEventListener('change', handleMotionChange);
            else motionQuery.removeListener(handleMotionChange);
        },
    };
}

export default function accountFlow() {
    return {
        controller: null,
        paused: false,
        init() {
            this.$nextTick(() => {
                if (this.$refs.canvas) {
                    const wipeCanvas = document.body.classList.contains('launcher-login-page')
                        ? document.querySelector('.account-entry-flow') : null;
                    this.controller = createAccountFlow(this.$refs.canvas, this.$el, wipeCanvas);
                }
            });
        },
        destroy() {
            this.controller?.destroy();
            this.controller = null;
        },
        toggleFlow() {
            if (this.controller) {
                this.paused = this.controller.setPaused(!this.paused);
            }
        },
    };
}
