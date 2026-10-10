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

function createAccountFlow(canvas, host) {
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

    function draw(time) {
        context.clearRect(0, 0, width, height);

        pointer.x += (pointer.targetX - pointer.x) * 0.075;
        pointer.y += (pointer.targetY - pointer.y) * 0.075;

        if (pointer.active && !prefersReducedMotion) {
            const halo = context.createRadialGradient(
                pointer.x * width,
                pointer.y * height,
                0,
                pointer.x * width,
                pointer.y * height,
                Math.max(width, height) * 0.28,
            );
            halo.addColorStop(0, rgba(palette.primary, palette.dark ? 0.13 : 0.09));
            halo.addColorStop(1, rgba(palette.primary, 0));
            context.fillStyle = halo;
            context.fillRect(0, 0, width, height);
        }

        const streamCount = Math.max(7, Math.min(12, Math.round(height / 76)));
        const step = Math.max(18, Math.round(width / 52));
        context.lineCap = 'round';
        context.lineJoin = 'round';

        for (let index = 0; index < streamCount; index += 1) {
            const isAccent = index % 4 === 1;
            context.beginPath();
            for (let x = -step; x <= width + step; x += step) {
                const y = streamY(index, x, time, streamCount);
                if (x === -step) context.moveTo(x, y);
                else context.lineTo(x, y);
            }
            context.strokeStyle = isAccent
                ? rgba(palette.primary, palette.dark ? 0.24 : 0.18)
                : rgba(palette.foreground, palette.dark ? 0.10 : 0.075);
            context.lineWidth = isAccent ? 1.35 : 1;
            context.stroke();
        }

        const markerCount = Math.max(10, Math.min(22, Math.round(width / 45)));
        for (let marker = 0; marker < markerCount; marker += 1) {
            const streamIndex = marker % streamCount;
            const speed = 0.000012 + (marker % 5) * 0.0000025;
            const progress = (time * speed + marker * 0.117) % 1;
            const x = progress * (width + 80) - 40;
            const y = streamY(streamIndex, x, time, streamCount);
            const radius = 1.4 + (marker % 3) * 0.7;

            context.beginPath();
            context.arc(x, y, radius, 0, TAU);
            context.fillStyle = rgba(
                marker % 3 === 0 ? palette.primary : palette.foreground,
                marker % 3 === 0 ? (palette.dark ? 0.78 : 0.66) : (palette.dark ? 0.34 : 0.24),
            );
            context.fill();
        }
    }

    function scheduleFrame() {
        if (destroyed || frameId || !visible || manuallyPaused || prefersReducedMotion || document.hidden) return;
        frameId = window.requestAnimationFrame(renderFrame);
    }

    function renderFrame(now) {
        frameId = 0;
        if (destroyed || !visible || manuallyPaused || document.hidden) return;
        const delta = lastFrame ? Math.min(40, now - lastFrame) : 16;
        lastFrame = now;
        elapsed += delta;
        draw(elapsed);
        scheduleFrame();
    }

    function resize() {
        bounds = host.getBoundingClientRect();
        width = Math.max(1, Math.round(bounds.width));
        height = Math.max(1, Math.round(bounds.height));
        const pixelRatio = Math.min(2, window.devicePixelRatio || 1);
        canvas.width = Math.round(width * pixelRatio);
        canvas.height = Math.round(height * pixelRatio);
        canvas.style.width = `${width}px`;
        canvas.style.height = `${height}px`;
        context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
        updatePalette();
        draw(prefersReducedMotion ? 0 : elapsed);
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
        if (!visible && frameId) {
            window.cancelAnimationFrame(frameId);
            frameId = 0;
        }
        scheduleFrame();
    });
    const themeObserver = new MutationObserver(() => {
        updatePalette();
        draw(prefersReducedMotion ? 0 : elapsed);
    });

    resizeObserver.observe(host);
    intersectionObserver.observe(host);
    themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    host.addEventListener('pointermove', handlePointerMove, { passive: true });
    host.addEventListener('pointerleave', handlePointerLeave, { passive: true });
    document.addEventListener('visibilitychange', handleVisibilityChange);
    if (motionQuery.addEventListener) motionQuery.addEventListener('change', handleMotionChange);
    else motionQuery.addListener(handleMotionChange);
    resize();

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
                    this.controller = createAccountFlow(this.$refs.canvas, this.$el);
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
