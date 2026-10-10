/** @type {import('tailwindcss').Config} */
export default {
  // 扫描这些文件以提取使用的CSS类
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
    "../templates/**/*.html",
    "../blog/templates/**/*.html",
    "../accounts/templates/**/*.html",
    "../comments/templates/**/*.html",
    "../oauth/templates/**/*.html",
  ],

  // 深色模式配置 - 使用 data-theme 属性，与 dark_mode 插件配合
  darkMode: ['selector', '[data-theme="dark"]'],

  theme: {
    // 侧栏在默认 1024px 断点会挤压正文，因此只调整响应式断点。
    screens: {
      sm: '640px',
      md: '768px',
      lg: '1080px',   // 侧栏开关：默认 1024px 时主栏只剩 ~540px，标题和日期轨道会被挤扁
      xl: '1400px',
      '2xl': '1536px',
    },
    extend: {
      // 保留 Tailwind 的标准 max-width 比例；站点宽度用语义化名称单独表达。
      maxWidth: {
        site: '86rem',
        content: '86rem',
      },

      // 自定义颜色，使用CSS变量支持动态主题
      colors: {
        // 主题色系统
        // DEFAULT 指向语义 token --primary（亮色 #7C3AED / 暗色 #A78BFA），
        // 这样 bg-primary、text-primary、border-primary 以及它们的透明度变体
        // （bg-primary/5、hover:bg-primary/15）才能被生成。
        // 注意：不要用函数形式 ({ opacityValue }) 的写法，写错时 Tailwind 会静默
        // 生成一个空类 .bg-primary{}，页面上什么都不显示，且很难排查。
        primary: {
          DEFAULT: 'rgb(var(--primary) / <alpha-value>)',
          50: 'rgb(var(--color-primary-50) / <alpha-value>)',
          100: 'rgb(var(--color-primary-100) / <alpha-value>)',
          200: 'rgb(var(--color-primary-200) / <alpha-value>)',
          300: 'rgb(var(--color-primary-300) / <alpha-value>)',
          400: 'rgb(var(--color-primary-400) / <alpha-value>)',
          500: 'rgb(var(--color-primary-500) / <alpha-value>)',
          600: 'rgb(var(--color-primary-600) / <alpha-value>)',
          700: 'rgb(var(--color-primary-700) / <alpha-value>)',
          800: 'rgb(var(--color-primary-800) / <alpha-value>)',
          900: 'rgb(var(--color-primary-900) / <alpha-value>)',
        },
        // 语义化颜色（对标 Next.js）
        border: 'rgb(var(--border) / <alpha-value>)',
        input: 'rgb(var(--input) / <alpha-value>)',
        ring: 'rgb(var(--ring) / <alpha-value>)',
        background: 'rgb(var(--background) / <alpha-value>)',
        foreground: 'rgb(var(--foreground) / <alpha-value>)',
        card: {
          DEFAULT: 'rgb(var(--card) / <alpha-value>)',
          foreground: 'rgb(var(--card-foreground) / <alpha-value>)',
        },
        muted: {
          DEFAULT: 'rgb(var(--muted) / <alpha-value>)',
          foreground: 'rgb(var(--muted-foreground) / <alpha-value>)',
        },
        secondary: {
          DEFAULT: 'rgb(var(--secondary) / <alpha-value>)',
          foreground: 'rgb(var(--secondary-foreground) / <alpha-value>)',
        },
        accent: {
          DEFAULT: 'rgb(var(--accent) / <alpha-value>)',
          foreground: 'rgb(var(--accent-foreground) / <alpha-value>)',
        },
        // 紫色强调色的三个语义档位（模板里用 bg-primary-soft / border-primary-line 等）
        'primary-soft': 'rgb(var(--primary-soft) / <alpha-value>)',
        'primary-line': 'rgb(var(--primary-line) / <alpha-value>)',
        'primary-deep': 'rgb(var(--primary-deep) / <alpha-value>)',
        // 让 bg-primary / text-primary-foreground / border-primary 也能直接使用
        'primary-foreground': 'rgb(var(--primary-foreground) / <alpha-value>)',
        'card-foreground': 'rgb(var(--card-foreground) / <alpha-value>)',
        'muted-foreground': 'rgb(var(--muted-foreground) / <alpha-value>)',
        'secondary-foreground': 'rgb(var(--secondary-foreground) / <alpha-value>)',
        destructive: {
          DEFAULT: 'rgb(var(--destructive) / <alpha-value>)',
          foreground: 'rgb(var(--destructive-foreground) / <alpha-value>)',
        },
      },

      // Z-index 层级定义
      zIndex: {
        'modal': '60',
      },

      // 字体家族
      // 拉丁字形走 Open Sans（自托管 woff2），中文落到系统黑体，
      // 避免为中文引入数百 KB Web 字体；数字默认等宽以对齐元信息
      fontFamily: {
        sans: [
          '"Open Sans"',
          '-apple-system',
          'BlinkMacSystemFont',
          '"Segoe UI"',
          '"PingFang SC"',
          '"HarmonyOS Sans SC"',
          '"Hiragino Sans GB"',
          '"Microsoft YaHei"',
          '"Noto Sans SC"',
          'sans-serif',
        ],
        mono: [
          'ui-monospace',
          '"JetBrains Mono"',
          '"SFMono-Regular"',
          'Consolas',
          '"Liberation Mono"',
          'monospace',
        ],
      },

      // 圆角：容器大、内部元素小
      borderRadius: {
        xs: '6px',
        sm: '0.5rem',
        md: '0.75rem',
        lg: '1rem',
        xl: '1.5rem',
      },

      // 阴影：统一冷灰、单一光源，不用纯黑
      boxShadow: {
        xs: 'var(--shadow-xs)',
        sm: 'var(--shadow-sm)',
        card: 'var(--shadow-card)',
        'card-hover': 'var(--shadow-card-hover)',
        elevated: 'var(--shadow-elevated)',
        glow: 'var(--shadow-glow)',
      },

      // 动效：统一缓动，避免各组件各写一套
      transitionTimingFunction: {
        soft: 'cubic-bezier(0.22, 1, 0.36, 1)',
      },

      animation: {
        'fade-in': 'fadeIn 0.3s cubic-bezier(0.22, 1, 0.36, 1) both',
        'slide-up': 'slideUp 0.35s cubic-bezier(0.22, 1, 0.36, 1) both',
        'slide-down': 'slideDown 0.3s cubic-bezier(0.22, 1, 0.36, 1) both',
        'heartbeat': 'heartbeat 1.2s ease-in-out infinite',
        'hero-rise': 'heroRise 0.6s cubic-bezier(0.22, 1, 0.36, 1) both',
      },

      keyframes: {
        heroRise: {
          '0%': { opacity: '0', transform: 'translateY(12px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { transform: 'translateY(10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        slideDown: {
          '0%': { transform: 'translateY(-10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        heartbeat: {
          '0%, 100%': { transform: 'scale(1)' },
          '14%': { transform: 'scale(1.3)' },
          '28%': { transform: 'scale(1)' },
          '42%': { transform: 'scale(1.3)' },
          '70%': { transform: 'scale(1)' },
        },
      },
    },
  },

  plugins: [
    require('@tailwindcss/typography'),
  ],
};
