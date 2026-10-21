# YFY：模块职责：账号域表单；登录复用 AuthenticationForm，注册复用 UserCreationForm，
# YFY：找回密码是自定义多字段表单（邮箱 + 验证码 + 两次新密码）。
# YFY：职责边界：表单只负责清洗/校验与错误提示；写库、发信、登录会话由 views 完成。
from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.exceptions import ValidationError
from django.forms import widgets
from django.utils.translation import gettext_lazy as _

from . import utils
from .models import BlogUser


# YFY：仅替换用户名/密码控件的样式与 placeholder，认证规则完全继承 AuthenticationForm。
class LoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super(LoginForm, self).__init__(*args, **kwargs)
        self.fields['username'].widget = widgets.TextInput(
            attrs={'placeholder': "username", "class": "form-control"})
        self.fields['password'].widget = widgets.PasswordInput(
            attrs={'placeholder': "password", "class": "form-control"})


# YFY：注册表单在 UserCreationForm 基础上调整控件；字段范围由 Meta.fields 限定为 username/email。
class RegisterForm(UserCreationForm):
    def __init__(self, *args, **kwargs):
        super(RegisterForm, self).__init__(*args, **kwargs)

        self.fields['username'].widget = widgets.TextInput(
            attrs={'placeholder': "username", "class": "form-control"})
        self.fields['email'].widget = widgets.EmailInput(
            attrs={'placeholder': "email", "class": "form-control"})
        self.fields['password1'].widget = widgets.PasswordInput(
            attrs={'placeholder': "password", "class": "form-control"})
        self.fields['password2'].widget = widgets.PasswordInput(
            attrs={'placeholder': "repeat password", "class": "form-control"})

    # YFY：clean_email表单钩子，校验邮箱是否已被注册，防止重复邮箱注册账号
    # YFY：边界：BlogUser.email 没有数据库唯一约束，exists() 检查存在并发竞态；
    # YFY：两个请求同时通过校验时仍可能写入重复邮箱，彻底修复需要模型层唯一约束。
    def clean_email(self):
        email = self.cleaned_data['email']
        if get_user_model().objects.filter(email=email).exists():
            raise ValidationError(_("email already exists"))
        return email

    class Meta:
        model = get_user_model()
        fields = ("username", "email")


# YFY：找回密码表单：清洗顺序为 new_password1 → new_password2 → email → code；
# YFY：clean_code 读取 cleaned_data.email，邮箱失败时为 None，仍会校验并多报一条“验证码错误”。
class ForgetPasswordForm(forms.Form):
    new_password1 = forms.CharField(
        label=_("New password"),
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                'placeholder': _("New password")
            }
        ),
    )

    new_password2 = forms.CharField(
        label="确认密码",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                'placeholder': _("Confirm password")
            }
        ),
    )

    email = forms.EmailField(
        label='邮箱',
        widget=forms.TextInput(
            attrs={
                'class': 'form-control',
                'placeholder': _("Email")
            }
        ),
    )

    code = forms.CharField(
        label=_('Code'),
        widget=forms.TextInput(
            attrs={
                'class': 'form-control',
                'placeholder': _("Code")
            }
        ),
    )

    # YFY：注意：这里读取 self.data 而不是 cleaned_data，等价于再次取原始输入；
    # YFY：password_validation 对 password2 做强度校验，密码不一致时先抛“两次密码不一致”。
    def clean_new_password2(self):
        password1 = self.data.get("new_password1")
        password2 = self.data.get("new_password2")
        if password1 and password2 and password1 != password2:
            raise ValidationError(_("passwords do not match"))
        password_validation.validate_password(password2)

        return password2

    # YFY：存在性校验会向未登录用户暴露“该邮箱是否注册”；注释中的 todo 已记录这一取舍。
    # YFY：若改为统一提示，需要同时调整视图与模板，属于跨层改动。
    def clean_email(self):
        user_email = self.cleaned_data.get("email")
        if not BlogUser.objects.filter(
                email=user_email
        ).exists():
            # todo 这里的报错提示可以判断一个邮箱是不是注册过，如果不想暴露可以修改
            raise ValidationError(_("email does not exist"))
        return user_email

    # YFY：clean_code钩子，调用utils工具类校验用户提交的重置密码验证码是否正确
    # YFY：这里只校验不消费；验证码会在 ForgetPasswordView 保存密码成功后由 delete_code 删除。
    def clean_code(self):
        code = self.cleaned_data.get("code")
        error = utils.verify(
            email=self.cleaned_data.get("email"),
            code=code,
        )
        if error:
            raise ValidationError(error)
        return code


# YFY：申请验证码的表单只做邮箱格式校验，不查询用户是否存在，避免在此接口暴露账号状态。
class ForgetPasswordCodeForm(forms.Form):
    email = forms.EmailField(
        label=_('Email'),
    )
