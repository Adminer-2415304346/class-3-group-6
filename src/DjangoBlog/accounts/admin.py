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

    def save(self, commit=True):
        # 标记用户来源为后台创建，其余逻辑交给父类
        self.instance.source = 'adminsite'
        return super().save(commit=commit)


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
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'nickname', 'usable_password',
                       'password1', 'password2'),
        }),
    )
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
