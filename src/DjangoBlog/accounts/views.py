# YFY：模块职责：accounts 的 HTTP 入口，编排注册激活、登录登出、找回密码与验证码接口。
# YFY：职责边界：输入校验在 forms/认证后端，密码哈希由 Django hasher 完成；邮件投递统一经
# YFY：djangoblog.utils.send_email → blog_signals.send_email_signal，本模块不直接调用 SMTP。
import logging

from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.contrib import auth
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth import get_user_model
from django.contrib.auth import logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.hashers import make_password
from django.http import HttpResponseRedirect, HttpResponseForbidden
from django.http.request import HttpRequest
from django.http.response import HttpResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View

from djangoblog.utils import send_email, get_sha256, get_current_site, generate_code, delete_sidebar_cache
from djangoblog.base_views import SecureFormView, LoginFormView, LogoutRedirectView
from . import utils
from .forms import RegisterForm, LoginForm, ForgetPasswordForm, ForgetPasswordCodeForm
from .models import BlogUser

logger = logging.getLogger(__name__)


# Create your views here.

class RegisterView(SecureFormView):
    """
    用户注册视图（重构版）

    使用 SecureFormView 基类，自动提供 CSRF 保护
    """
    form_class = RegisterForm
    template_name = 'account/registration_form.html'

    # YFY：表单校验通过后执行，视图负责业务逻辑：创建未激活用户、发送邮箱验证链接
    # YFY：前置条件：FormView 已调用 form.is_valid()；这里的再次 is_valid() 是冗余判断，
    # YFY：不会改变结果，但会让“谁负责校验”的边界变得模糊。
    # YFY：状态策略：先 save(commit=False) 拿到已哈希密码的实例，再显式置 is_active=False，
    # YFY：确保注册后必须走邮箱验证链接才能登录。
    def form_valid(self, form):
        if form.is_valid():
            user = form.save(False)
            user.is_active = False
            user.source = 'Register'
            user.save(True)
            site = get_current_site().domain
            # YFY：签名使用 SECRET_KEY 对 user.id 做两次 HMAC-SHA256，id 与 sign 一起构成激活凭证。
            sign = get_sha256(get_sha256(settings.SECRET_KEY + str(user.id)))

            # YFY：DEBUG 下强制使用本地域名，便于开发时手工点开邮件里的验证链接；
            # YFY：生产环境必须关闭 DEBUG，否则会生成指向 127.0.0.1 的无效链接。
            if settings.DEBUG:
                site = '127.0.0.1:8000'
            path = reverse('account:result')
            url = "http://{site}{path}?type=validation&id={id}&sign={sign}".format(
                site=site, path=path, id=user.id, sign=sign)

            content = """
                            <p>请点击下面链接验证您的邮箱</p>

                            <a href="{url}" rel="bookmark">{url}</a>

                            再次感谢您！
                            <br />
                            如果上面链接无法打开，请将此链接复制至浏览器。
                            {url}
                            """.format(url=url)
            # YFY：邮件发送是同步信号；若 SMTP 抛异常，用户已写入数据库但拿不到验证链接，
            # YFY：当前实现没有补偿或重发入口，属于后续可改进的失败路径。
            send_email(
                emailto=[
                    user.email,
                ],
                title='验证您的电子邮箱',
                content=content)

            # YFY：这里用 application namespace（accounts）反查，与上面的 account 实例命名空间指向
            # YFY：同一个 result 路由；两种写法都已由 accounts.tests.test_validate_register 核对。
            url = reverse('accounts:result') + \
                  '?type=register&id=' + str(user.id)
            return HttpResponseRedirect(url)
        else:
            return self.render_to_response({
                'form': form
            })


class LogoutView(LogoutRedirectView):
    """
    用户登出视图（重构版）

    使用 LogoutRedirectView 基类，自动禁用缓存
    """
    url = '/login/'

    # YFY：登出顺序：先让 Django 清空 session，再清侧边栏缓存，最后让浏览器删除 logged_user 标记。
    # YFY：注意：logged_user 只是前端展示标记，不是认证凭证；真正的登录态仍由 session cookie 决定。
    def get(self, request, *args, **kwargs):
        logout(request)
        delete_sidebar_cache()
        # 获取响应对象并删除登录标记 cookie
        response = super(LogoutView, self).get(request, *args, **kwargs)
        response.delete_cookie('logged_user')
        return response


