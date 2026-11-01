# YFY：模块职责：项目唯一的认证后端，把“用户名或邮箱”统一映射到 BlogUser 查询。
# YFY：边界：这里只做凭据校验并返回用户对象，不创建 session；
# YFY：登录动作由 accounts.views.LoginView 调用 auth.login 完成。
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailOrUsernameModelBackend(ModelBackend):
    """
    允许使用用户名或邮箱登录
    """

    # YFY：入口条件：username/password 都可能为 None，必须先拒绝空值；
    # YFY：否则后面的 `'@' in username` 会抛 TypeError，而不是返回认证失败。
    # YFY：分支策略：含 @ 视为邮箱，否则视为用户名；两种输入最终都落到 accounts_bloguser 单表。
    # YFY：激活策略：复用 ModelBackend.user_can_authenticate（即 is_active），
    # YFY：与 Django 默认后端保持一致，避免未激活账号绕过表单在 authenticate() 路径被放行。
    def authenticate(self, request, username=None, password=None, **kwargs):
        user_model = get_user_model()
        if username is None:
            username = kwargs.get(user_model.USERNAME_FIELD)
        if username is None or password is None:
            return None
        if '@' in username:
            lookup = {'email': username}
        else:
            lookup = {'username': username}
        try:
            user = user_model.objects.get(**lookup)
        except user_model.DoesNotExist:
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

    # YFY：Django 会话恢复时调用 get_user(user_id)；参数名沿用 username 但语义是主键 pk。
    def get_user(self, username):
        try:
            return get_user_model().objects.get(pk=username)
        except get_user_model().DoesNotExist:
            return None
