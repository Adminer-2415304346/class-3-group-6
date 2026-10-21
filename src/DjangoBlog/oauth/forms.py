# GZX：本模块只服务"第三方未返回邮箱"时的补绑表单，被 RequireEmailView 使用；
# 只做字段级校验，不承担身份鉴权，鉴权与落库在 views 层完成。
from django.contrib.auth.forms import forms
from django.forms import widgets


class RequireEmailForm(forms.Form):
    # GZX：email 由 EmailField 做格式必填校验；oauthid 是隐藏字段，仅携带 OAuthUser 主键，
    # 它不是权限凭证——隐藏值可被前端篡改，不能用来证明当前会话拥有该第三方账号。
    email = forms.EmailField(label='电子邮箱', required=True)
    oauthid = forms.IntegerField(widget=forms.HiddenInput, required=False)

    def __init__(self, *args, **kwargs):
        # GZX：渲染时把邮箱输入框换成 EmailInput 并加样式占位，不改校验规则。
        super(RequireEmailForm, self).__init__(*args, **kwargs)
        self.fields['email'].widget = widgets.EmailInput(
            attrs={'placeholder': "email", "class": "form-control"})
