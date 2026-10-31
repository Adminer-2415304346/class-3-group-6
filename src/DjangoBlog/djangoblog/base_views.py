#!/usr/bin/env python
# encoding: utf-8

"""
Django Blog 基础视图类
提供带有常用装饰器的视图基类，减少重复的 dispatch 方法定义
"""

from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.debug import sensitive_post_parameters
from django.views.generic import FormView, RedirectView


class SecureFormView(FormView):
    """
    安全的 FormView 基类

    自动添加 CSRF 保护，适用于所有需要表单提交的视图

    Usage:
        class MyFormView(SecureFormView):
            form_class = MyForm
            template_name = 'my_form.html'

            def form_valid(self, form):
                # 处理表单数据
                return super().form_valid(form)
    """
    # GCY（类/函数层）：公共表单视图基类，调用方为 accounts/comments
    # 等 app 的表单视图。通过重写 dispatch 统一叠加装饰器，子类无需
    # 重复声明。约定：子类只实现 form_class/template_name 与
    # form_valid 即可，dispatch 的签名（含 *args, **kwargs）保持不变，
    # 以保证 method_decorator 能正确包裹任何 HTTP 方法。

    @method_decorator(csrf_protect)
    def dispatch(self, *args, **kwargs):
        """添加 CSRF 保护"""
        return super().dispatch(*args, **kwargs)


class AuthenticatedFormView(FormView):
    """
    需要登录的 FormView

    自动检查用户登录状态并添加 CSRF 保护
    未登录用户会被重定向到登录页面

    Usage:
        class MyAuthFormView(AuthenticatedFormView):
            form_class = MyForm
            template_name = 'my_form.html'
    """

    @method_decorator(login_required)
    @method_decorator(csrf_protect)
    def dispatch(self, *args, **kwargs):
        """添加登录要求和 CSRF 保护"""
        return super().dispatch(*args, **kwargs)


class LoginFormView(FormView):
    """
    登录专用 FormView

    包含以下保护措施：
    - 敏感参数保护（password 等）
    - CSRF 保护
    - 禁用缓存（防止登录状态被缓存）

    Usage:
        class LoginView(LoginFormView):
            form_class = LoginForm
            template_name = 'login.html'

            def form_valid(self, form):
                # 处理登录逻辑
                return super().form_valid(form)
    """

    @method_decorator(sensitive_post_parameters('password'))
    @method_decorator(csrf_protect)
    @method_decorator(never_cache)
    def dispatch(self, request, *args, **kwargs):
        """添加敏感参数保护、CSRF 保护和禁用缓存"""
        return super().dispatch(request, *args, **kwargs)


class LogoutRedirectView(RedirectView):
    """
    登出专用 RedirectView

    自动禁用缓存，确保登出操作不会被缓存

    Usage:
        class LogoutView(LogoutRedirectView):
            url = '/login/'

            def get(self, request, *args, **kwargs):
                logout(request)
                return super().get(request, *args, **kwargs)
    """
    # GCY（类/函数层）：登出视图基类。never_cache 保证登出响应带
    # Cache-Control: no-cache，防止浏览器回退后仍显示已登录页面。
    # 子类 get 中应先执行 logout(request) 再调用父类重定向，父类
    # dispatch 不感知具体登出逻辑，只负责缓存策略。

    @method_decorator(never_cache)
    def dispatch(self, request, *args, **kwargs):
        """禁用缓存"""
        return super().dispatch(request, *args, **kwargs)


class NoCacheFormView(FormView):
    """
    禁用缓存的 FormView

    适用于需要实时数据的表单（如验证码、动态内容等）

    Usage:
        class MyCacheDisabledFormView(NoCacheFormView):
            form_class = MyForm
            template_name = 'my_form.html'
    """

    @method_decorator(never_cache)
    @method_decorator(csrf_protect)
    def dispatch(self, request, *args, **kwargs):
        """禁用缓存并添加 CSRF 保护"""
        return super().dispatch(request, *args, **kwargs)
