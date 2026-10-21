# YFY：模块职责：把 BlogUser 注册到 Django admin，定义后台新增/修改表单与列表展示字段。
# YFY：边界：新增表单继承 AdminUserCreationForm，以兼容 Django 5.1+ 的 usable_password；
# YFY：密码校验、哈希与保存均由父类完成，本模块只补充 nickname/email 字段与 source 标记。
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import AdminUserCreationForm
from django.contrib.auth.forms import UserChangeForm
from django.contrib.auth.forms import UsernameField

# Register your models here.
from .models import BlogUser


# YFY：BlogUserCreationForm用于后台新增用户，适配Django5.1+ usable_password字段，标记用户来源为adminsite
class BlogUserCreationForm(AdminUserCreationForm):
    """后台“新增用户”表单。

    Django 5.1 起 UserAdmin.add_fieldsets 中新增了 usable_password 字段，
    对应的 add_form 必须是 AdminUserCreationForm（或其子类），
    否则新增用户页面会抛出
    FieldError: Unknown field(s) (usable_password) specified for BlogUser。
    密码校验、usable_password 处理以及密码加密保存均由父类完成。
    """

    class Meta:
        model = BlogUser
        fields = ('username', 'email', 'nickname')
        field_classes = {'username': UsernameField}

    # YFY：先写 source 再委托父类保存；commit=False 时只改内存实例，由调用方决定何时落库。
    def save(self, commit=True):
        # 标记用户来源为后台创建，其余逻辑交给父类
        self.instance.source = 'adminsite'
        return super().save(commit=commit)


# YFY：修改表单使用 UserChangeForm；fields='__all__' 会包含 AbstractUser 的 password 只读展示字段。
class BlogUserChangeForm(UserChangeForm):
    class Meta:
        model = BlogUser
        fields = '__all__'
        field_classes = {'username': UsernameField}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


# YFY：BlogUserAdmin为自定义用户后台管理类，绑定BlogUser模型，配置列表展示、搜索、新增编辑表单
class BlogUserAdmin(UserAdmin):
    form = BlogUserChangeForm
    add_form = BlogUserCreationForm
    # YFY：新增页字段必须与 AdminUserCreationForm 支持的字段一致，否则 add_view 会抛 FieldError。
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'nickname', 'usable_password',
                       'password1', 'password2'),
        }),
    )
    # YFY：列表不展示 is_active/source 的筛选器；账号激活状态需要在修改页查看。
    list_display = (
        'id',
        'nickname',
        'username',
        'email',
        'last_login',
        'date_joined',
        'source')
    list_display_links = ('id', 'username')
    ordering = ('-id',)
    search_fields = ('username', 'nickname', 'email')
