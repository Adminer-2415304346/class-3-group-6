import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class SpiderNotify():
    # GCY（类/函数层）：搜索引擎主动推送工具（百度收录）。baidu_notify
    # 把 URL 列表按行拼接后 POST 到 settings.BAIDU_NOTIFY_URL；异常被
    # 吞掉只记日志，推送失败不影响主流程，属于尽力而为的外部通知。
    # 调用方为 blog_signals 的 post_save 回调。限制：非 TESTING 环境下
    # 每次文章保存都触发真实 HTTP 请求，测试需 mock 或跳过。
    @staticmethod
    def baidu_notify(urls):
        try:
            data = '\n'.join(urls)
            # GCY（改进说明）：为外部推送请求增加 5 秒超时，避免百度接口
            # 无响应时阻塞请求线程（B113 告警修复）。
            result = requests.post(settings.BAIDU_NOTIFY_URL, data=data, timeout=5)
            logger.info(result.text)
        except Exception as e:
            logger.error(e)

    @staticmethod
    def notify(url):
        SpiderNotify.baidu_notify(url)
