# SZX（代SY，第7—8周）：适配Django缓存的会话接口；不限定Redis/Memcached后端。
import logging

from django.core.cache import cache
from werobot.session import SessionStorage
from werobot.utils import json_dumps, json_loads

logger = logging.getLogger(__name__)


class MemcacheStorage(SessionStorage):
    def __init__(self, prefix="ws_"):
        self.prefix = prefix
        self.cache = cache

    @property
    def is_available(self):
        # SZX（代SY，第7—8周）：后端不可用时允许选择文件适配器，探测键不长期保留。
        try:
            self.set("checkavaliable", value="1")
            return self.get("checkavaliable") == "1"
        except Exception as error:
            logger.warning("机器人会话缓存不可用：%s", type(error).__name__)
            return False
        finally:
            try:
                self.delete("checkavaliable")
            except Exception as error:
                logger.warning("机器人探测键清理失败：%s", type(error).__name__)

    def key_name(self, s):
        return "{prefix}{s}".format(prefix=self.prefix, s=s)

    def get(self, id):
        # SZX（代SY，第7—8周）：缓存内容为JSON；解析与应用层状态验证分层处理。
        id = self.key_name(id)
        session_json = self.cache.get(id) or "{}"
        return json_loads(session_json)

    def set(self, id, value):
        id = self.key_name(id)
        self.cache.set(id, json_dumps(value))

    def delete(self, id):
        id = self.key_name(id)
        self.cache.delete(id)
