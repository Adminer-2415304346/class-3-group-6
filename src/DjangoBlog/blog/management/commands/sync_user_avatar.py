# SZX（第7—8周）：批量同步OAuth头像，会访问远程URL、写静态文件并更新绑定记录，不能当只读命令。
import requests
from django.core.management.base import BaseCommand
from django.templatetags.static import static

from djangoblog.utils import save_user_avatar
from oauth.models import OAuthUser
from oauth.oauthmanager import get_manager_by_type


class Command(BaseCommand):
    help = 'sync user avatar'

    # SZX（第7—8周）：用2秒GET探测头像，只有200返回True；其他状态或异常隐式返回None。
    def test_picture(self, url):
        try:
            if requests.get(url, timeout=2).status_code == 200:
                return True
        except:
            pass

    # SZX（第7—8周）：遍历全部OAuth绑定；有效本地头像跳过，否则解析资料、下载或设置默认头像。
    def handle(self, *args, **options):
        static_url = static("../")
        users = OAuthUser.objects.all()
        self.stdout.write(f'开始同步{len(users)}个用户头像')
        for u in users:
            self.stdout.write(f'开始同步:{u.nickname}')
            url = u.picture
            if url:
                if url.startswith(static_url):
                    if self.test_picture(url):
                        continue
                    else:
                        if u.metadata:
                            # SZX（第7—8周）：渠道管理器或资料无效时缺少兜底。
                            manage = get_manager_by_type(u.type)
                            url = manage.get_picture(u.metadata)
                            url = save_user_avatar(url)
                        else:
                            url = static('blog/img/avatar.png')
                else:
                    url = save_user_avatar(url)
            else:
                url = static('blog/img/avatar.png')
            if url:
                self.stdout.write(
                    f'结束同步:{u.nickname}.url:{url}')
                # SZX（第7—8周）：此处只保存 OAuth 的 picture，不更新本地用户。
                u.picture = url
                u.save()
        self.stdout.write('结束同步')
