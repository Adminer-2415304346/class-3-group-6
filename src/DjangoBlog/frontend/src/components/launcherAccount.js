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
            const result = (await response.text()).trim();
            if (this.destroyed) return;
            if (!response.ok || result !== 'ok') {
                this.codeError = result === '错误的邮箱'
                    ? '邮箱格式不正确，请检查后重试。'
                    : '验证码发送失败，请稍后重试。';
                return;
            }
            // 只有后台确认成功才显示“已发送”，失败后可立即重试。
            this.codeMessage = '验证码已发送，请检查邮箱。';
            this.codeDeadline = Date.now() + 60000;
            this.updateCooldown();
            this.codeTimer = window.setInterval(() => this.updateCooldown(), 1000);
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
