import logging
import time

from ipware import get_client_ip
from user_agents import parse

from blog.documents import ELASTICSEARCH_ENABLED, ElaspedTimeDocumentManager

logger = logging.getLogger(__name__)

# GCY：OnlineMiddleware 在调用后续处理链前开始计时，响应返回后计算耗时、读取客户端信息，并为非流式响应替换耗时占位符。
# SZX：审校修正前置拦截的描述；这里没有拦截请求，Elasticsearch 耗时记录仅在 ELASTICSEARCH_ENABLED 为真时写入。
class OnlineMiddleware(object):
    def __init__(self, get_response=None):
        self.get_response = get_response
        super().__init__()

    def __call__(self, request):
        ''' page render time '''
        start_time = time.time()
        response = self.get_response(request)
        http_user_agent = request.META.get('HTTP_USER_AGENT', '')
        ip, _ = get_client_ip(request)
        user_agent = parse(http_user_agent)
        if not response.streaming:
            try:
                cast_time = time.time() - start_time
                if ELASTICSEARCH_ENABLED:
                    time_taken = round((cast_time) * 1000, 2)
                    url = request.path
                    from django.utils import timezone
                    ElaspedTimeDocumentManager.create(
                        url=url,
                        time_taken=time_taken,
                        log_datetime=timezone.now(),
                        useragent=user_agent,
                        ip=ip)
                response.content = response.content.replace(
                    b'<!!LOAD_TIMES!!>', str.encode(str(cast_time)[:5]))
            except Exception as e:
                logger.error("Error OnlineMiddleware: %s" % e)

        return response
