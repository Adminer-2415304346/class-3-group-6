"""Create repeatable, theme-specific demo content for the course blog."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models.signals import post_save
from django.utils import timezone

from blog.models import Article, BlogSettings, Category, Tag
from comments.models import Comment


DEMO_AUTHOR_EMAIL = 'agent-demo@example.invalid'
DEMO_READER_EMAIL = 'agent-reader@example.invalid'
ROOT_CATEGORY = 'AI Agent 工程实践'

# Category, title, introduction, tags. The rest of each Markdown article is
# generated from the same outline so the cards and detail pages contain useful
# content without suggesting that this blog itself implements an Agent runtime.
DEMO_ARTICLES = [
    ('基础与架构', 'AI Agent 是什么：从问答到可执行工作流',
     '区分普通聊天、固定工作流与能够选择工具并根据结果继续行动的 Agent。',
     ('Agent', 'LLM')),
    ('基础与架构', '一个最小 Agent 的组成：目标、状态、工具与反馈',
     '把系统拆成可观察的四个部分，明确模型负责决策，程序负责执行和校验。',
     ('Agent', 'Architecture')),
    ('基础与架构', '单 Agent 还是多 Agent：先把边界画清楚',
     '用任务分解、共享状态和交接成本判断何时需要多个角色协作。',
     ('Agent', 'Architecture')),
    ('工具与工作流', '工具调用设计：让参数、权限与结果都可验证',
     '从工具清单、输入约束、超时和错误处理入手，减少模型调用外部能力时的意外。',
     ('Tool-Calling', 'Safety')),
    ('工具与工作流', '规划与执行：把复杂目标拆成可回退的步骤',
     '用计划、执行、观察、复核四阶段组织任务，并在关键步骤设置人工确认点。',
     ('Planning', 'Workflow')),
    ('工具与工作流', '用 Django 记录 Agent 任务的状态流转',
     '以博客项目的 Django 技术栈为例，讨论任务状态、操作日志和失败重试如何建模。',
     ('Django', 'Workflow')),
    ('知识与记忆', 'RAG 入门：检索结果如何进入 Agent 上下文',
     '理解切分、召回、重排与引用展示，避免把未经验证的片段当作确定事实。',
     ('RAG', 'Knowledge')),
    ('知识与记忆', '短期状态与长期记忆：哪些信息值得保存',
     '比较会话上下文、任务状态和可复用知识，并考虑过期、删除与隐私边界。',
     ('Memory', 'Safety')),
    ('评测与安全', 'Agent 评测：成功率之外还要看什么',
     '同时记录任务完成、工具错误、成本、时延和人工接管次数，构建可复现的评测集。',
     ('Evaluation', 'Observability')),
    ('评测与安全', '提示注入与越权调用：给 Agent 设安全护栏',
     '区分用户指令与外部资料，限制高风险工具，记录审批和审计证据。',
     ('Safety', 'Tool-Calling')),
    ('应用案例', '案例：文档问答助手的需求与界面草图',
     '从上传资料、提问、引用回溯和错误反馈出发设计一个可检查的演示场景。',
     ('RAG', 'Case-Study')),
    ('应用案例', '案例：研发任务助手如何与人协作',
     '用工单摘要、方案草拟、测试建议和人工确认说明 Agent 的辅助定位。',
     ('Workflow', 'Case-Study')),
]

# A topic-specific paragraph for each article. Keeping it separate from the
# metadata makes the seed readable while giving each detail page a useful lead.
ARTICLE_PRACTICE_NOTES = [
    '普通问答通常在一次回复后结束，固定工作流按预设节点推进。Agent 则会依据目标与观察结果选择下一步行动，但行动仍须受到工具权限、终止条件和人工审批约束。判断是否需要 Agent，先看任务是否真的存在动态决策。',
    '目标描述期望结果，状态记录已知事实与进度，工具负责访问外部世界，反馈则让系统检验上一动作是否有效。四者需要明确的数据接口；若只保存聊天记录而不记录工具结果，就难以复盘错误来源。',
    '多 Agent 适合职责清晰、可独立验收的子任务。若多个角色频繁共享同一上下文，协调成本可能高于收益。应先实现单 Agent 的可观测执行，再把检索、审查或交付等独立步骤拆分出去。',
    '每个工具都应声明用途、参数模式、返回结构和失败类型。执行层应再次校验模型给出的参数，设置超时与速率限制，并将写操作与只读操作区分。删除或对外发送等高风险动作应要求明确的人工确认。',
    '计划不是一次生成后不可更改的清单。执行阶段应保存每步的输入与输出，观察阶段检查是否达成中间目标，复核阶段决定继续、重试或回退。这样即使模型判断失误，也能定位并恢复到上一个安全状态。',
    '如果未来在 Django 中实现任务助手，可以把任务、步骤与工具调用分别建模，并记录状态、时间戳及错误信息。当前课程博客只发布这类设计文章，并未新增运行时模型；案例是数据建模思路，不是现有功能说明。',
    'RAG 的核心是先从可信资料中检索相关片段，再把片段连同来源送入生成步骤。切分过细会丢上下文，过粗会降低召回精度。界面应展示引用片段与原文链接，使读者能够检查答案依据。',
    '短期状态服务于当前任务，长期记忆保存经确认、可再次使用的信息。不是所有对话都应永久保存；个人信息需要明确目的和保留期限，并支持更正与删除。过期记忆还会导致系统反复沿用错误结论。',
    '评测集应覆盖正常任务、模糊输入、工具故障和拒绝执行的边界情况。除最终成功率，还需记录每步调用、成本、时延与人工接管次数。所有测试样例应固定输入和评分标准，才能比较改动前后的效果。',
    '外部网页、检索结果和工具输出都可能包含伪装成指令的文本。系统应区分这些不可信内容与用户授权，限制工具作用域，并在执行前校验目标、参数和权限。高风险请求要保留人工审批及审计记录。',
    '文档问答助手的关键界面不只是输入框，还包括资料来源、检索片段、答案引用、无结果提示与纠错入口。案例文章讨论如何设计这些元素；当前博客仅展示文字与图示，不提供真实文档上传或问答服务。',
    '研发任务助手可以先归纳工单背景，再给出实现方案与测试建议，最后由工程师确认和提交。它应呈现“建议”和“已执行”之间的区别，并展示依据与风险。课程博客以此说明人机协作边界，而非自动修改代码。',
]

DEMO_COMMENTS = (
    (0, '建议在入门篇里补充固定工作流与 Agent 的区别，便于初学者理解。'),
    (6, '检索结果最好展示来源和片段，方便读者核对答案。'),
    (9, '高风险工具调用增加人工确认后，演示会更贴近真实项目。'),
)


class Command(BaseCommand):
    help = 'Create repeatable AI Agent engineering demo data (development only)'

    def handle(self, *args, **options):
        # The normal post-save handler sends search-engine pings and comment
        # email. Demo creation must have no such external side effects.
        from djangoblog.blog_signals import model_post_save_callback
        was_connected = post_save.disconnect(model_post_save_callback)
        try:
            self.create_demo_data()
        finally:
            if was_connected:
                post_save.connect(model_post_save_callback)

    @transaction.atomic
    def create_demo_data(self):
        User = get_user_model()
        author, created = User.objects.get_or_create(
            email=DEMO_AUTHOR_EMAIL,
            defaults={'username': 'agent-editor', 'nickname': 'Agent 实践编辑'},
        )
        if created:
            author.set_unusable_password()
            author.save(update_fields=['password'])

        reader, created = User.objects.get_or_create(
            email=DEMO_READER_EMAIL,
            defaults={'username': 'agent-reader', 'nickname': 'Agent 实践读者'},
        )
        if created:
            reader.set_unusable_password()
            reader.save(update_fields=['password'])

        BlogSettings.objects.get_or_create(defaults={
            'site_name': ROOT_CATEGORY,
            'site_description': '记录 AI Agent 的原理、开发方法与应用案例',
            'site_seo_description': 'AI Agent 工程实践：架构、工具调用、RAG、评测与安全',
            'site_keywords': 'AI Agent,LLM,RAG,工具调用,评测,安全',
            'color_scheme': 'blue',
            'article_sub_length': 140,
        })

        root, _ = Category.objects.get_or_create(
            name=ROOT_CATEGORY,
            defaults={'parent_category': None, 'index': 10},
        )
        category_names = dict.fromkeys(item[0] for item in DEMO_ARTICLES)
        categories = {}
        for index, name in enumerate(category_names, start=1):
            categories[name], _ = Category.objects.get_or_create(
                name=name,
                defaults={'parent_category': root, 'index': 10 - index},
            )

        published_at = timezone.now()
        articles = []
        for index, (category_name, title, intro, tag_names) in enumerate(DEMO_ARTICLES):
            if Article.objects.filter(title=title).exclude(author=author).exists():
                raise CommandError(f'演示标题与现有文章冲突，未覆盖原文章：{title}')
            body = (
                f'{intro}\n\n{ARTICLE_PRACTICE_NOTES[index]}\n\n'
                '## 设计问题\n\n'
                '实际场景中，先确认目标、输入、可用工具与完成标准，再决定是否需要 Agent。'
                '不能因为使用了大模型，就默认系统已经具备自主执行能力。\n\n'
                '## 实践步骤\n\n'
                '1. 写出任务边界与预期输出。\n'
                '2. 为每一步记录输入、结果和失败原因。\n'
                '3. 对外部数据和高风险操作加入校验或人工确认。\n\n'
                '## 检查清单\n\n'
                '- 结果能否追溯到输入与工具调用？\n'
                '- 失败时能否安全停止或重试？\n'
                '- 用户能否看懂系统当前状态？\n'
            )
            article, _ = Article.objects.update_or_create(
                title=title,
                author=author,
                defaults={
                    'category': categories[category_name],
                    'body': body,
                    'pub_time': published_at - timedelta(days=(len(DEMO_ARTICLES) - index - 1) * 4),
                    'status': 'p',
                    'type': 'a',
                    'comment_status': 'o',
                    'show_toc': True,
                },
            )
            article.tags.set(Tag.objects.get_or_create(name=name)[0] for name in tag_names)
            articles.append(article)

        for article_index, body in DEMO_COMMENTS:
            Comment.objects.get_or_create(
                article=articles[article_index], author=reader, body=body,
                defaults={'is_enable': True},
            )

        from djangoblog.utils import cache
        cache.clear()
        self.stdout.write(self.style.SUCCESS(
            f'AI Agent demo ready: {len(articles)} articles, '
            f'{len(categories) + 1} categories, '
            f'{Tag.objects.filter(article__in=articles).distinct().count()} tags'
        ))
