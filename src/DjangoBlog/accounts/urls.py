# YFY：模块职责：accounts 的路由表；app_name='accounts' 是 application namespace。
# YFY：项目挂载：djangoblog/urls.py 以 include('accounts.urls', namespace='account') 引入，
# YFY：实例命名空间是 account，应用命名空间是 accounts；两种前缀都能反查到同一批路由。
from django.urls import path
from django.urls import re_path

from . import views
from .forms import LoginForm

app_name = "accounts"

urlpatterns = [
# YFY：re_path使用正则匹配url，将/login/路由映射LoginView视图，kwargs传入自定义登录表单类
# YFY：注意：kwargs 是 URL 模式的默认参数，FormView.get_form_kwargs 不会读取它；
# YFY：真正决定表单类型的是 views.LoginView.form_class = LoginForm，这里的传参是冗余配置。
re_path(r'^login/$',
                       views.LoginView.as_view(success_url='/'),
                       name='login',
                       kwargs={'authentication_form': LoginForm}),
# YFY：注册路由映射RegisterView，提交表单后由视图调用RegisterForm完成数据校验
               re_path(r'^register/$',
                       views.RegisterView.as_view(success_url="/"),
                       name='register'),
# YFY：登出路由绑定LogoutView，执行登出逻辑、清除session与登录cookie
               re_path(r'^logout/$',
                       views.LogoutView.as_view(),
                       name='logout'),
# YFY：结果页承载两种业务状态：type=register 展示注册成功，type=validation 校验 id+sign 后激活账号。
               path(r'account/result.html',
                    views.account_result,
                    name='result'),
# YFY：忘记密码页面入口，绑定ForgetPasswordView，页面提交交给ForgetPasswordForm校验
               re_path(r'^forget_password/$',
                       views.ForgetPasswordView.as_view(),
                       name='forget_password'),
# YFY：获取重置密码验证码接口，POST请求，由ForgetPasswordEmailCode视图处理
               re_path(r'^forget_password_code/$',
                       views.ForgetPasswordEmailCode.as_view(),
                       name='forget_password_code'),
               ]
