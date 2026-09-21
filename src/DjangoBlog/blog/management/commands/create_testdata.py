from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.utils import timezone

from blog.models import Article, Tag, Category


DEMO_ARTICLES = [
    (
        '从零搭建 Django 项目：目录与配置',
        '从虚拟环境、依赖管理到 settings 拆分，搭好一个适合持续迭代的 Django 项目骨架。',
        ('Django', '工程化'),
        36,
    ),
    (
        '理解一次 Django 请求的完整生命周期',
        '沿着中间件、URL 路由、视图和响应回溯一次请求，弄清每个扩展点应该放什么逻辑。',
        ('Django', 'Python'),
        42,
    ),
    (
        '模型设计：外键、索引与数据约束',
        '用一组博客模型说明关系字段、联合索引和数据库约束如何共同保证数据质量。',
        ('Django', '数据库'),
        51,
    ),
    (
        'QuerySet 的惰性查询与性能陷阱',
        '理解 QuerySet 何时真正访问数据库，并避开重复求值、无效切片和意外全表扫描。',
        ('Django', '性能优化'),
        48,
    ),
    (
        '用类视图整理重复的页面逻辑',
        '从函数视图迁移到 Class-Based View，复用查询、分页和权限判断，同时保持代码可读。',
        ('Django', '工程化'),
        63,
    ),
    (
        '表单验证：从 clean 到错误提示',
        '把字段校验、跨字段校验和面向用户的错误信息串成一条清晰、可测试的验证链路。',
        ('Django', '测试'),
        70,
    ),
    (
        '模板继承与可复用组件',
        '通过基础布局、include 和自定义模板标签，减少重复标记并保持页面结构一致。',
        ('Django', '前端'),
        57,
    ),
    (
        '让 Vite 接管 Django 的前端资源',
        '打通开发热更新、生产构建与静态文件清单，让现代前端工具自然融入 Django。',
        ('工程化', '前端'),
        92,
    ),
    (
        'Django Admin 的五个实用定制',
        '围绕列表筛选、批量操作、只读字段和查询优化，把后台改造成真正顺手的内容工具。',
        ('Django', '工程化'),
        76,
    ),
    (
        '登录、权限与常见安全边界',
        '梳理认证、授权、CSRF 与安全 Cookie，明确哪些保护应由框架完成，哪些需要业务兜底。',
        ('Django', '安全'),
        81,
    ),
    (
        '用缓存减少重复数据库查询',
        '从页面片段到查询结果，选择合适的缓存粒度，并处理失效、穿透与数据一致性。',
        ('性能优化', '数据库'),
        105,
    ),
    (
        '分页、排序与筛选的组合设计',
        '让多个查询参数稳定共存，保留用户当前状态，并为大数据量列表控制查询成本。',
        ('Django', '数据库'),
        68,
    ),
    (
        '为 Django 视图补上自动化测试',
        '使用测试客户端覆盖成功、权限和异常路径，让重构不再依赖手工刷新页面验证。',
        ('Django', '测试'),
        99,
    ),
    (
        '部署前必须检查的关键设置',
        '从 DEBUG、密钥、Allowed Hosts 到静态资源和 HTTPS，逐项收紧生产环境配置。',
        ('部署', '安全'),
        88,
    ),
    (
        'Celery 异步任务的最小实践',
        '把邮件和耗时任务移出请求链路，并用重试、幂等与可观测性保证任务可靠执行。',
        ('Python', '工程化'),
        64,
    ),
    (
        '日志、异常与线上问题定位',
        '设计有上下文的结构化日志，串联请求与异常信息，让一次线上排查更快得到结论。',
        ('工程化', '部署'),
        73,
    ),
    (
        '从 N+1 查询到 select_related',
        '通过真实查询案例定位 N+1 问题，并比较 select_related 与 prefetch_related 的适用边界。',
        ('Django', '性能优化'),
        118,
    ),
    (
        'Django 项目的现代化工程结构',
        '重新划分配置、应用、模板和服务层边界，让项目从第一天起就易于维护和扩展。',
        ('Django', '工程化'),
        132,
    ),
    (
        '用 Django 与 HTMX 构建轻量交互页面',
        '不引入复杂前端框架，只用 HTMX 与少量 Alpine.js 完成局部刷新、历史记录和渐进增强。',
        ('Django', 'HTMX', '前端'),
        156,
    ),
]


class Command(BaseCommand):
    help = 'create test datas'

    def handle(self, *args, **options):
        user = get_user_model().objects.get_or_create(
            email='test@test.com', username='测试用户', password=make_password('test!q@w#eTYU'))[0]

        pcategory = Category.objects.get_or_create(
            name='技术专栏', parent_category=None)[0]

        category = Category.objects.get_or_create(
            name='Django 开发', parent_category=pcategory)[0]

        category.save()
        published_at = timezone.now()
        total = len(DEMO_ARTICLES)
        for index, (title, body, tag_names, views) in enumerate(DEMO_ARTICLES):
            article = Article.objects.update_or_create(
                category=category,
                title=title,
                author=user,
                defaults={
                    'body': body,
                    'pub_time': published_at - timedelta(days=(total - index - 1) * 6),
                    'views': views,
                },
            )[0]
            article.tags.set(Tag.objects.get_or_create(name=name)[0] for name in tag_names)

        from djangoblog.utils import cache
        cache.clear()
        self.stdout.write(self.style.SUCCESS('created test datas \n'))
