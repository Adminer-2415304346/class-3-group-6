/** SZX：登录页只增强表单反馈，不替代 Django 的验证、会话和跳转。 */
export default () => ({
    showPassword: false,
    submitting: false,
    ready: false,
    onPageShow: null,

    init() {
        this.syncFields();
        this.onPageShow = () => {
            this.submitting = false;
            this.showPassword = false;
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
        // 直接读取输入控件，兼容密码管理器；不把凭据另存到前端状态或本地存储。
        this.ready = Boolean(this.$refs.username?.value.trim() && this.$refs.password?.value);
    },

    submit(event) {
        if (this.submitting) {
            event.preventDefault();
            return;
        }
        this.submitting = true;
    },

    destroy() {
        window.removeEventListener('pageshow', this.onPageShow);
    },
});
