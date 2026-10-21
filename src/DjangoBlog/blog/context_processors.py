# SZX（第7—8周）：请求模板上下文处理器提供站点配置、导航和当前年份，保留 GCY 原标注。
import logging

from django.utils import timezone

from djangoblog.utils import cache, get_blog_setting
from .models import Category, Article

logger = logging.getLogger(__name__)

# GCY：seo_processor 已注册到模板引擎；使用请求上下文渲染模板时提供站点设置与导航数据，并非所有模板渲染都无条件调用。
# SZX：审校限定调用条件；静态站点数据缓存 10 小时，SITE_BASE_URL 与 CURRENT_YEAR 在缓存命中时仍按当前请求和时间更新。
def seo_processor(requests):
    # SZX（第7—8周）：缓存静态站点信息；scheme/host 必须随本次请求重新计算。
    key = 'seo_processor'
    value = cache.get(key)
    if value:
        # 更新动态值（不需要缓存的内容）
        value['SITE_BASE_URL'] = requests.scheme + '://' + requests.get_host() + '/'
        value['CURRENT_YEAR'] = timezone.now().year
        return value
    else:
        logger.info('set processor cache.')
        setting = get_blog_setting()

        # 优化查询：预加载关联数据
        nav_category_list = Category.objects.all()
        nav_pages = Article.objects.filter(
            type='p',
            status='p'
        )

        value = {
            'SITE_NAME': setting.site_name,
            'SHOW_GOOGLE_ADSENSE': setting.show_google_adsense,
            'GOOGLE_ADSENSE_CODES': setting.google_adsense_codes,
            'SITE_SEO_DESCRIPTION': setting.site_seo_description,
            'SITE_DESCRIPTION': setting.site_description,
            'SITE_KEYWORDS': setting.site_keywords,
            'SITE_BASE_URL': requests.scheme + '://' + requests.get_host() + '/',
            'ARTICLE_SUB_LENGTH': setting.article_sub_length,
            'nav_category_list': nav_category_list,  # 保持QuerySet
            'nav_pages': nav_pages,  # 保持QuerySet
            'OPEN_SITE_COMMENT': setting.open_site_comment,
            'BEIAN_CODE': setting.beian_code,
            'ANALYTICS_CODE': setting.analytics_code,
            "BEIAN_CODE_GONGAN": setting.gongan_beiancode,
            "SHOW_GONGAN_CODE": setting.show_gongan_code,
            "CURRENT_YEAR": timezone.now().year,
            "GLOBAL_HEADER": setting.global_header,
            "GLOBAL_FOOTER": setting.global_footer,
            "COMMENT_NEED_REVIEW": setting.comment_need_review,
            "COLOR_SCHEME": setting.color_scheme,
        }
        cache.set(key, value, 60 * 60 * 10)
        return value
