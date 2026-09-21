/**
 * 导航栏组件
 * 处理移动端菜单、搜索等交互
 */

export default () => ({
  // ==================== 状态 ====================
  menuOpen: false,
  windowWidth: window.innerWidth,
  isSearchOpen: false,
  searchQuery: '',

  // ==================== 初始化 ====================
  init() {
    console.log('🧭 Navigation Initialized');

    // 监听窗口大小变化
    window.addEventListener('resize', () => {
      this.windowWidth = window.innerWidth;
      if (window.innerWidth >= 768 && this.menuOpen) {
        this.menuOpen = false;
        document.body.style.overflow = '';
      }
    });

    // 监听HTMX导航事件，自动关闭移动端菜单
    document.body.addEventListener('htmx:beforeRequest', (event) => {
      // 如果是导航链接触发的请求，并且在移动端模式，则关闭菜单
      if (this.windowWidth < 768 && this.menuOpen) {
        console.log('🔗 HTMX navigation detected, closing mobile menu');
        this.closeMobileMenu();
      }
    });
  },

  // ==================== 移动端菜单 ====================
  toggleMenu() {
    this.menuOpen = !this.menuOpen;

    // 移动端防止背景滚动
    if (this.windowWidth < 768) {
      if (this.menuOpen) {
        document.body.style.overflow = 'hidden';
      } else {
        document.body.style.overflow = '';
      }
    }

    console.log('📱 Mobile menu:', this.menuOpen ? 'opened' : 'closed');
  },

  closeMobileMenu() {
    this.menuOpen = false;
    document.body.style.overflow = '';
  },

  // ==================== 搜索功能 ====================
  toggleSearch() {
    this.isSearchOpen = !this.isSearchOpen;

    if (this.isSearchOpen) {
      // 聚焦到搜索框
      this.$nextTick(() => {
        this.$refs.searchInput?.focus();
      });
    }

    console.log('🔍 Search:', this.isSearchOpen ? 'opened' : 'closed');
  },

  submitSearch() {
    if (this.searchQuery.trim()) {
      window.location.href = `/search/?q=${encodeURIComponent(this.searchQuery)}`;
    }
  },

  // ==================== 主题切换 ====================
  // 统一走 base.html 里内联脚本的 window.themeManager：
  // 它负责 data-theme / .dark / localStorage('dark-mode-enabled') / theme-color meta，
  // 并且只在切换的 260ms 内挂 data-theme-anim 让颜色平滑过渡。
  //
  // 这里原来是自己 setAttribute + 写 localStorage.setItem('theme', ...)：
  //   - 存的键和另外两处（'dark-mode-enabled'）不一致，刷新后两边打架；
  //   - 漏了 .dark class、theme-color meta，也没挂过渡标记，所以切换时样式会"跳/卡"。
  toggleTheme() {
    if (window.themeManager && typeof window.themeManager.toggle === 'function') {
      window.themeManager.toggle();
      return;
    }
    // 兜底（内联脚本未执行时不至于点了没反应）
    const html = document.documentElement;
    const isDark = html.getAttribute('data-theme') === 'dark';
    if (isDark) {
      html.removeAttribute('data-theme');
      html.classList.remove('dark');
    } else {
      html.setAttribute('data-theme', 'dark');
      html.classList.add('dark');
    }
    try {
      localStorage.setItem('dark-mode-enabled', isDark ? 'light' : 'dark');
    } catch (e) { /* 隐私模式忽略 */ }
  },
});
