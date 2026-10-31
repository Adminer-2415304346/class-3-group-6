# GCY（模块层）：钩子名称常量。ARTICLE_* 为文章生命周期 Action 钩子，
# ARTICLE_CONTENT_HOOK_NAME 是正文内容 Filter 钩子（模板标签处触发），
# POSITION_HOOKS 把模板位置映射到插件渲染方法名。常量集中定义避免
# 插件与业务代码硬编码字符串导致拼写不一致。
ARTICLE_DETAIL_LOAD = 'article_detail_load'
ARTICLE_CREATE = 'article_create'
ARTICLE_UPDATE = 'article_update'
ARTICLE_DELETE = 'article_delete'

ARTICLE_CONTENT_HOOK_NAME = "the_content"

# 位置钩子常量
POSITION_HOOKS = {
    'article_top': 'article_top_widgets',
    'article_bottom': 'article_bottom_widgets',
    'sidebar': 'sidebar_widgets',
    'header': 'header_widgets',
    'footer': 'footer_widgets',
    'comment_before': 'comment_before_widgets',
    'comment_after': 'comment_after_widgets',
}

# 资源注入钩子
HEAD_RESOURCES_HOOK = 'head_resources'
BODY_RESOURCES_HOOK = 'body_resources'

