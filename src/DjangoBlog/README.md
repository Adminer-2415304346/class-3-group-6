# Django 技术博客系统

> 软件工程方法学课程项目 · 24 级软件工程 3 班第 6 组

这是一个基于 Django 的内容发布与交流平台。项目在开源项目
[DjangoBlog](https://github.com/liangliangyy/DjangoBlog) 的基础上进行二次开发，保留文章、分类、标签、搜索、评论、OAuth
登录和插件机制等核心能力，重点完成了前端视觉体系、交互体验、演示内容、后台兼容性和质量检查流程的改造。

本目录中的代码是课程项目当前版本，不是上游项目的原样镜像。

## 项目改造内容

| 模块 | 本项目的主要改动 |
| --- | --- |
| 视觉系统 | 重构 Tailwind 语义色、间距、圆角、阴影、字体和响应式断点，统一首页、文章页、搜索页、错误页与账号页面的视觉语言 |
| 首页与内容页 | 重新设计文章列表、文章元信息、归档、标签、友情链接、面包屑和侧栏，改善信息层级与窄屏阅读体验 |
| 导航与移动端 | 重写桌面/移动导航交互，完善移动菜单、子分类、搜索入口、焦点状态和无障碍属性 |
| 深色模式 | 统一主题状态管理，支持系统主题、用户偏好持久化、无闪烁初始化和平滑切换；可使用 `Ctrl/Cmd + Shift + D` 快速切换 |
| 登录与账号流程 | 重做登录、注册、OAuth 绑定和结果页；新增响应式 Canvas 流线背景，并支持减少动态效果、页面不可见时暂停和手动暂停 |
| 评论体验 | 优化现代评论卡片、嵌套回复、输入区域以及亮色/暗色主题下的可读性 |
| 演示内容 | 将原有占位数据替换为 19 篇中文 Django 技术文章，补充真实分类、标签、发布时间和阅读量；生成命令可重复执行 |
| 后台管理 | 修复 Django 5.1+ `UserAdmin` 新建用户时的 `usable_password` 兼容问题，并补充有密码/无密码用户的回归测试 |
| 前端质量 | 新增静态资源一致性检查和 WCAG 2.1 AA 配色对比度检查脚本，降低漏构建和主题可读性问题 |

## 主要功能

- 文章、独立页面、分类与标签管理
- Markdown 编辑、代码高亮与文章归档
- Whoosh 全文搜索，支持切换到 Elasticsearch
- 用户注册、登录、找回密码与第三方 OAuth 登录
- 支持嵌套回复的评论系统
- 浅色/深色主题与响应式布局
- 本地内存或 Redis 缓存
- SEO、阅读量、阅读时间、文章推荐、外链处理和图片懒加载等插件
- Django Admin 内容管理后台
- Docker、Docker Compose 与 Kubernetes 部署配置

## 技术栈

| 层级 | 技术 |
| --- | --- |
| 后端 | Python 3.10+、Django 5.2.17 |
| 数据库 | MySQL / MariaDB |
| 前端 | Django Templates、Alpine.js 3.16、HTMX 2.0、Tailwind CSS 3.4 |
| 构建工具 | Vite 6、PostCSS、Autoprefixer、CSSNano、Terser |
| 搜索 | Whoosh（默认）、Elasticsearch（可选） |
| 缓存 | LocalMem（默认）、Redis（可选） |
| 内容 | Markdown、Pygments、django-mdeditor |
| 部署 | Docker、Nginx、Kubernetes、Gevent |

本项目已在 Python 3.12.7、MySQL 8.0.46、Node.js 22.19.0 环境下完成本地运行验证。

## 目录结构

```text
DjangoBlog/
├─ accounts/       # 用户模型、认证与后台管理
├─ blog/           # 文章、分类、标签、搜索和演示数据
├─ comments/       # 评论与回复
├─ djangoblog/     # 项目配置、URL、搜索后端和通用能力
├─ frontend/       # Alpine.js、Tailwind CSS 与 Vite 源码
├─ oauth/          # 第三方登录
├─ plugins/        # 可插拔功能模块
├─ templates/      # Django 页面模板
├─ scripts/        # 资源和配色质量检查脚本
├─ deploy/         # Docker、Nginx 与 Kubernetes 配置
├─ docs/           # 扩展配置与部署文档
├─ manage.py
└─ requirements.txt
```

## 本地运行

### 1. 获取代码

```powershell
git clone https://github.com/Adminer-2415304346/class-3-group-6.git
cd class-3-group-6\src\DjangoBlog
```

### 2. 创建 Python 虚拟环境

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 3. 准备 MySQL

先在 MySQL 中创建 UTF-8 数据库：

```sql
CREATE DATABASE djangoblog
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
```

项目优先从环境变量读取数据库配置。PowerShell 示例：

```powershell
$env:DJANGO_MYSQL_DATABASE = "djangoblog"
$env:DJANGO_MYSQL_USER = "root"
$env:DJANGO_MYSQL_PASSWORD = "<你的 MySQL 密码>"
$env:DJANGO_MYSQL_HOST = "127.0.0.1"
$env:DJANGO_MYSQL_PORT = "3306"
```

Linux/macOS 可设置同名环境变量。不要把本机密码、生产密钥或邮箱凭据写入仓库。

### 4. 构建前端资源

```powershell
cd frontend
npm ci
npm run build
cd ..
```

前端开发时可使用 `npm run dev` 启动 Vite 开发服务器，或使用 `npm run watch` 持续构建资源。

### 5. 初始化并启动

```powershell
python manage.py migrate
python manage.py createsuperuser

# 可选：生成课程演示用的中文文章、分类和标签
python manage.py create_testdata

python manage.py runserver
```

访问地址：

- 博客首页：<http://127.0.0.1:8000/>
- 管理后台：<http://127.0.0.1:8000/admin/>

`create_testdata` 会创建仅供本地演示的数据和测试用户，请勿直接用于生产环境。

## 常用配置

| 环境变量 | 用途 | 是否必需 |
| --- | --- | --- |
| `DJANGO_MYSQL_DATABASE` | MySQL 数据库名 | 本地有默认值 |
| `DJANGO_MYSQL_USER` | MySQL 用户名 | 本地有默认值 |
| `DJANGO_MYSQL_PASSWORD` | MySQL 密码 | 建议显式设置 |
| `DJANGO_MYSQL_HOST` | MySQL 地址 | 本地有默认值 |
| `DJANGO_MYSQL_PORT` | MySQL 端口 | 本地有默认值 |
| `DJANGO_SECRET_KEY` | Django 签名密钥 | 生产环境必须设置 |
| `DJANGO_DEBUG` | 是否开启调试模式，值为 `True` 或 `False` | 生产环境必须设为 `False` |
| `DJANGO_REDIS_URL` | Redis 地址，例如 `127.0.0.1:6379/0` | 可选 |
| `DJANGO_ELASTICSEARCH_HOST` | Elasticsearch 服务地址 | 可选 |
| `DJANGO_EMAIL_USER` | SMTP 用户名 | 邮件功能可选 |
| `DJANGO_EMAIL_PASSWORD` | SMTP 密码 | 邮件功能可选 |

更多说明见 [项目配置](docs/config.md) 和 [搜索引擎配置](docs/search-engine-config.md)。

## 检查与测试

提交代码前建议执行：

```powershell
# Django 配置与模型检查
python manage.py check

# 自动化测试
python manage.py test

# 亮色/暗色主题的 WCAG 2.1 AA 对比度检查
python scripts/check_contrast.py
```

启动 Django 开发服务器后，还可以在另一个终端检查页面引用的 CSS 是否与模板一致：

```powershell
python scripts/check_assets.py
```

如果资源检查提示样式缺失，请进入 `frontend` 目录重新运行 `npm run build`。

## 部署

- 收集静态资源：`python manage.py collectstatic --noinput`
- Docker 部署：[docs/docker.md](docs/docker.md)
- Kubernetes 部署：[docs/k8s.md](docs/k8s.md)

正式部署前必须设置新的 `DJANGO_SECRET_KEY`、关闭 `DJANGO_DEBUG`，并按实际域名收紧
`ALLOWED_HOSTS` 与 `CSRF_TRUSTED_ORIGINS`。数据库、邮件、OAuth 和其他第三方服务的凭据应通过环境变量或密钥管理服务注入。

## 项目成员

| 姓名 | 学号 | 班级 |
| --- | --- | --- |
| 石兆翔 | 2415304346 | 24 级软件工程 3 班 |
| 喻飞扬 | 2415304347 | 24 级软件工程 3 班 |
| 王子扬 | 2415304348 | 24 级软件工程 3 班 |
| 顾梓鑫 | 2415304345 | 24 级软件工程 3 班 |
| 宋洋 | 2415304330 | 24 级软件工程 3 班 |

## 开源说明

本项目基于 [liangliangyy/DjangoBlog](https://github.com/liangliangyy/DjangoBlog) 进行课程二次开发。
感谢原项目作者与贡献者提供的基础实现。本项目继续遵循仓库中的 [MIT License](LICENSE)。
