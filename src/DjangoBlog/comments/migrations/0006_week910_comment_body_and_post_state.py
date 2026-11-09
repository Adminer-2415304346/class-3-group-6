# WZY（第9—10周 C91/C92）：评论正文上限对齐共享配置，并新增发布状态表。
# 说明：
# 1) Comment.body 的 max_length 由 300 调整为 2000（COMMENT_MAX_LENGTH 默认值），
#    该参数只参与模型/表单校验，不改变 MySQL TEXT 列的物理存储能力；
# 2) 新增 CommentPostState，用于 C92 的限频与重复保护，
#    状态行与评论写入同事务提交，回滚即失效。
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('comments', '0005_commentreaction'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='comment',
            name='body',
            field=models.TextField(max_length=2000, verbose_name='正文'),
        ),
        migrations.CreateModel(
            name='CommentPostState',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('scope', models.CharField(choices=[('interval', 'comment interval'), ('duplicate', 'duplicate comment')], max_length=16, verbose_name='scope')),
                ('state_key', models.CharField(max_length=64, verbose_name='state key')),
                ('expires_at', models.DateTimeField(verbose_name='expires at')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='updated at')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='user')),
            ],
            options={
                'verbose_name': 'comment post state',
                'verbose_name_plural': 'comment post state',
                'indexes': [models.Index(fields=['scope', 'expires_at'], name='idx_cmt_state_expire')],
                'constraints': [models.UniqueConstraint(fields=('user', 'scope', 'state_key'), name='uniq_comment_post_state')],
            },
        ),
    ]
