# GZX（第9—10周 O92）：新增 PendingBinding 一次性待绑定证明表。
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('oauth', '0003_alter_oauthuser_nickname'),
    ]

    operations = [
        migrations.CreateModel(
            name='PendingBinding',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email', models.CharField(max_length=255, verbose_name='email')),
                ('nonce', models.CharField(max_length=64, unique=True, verbose_name='nonce')),
                ('browser_context', models.CharField(max_length=64, verbose_name='browser context')),
                ('expires_at', models.DateTimeField(verbose_name='expires at')),
                ('consumed', models.BooleanField(default=False, verbose_name='consumed')),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now, verbose_name='creation time')),
                ('oauth_user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='pending_bindings',
                    to='oauth.oauthuser',
                    verbose_name='oauth user')),
            ],
            options={
                'verbose_name': 'pending oauth binding',
                'ordering': ['-created_at'],
            },
        ),
    ]
