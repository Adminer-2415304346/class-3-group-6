from django.urls import path

from . import views

app_name = "oauth"
# GZX：路由分两端：oauth/oauthlogin 是"发起授权"（跳转第三方），oauth/authorize 是"回调"（拿 code 换用户）；
# 其余 requireemail/emailconfirm/bindsuccess 处理第三方未返回邮箱时的补绑流程。
urlpatterns = [
    path(
        r'oauth/authorize',
        views.authorize),
    path(
        r'oauth/requireemail/<int:oauthid>.html',
        views.RequireEmailView.as_view(),
        name='require_email'),
    path(
        r'oauth/emailconfirm/<int:id>/<sign>.html',
        views.emailconfirm,
        name='email_confirm'),
    path(
        r'oauth/bindsuccess/<int:oauthid>.html',
        views.bindsuccess,
        name='bindsuccess'),
    path(
        r'oauth/oauthlogin',
        views.oauthlogin,
        name='oauthlogin')]
