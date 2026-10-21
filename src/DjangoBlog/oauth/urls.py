from django.urls import path

from . import views

app_name = "oauth"
# GZX：路由分两端：oauth/oauthlogin 是"发起授权"（跳转第三方），oauth/authorize 是"回调"（拿 code 换用户）；
# 其余 requireemail/emailconfirm/bindsuccess 处理第三方未返回邮箱时的补绑流程。
urlpatterns = [
    # GZX：第三方回调入口，第三方带 code 跳回这里，换 token 并完成登录/转补邮箱。
    path(
        r'oauth/authorize',
        views.authorize),
    # GZX：第三方未返回邮箱时的补邮箱表单页，oauthid 为 OAuthUser 主键。
    path(
        r'oauth/requireemail/<int:oauthid>.html',
        views.RequireEmailView.as_view(),
        name='require_email'),
    # GZX：邮件确认链接，id 为 OAuthUser 主键，sign 为 HMAC 签名，验证后完成绑定并登录。
    path(
        r'oauth/emailconfirm/<int:id>/<sign>.html',
        views.emailconfirm,
        name='email_confirm'),
    # GZX：绑定结果提示页，靠 query 参数 type=email/success 区分文案。
    path(
        r'oauth/bindsuccess/<int:oauthid>.html',
        views.bindsuccess,
        name='bindsuccess'),
    # GZX：发起授权入口，按 type 拼接第三方授权地址后 302 跳转。
    path(
        r'oauth/oauthlogin',
        views.oauthlogin,
        name='oauthlogin')]