class LoginView(LoginFormView):
    """
    用户登录视图（重构版）

    使用 LoginFormView 基类，自动提供：
    - 敏感参数保护（password）
    - CSRF 保护
    - 禁用缓存
    """
    form_class = LoginForm
    template_name = 'account/login.html'
    success_url = '/'
    redirect_field_name = REDIRECT_FIELD_NAME

    def get_context_data(self, **kwargs):
        redirect_to = self.request.GET.get(self.redirect_field_name)
        if redirect_to is None:
            redirect_to = '/'
        kwargs['redirect_to'] = redirect_to

        return super(LoginView, self).get_context_data(**kwargs)

    # YFY：修订旧注释：这里并不是直接使用 FormView 已校验的 LoginForm，而是重新构造
    # YFY：AuthenticationForm 再做一次认证；因此一次 POST 会走两遍认证后端（密码哈希校验两次）。
    # YFY：旧注释只写了“登录表单校验成功”，未说明重新实例化带来的重复校验和自定义表单被替换。
    # YFY：行为后果：LoginForm 的控件样式作用于 GET 与校验失败后的重新渲染；
    # YFY：成功路径的第二次认证使用基类实例，本身也继承 AuthenticationForm，因此功能上冗余。
    def form_valid(self, form):
        form = AuthenticationForm(data=self.request.POST, request=self.request)

        if form.is_valid():
            delete_sidebar_cache()
            logger.info(self.redirect_field_name)

            auth.login(self.request, form.get_user())
            # YFY：有效期策略：勾选 remember 用 REMEMBER_ME_LOGIN_TTL（30 天），
            # YFY：否则用 SESSION_COOKIE_AGE（默认 2 周）；set_expiry 同时影响 session 与 cookie。
            if self.request.POST.get("remember"):
                self.request.session.set_expiry(settings.REMEMBER_ME_LOGIN_TTL)
                cookie_max_age = settings.REMEMBER_ME_LOGIN_TTL
            else:
                # 使用Django默认的2周
                self.request.session.set_expiry(settings.SESSION_COOKIE_AGE)
                cookie_max_age = settings.SESSION_COOKIE_AGE

            # YFY：logged_user 设为 httponly=False 供前端 JS 读取；它可被伪造，不能用于权限判断。
            # 获取响应对象并设置登录标记 cookie
            response = super(LoginView, self).form_valid(form)
            response.set_cookie(
                'logged_user',
                'true',
                max_age=cookie_max_age,
                httponly=False,  # 允许 JavaScript 访问
                samesite='Lax'
            )
            return response
            # return HttpResponseRedirect('/')
        else:
            return self.render_to_response({
                'form': form
            })

    # YFY：开放重定向防护：只接受同站 host（request.get_host()）的 next；
    # YFY：不合法（含外部域名、协议不匹配）时回退到 success_url='/'。
    def get_success_url(self):

        redirect_to = self.request.POST.get(self.redirect_field_name)
        if not url_has_allowed_host_and_scheme(
                url=redirect_to, allowed_hosts=[
                    self.request.get_host()]):
            redirect_to = self.success_url
        return redirect_to


# YFY：入口：注册成功后跳转（type=register）与邮件激活链接（type=validation）共用此视图。
# YFY：参数：id 定位用户，sign 只在 validation 分支校验；签名算法与 RegisterView 发信时一致。
# YFY：边界：get_object_or_404 在 type 判断之前执行，因此无效 id 返回 404；
# YFY：只有“有效 id + 非法 type”才会重定向到首页。
# YFY：状态策略：用户已激活时直接回首页，激活链接因此是幂等的；但链接本身没有过期时间。
def account_result(request):
    type = request.GET.get('type')
    id = request.GET.get('id')

    user = get_object_or_404(get_user_model(), id=id)
    logger.info(type)
    if user.is_active:
        return HttpResponseRedirect('/')
    if type and type in ['register', 'validation']:
        if type == 'register':
            content = '''
    恭喜您注册成功，一封验证邮件已经发送到您的邮箱，请验证您的邮箱后登录本站。
    '''
            title = '注册成功'
        else:
            # YFY：重新计算签名并逐字符比较；不匹配直接 403，避免仅凭 id 激活任意账号。
            c_sign = get_sha256(get_sha256(settings.SECRET_KEY + str(user.id)))
            sign = request.GET.get('sign')
            if sign != c_sign:
                return HttpResponseForbidden()
            # YFY：激活只改 is_active；save() 不带 update_fields，会触发完整 post_save 信号链路。
            user.is_active = True
            user.save()
            content = '''
            恭喜您已经成功的完成邮箱验证，您现在可以使用您的账号来登录本站。
            '''
            title = '验证成功'
        return render(request, 'account/result.html', {
            'title': title,
            'content': content
        })
    else:
        return HttpResponseRedirect('/')


class ForgetPasswordView(SecureFormView):
    """
    忘记密码视图（重构版）

    使用 SecureFormView 基类，自动提供 CSRF 保护
    """
    form_class = ForgetPasswordForm
    template_name = 'account/forget_password.html'

    # YFY：表单校验完成，视图执行密码加密更新，使用make_password加密后写入BlogUser模型
    # YFY：前置条件：ForgetPasswordForm.clean_email 已确认邮箱存在、clean_code 已确认验证码有效。
    # YFY：并发边界：clean 与这里之间用户可能被删除，filter().get() 仍可能抛 DoesNotExist。
    # YFY：密码策略：make_password 使用当前默认 hasher 生成哈希后直接赋给 password 字段；
    # YFY：强度校验已在表单 password_validation 中完成，这里不重复校验。
    def form_valid(self, form):
        if form.is_valid():
            blog_user = BlogUser.objects.filter(email=form.cleaned_data.get("email")).get()
            blog_user.password = make_password(form.cleaned_data["new_password2"])
            blog_user.save()
            # YFY：改进：密码保存成功后立即删除验证码，避免同一码在 5 分钟 TTL 内被重复使用。
            utils.delete_code(blog_user.email)
            return HttpResponseRedirect('/login/')
        else:
            return self.render_to_response({'form': form})


class ForgetPasswordEmailCode(View):

    # YFY：入口：POST 邮箱后生成 6 位数字码并发送邮件；只校验邮箱格式，不校验邮箱是否已注册。
    # YFY：设计取舍：不暴露“邮箱是否存在”，但也没有发送频率限制，存在被用于邮件轰炸的滥用面。
    # YFY：失败路径：邮箱格式非法返回纯文本“错误的邮箱”，HTTP 状态仍是 200，不是 400。
    def post(self, request: HttpRequest):
        form = ForgetPasswordCodeForm(request.POST)
        if not form.is_valid():
            return HttpResponse("错误的邮箱")
        to_email = form.cleaned_data["email"]

        # YFY：顺序：先发信再写缓存；发信抛异常时不会留下验证码，但接口会返回 500。
        code = generate_code()
        utils.send_verify_email(to_email, code)
        utils.set_code(to_email, code)

        return HttpResponse("ok")
