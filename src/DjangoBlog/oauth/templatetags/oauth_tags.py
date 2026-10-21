# GZX：模板标签包入口；本标签把"已启用渠道"转换成 (图标名, 授权链接) 列表交给模板渲染。
from django import template
from django.urls import reverse

from oauth.oauthmanager import get_oauth_apps

register = template.Library()


@register.inclusion_tag('oauth/oauth_applications.html')
def load_oauth_applications(request):
    # GZX：输入当前 request；输出模板上下文 {'apps': [(ICON_NAME, 授权URL), ...]}。
    # next_url 直接取当前完整路径，是否同域由 oauthlogin→get_redirecturl 二次校验。
    applications = get_oauth_apps()
    if applications:
        baseurl = reverse('oauth:oauthlogin')
        path = request.get_full_path()

        apps = list(map(lambda x: (x.ICON_NAME, '{baseurl}?type={type}&next_url={next}'.format(
            baseurl=baseurl, type=x.ICON_NAME, next=path)), applications))
    else:
        apps = []
    return {
        'apps': apps
    }
