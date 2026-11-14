/** SZX：注册/找回密码的轻量交互；提交和密码校验仍由 Django 处理。 */
export default () => ({
    submitting: false,
    ready: false,
    codeSending: false,
    codeRemaining: 0,
    codeMessage: '',
    codeError: '',
    codeDeadline: 0,
    codeTimer: null,
    codeController: null,
    onPageShow: null,
    destroyed: false,

    init() {
        this.syncFields();
        this.onPageShow = () => {
            this.submitting = false;
            this.updateCooldown();
            this.syncFields();
        };
        window.addEventListener('pageshow', this.onPageShow);
        this.$nextTick(() => {
            this.syncFields();
            const error = this.$refs.errorSummary || this.$root.querySelector('[aria-invalid="true"]');
            error?.focus();
        });
    },

    syncFields() {
        // 不保存用户输入，仅检查控件状态，兼容浏览器自动填充。
        const fields = [...(this.$refs.form?.querySelectorAll('input:not([type="hidden"])') || [])];
        this.ready = fields.length > 0 && fields.every(field => field.validity.valid);
    },

    submit(event) {
        if (this.submitting) {
            event.preventDefault();
            return;
        }
        this.submitting = true;
    },

    updateCooldown() {
        this.codeRemaining = Math.max(0, Math.ceil((this.codeDeadline - Date.now()) / 1000));
        if (this.codeRemaining === 0 && this.codeTimer !== null) {
            window.clearInterval(this.codeTimer);
            this.codeTimer = null;
        }
    },

    // YFY（第9—10周）：倒计时只使用服务端 retry_after，不在客户端硬编码默认秒数。
    startCooldown(seconds) {
        const value = Number(seconds);
        if (!Number.isFinite(value) || value <= 0) return;
        this.codeDeadline = Date.now() + value * 1000;
        this.updateCooldown();
        if (this.codeTimer !== null) window.clearInterval(this.codeTimer);
        this.codeTimer = window.setInterval(() => this.updateCooldown(), 1000);
    },

    async sendCode() {
        if (this.codeSending || this.codeRemaining > 0) return;
        const email = this.$refs.email;
        const form = this.$refs.form;
        const token = form?.querySelector('input[name="csrfmiddlewaretoken"]')?.value;
        const url = form?.dataset.codeUrl;
        this.codeError = '';
        this.codeMessage = '';

        if (!email || !token || !url) {
            this.codeError = '页面加载不完整，请刷新后重试。';
            return;
        }
        if (!email.value.trim() || !email.checkValidity()) {
            this.codeError = '请先填写有效的注册邮箱。';
            email.reportValidity();
            email.focus();
            return;
        }

        this.codeSending = true;
        const controller = new AbortController();
        this.codeController = controller;
        const timeout = window.setTimeout(() => controller.abort(), 15000);
        try {
            const response = await fetch(url, {
                method: 'POST',
                mode: 'same-origin',
                credentials: 'same-origin',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
                    'X-CSRFToken': token,
                },
                body: new URLSearchParams({ email: email.value.trim(), csrfmiddlewaretoken: token }).toString(),
                signal: controller.signal,
            });
            let payload = null;
            try {
                payload = await response.json();
            } catch (error) {
                payload = null;
            }
            if (this.destroyed) return;
            if (!response.ok || !payload || payload.success !== true || payload.code !== 'sent') {
                const retryAfter = Number(payload?.retry_after);
                if (response.status === 429 || payload?.code === 'rate_limited') {
                    // 服务端已占用冷却：按真实剩余秒数锁定按钮，而不是本地固定 60 秒。
                    this.startCooldown(retryAfter);
                    this.codeError = Number.isFinite(retryAfter) && retryAfter > 0
                        ? `请求过于频繁，请在 ${Math.ceil(retryAfter)} 秒后重试。`
                        : '请求过于频繁，请稍后重试。';
                    return;
                }
                if (payload?.code === 'invalid_email') {
                    this.codeError = '邮箱格式不正确，请检查后重试。';
                    return;
                }
                if (payload?.code === 'delivery_unavailable') {
                    this.codeError = '邮件服务暂时不可用，请稍后重试。';
                    return;
                }
                this.codeError = payload?.message || '验证码发送失败，请稍后重试。';
                return;
            }
            // 只有后台确认成功才显示“已发送”，失败后可立即重试。
            this.codeMessage = payload.message || '验证码已发送，请检查邮箱。';
            this.startCooldown(payload.retry_after);
        } catch (error) {
            if (!this.destroyed) {
                this.codeError = error.name === 'AbortError'
                    ? '请求超时，请稍后重试。'
                    : '网络连接失败，请检查后重试。';
            }
        } finally {
            window.clearTimeout(timeout);
            this.codeSending = false;
            this.codeController = null;
        }
    },

    destroy() {
        this.destroyed = true;
        window.removeEventListener('pageshow', this.onPageShow);
        if (this.codeTimer !== null) window.clearInterval(this.codeTimer);
        this.codeController?.abort();
    },
});
