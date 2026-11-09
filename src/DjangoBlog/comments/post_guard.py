"""WZY（第9—10周 C92）：评论发布限频与重复保护。

设计约定（与《共享配置与接口约定 v1.1》§4/§6 一致）：
- 判断顺序：先识别“重复”（同用户/同文章/同规范化正文/同回复目标），再判断“过频”；
- 阈值全部来自 get_maintenance_option，不在本模块写死；
- 状态落在本 App 的 CommentPostState 表，且必须由调用方放在同一个 transaction.atomic()
  里与评论写入一起提交：评论保存抛错或事务回滚时，状态行一并回滚，不残留冷却，
  也不会触发 post_commit 的缓存失效和邮件通知；
- 并发下靠 (user, scope, state_key) 唯一约束保证只有一个请求能占到状态行，
  Python 侧把 IntegrityError 解释为“重复/过频”，不把缓存后端描述成跨进程原子。
"""

import hashlib
import math
import re
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils.timezone import now

from djangoblog.maintenance_config import get_maintenance_option

from .models import CommentPostState

_WHITESPACE = re.compile(r'\s+')


class CommentPostRejected(Exception):
    """发布被拒绝；message 直接作为表单错误回显给用户。"""

    def __init__(self, code, message, retry_after):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retry_after = retry_after


def normalize_comment_body(body):
    """重复判定用的规范化正文：去首尾空白 + 连续空白折叠为单个空格。

    只用于计算摘要，不改变实际保存的正文（保存的是表单 clean_body 的结果）。
    """
    return _WHITESPACE.sub(' ', (body or '').strip())


def _digest(*parts):
    payload = '\x1f'.join(str(part) for part in parts)
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def duplicate_state_key(article_id, body, parent_comment_id=None):
    """同用户维度之外的重复键摘要：文章 + 规范化正文 + 回复目标。"""
    return _digest('duplicate', article_id, normalize_comment_body(body),
                   parent_comment_id or 0)


def interval_state_key():
    """间隔冷却键：每个用户一条（用户维度已由 state_key 的 user 外键承担）。"""
    return _digest('interval')


def _remaining_seconds(expires_at, at):
    """真实剩余秒数；向上取整且至少 1 秒，避免把“还差 0.4 秒”展示成 0。"""
    return max(1, math.ceil((expires_at - at).total_seconds()))


def _active_state(user_id, scope, state_key, at):
    return CommentPostState.objects.filter(
        user_id=user_id, scope=scope, state_key=state_key,
        expires_at__gt=at).first()


def _reserve(user_id, scope, state_key, expires_at):
    """写状态行：只允许插入；唯一约束冲突（并发请求抢先）时返回 None。

    这里必须用 create 而不是 update_or_create：限频用的是固定 state_key，
    update_or_create 遇到已存在的行会直接改写 expires_at 并返回成功，等于让
    后一个请求无声覆盖前一个请求的抢占结果，两条评论都会入库。
    调用前的 _prune_expired 已清掉到期行，因此插入失败只可能是并发抢占。
    """
    try:
        with transaction.atomic():
            return CommentPostState.objects.create(
                user_id=user_id,
                scope=scope,
                state_key=state_key,
                expires_at=expires_at,
            )
    except IntegrityError:
        return None


def _prune_expired(user_id, at):
    """清理该用户已到期的状态行，避免表无限增长；只动本 App、本用户的记录。"""
    CommentPostState.objects.filter(user_id=user_id, expires_at__lte=at).delete()


def check_and_reserve(user_id, article_id, body, parent_comment_id=None, at=None):
    """校验并占用发布状态；被拒绝时抛 CommentPostRejected。

    必须在调用方的 transaction.atomic() 内执行，且紧随其后完成评论入库，
    这样“状态占用 + 评论写入”是一个原子单元。
    """
    at = at or now()
    duplicate_window = get_maintenance_option("COMMENT_DUPLICATE_WINDOW_SECONDS")
    interval_seconds = get_maintenance_option("COMMENT_INTERVAL_SECONDS")
    _prune_expired(user_id, at)

    duplicate_key = duplicate_state_key(article_id, body, parent_comment_id)
    repeated = _active_state(user_id, CommentPostState.SCOPE_DUPLICATE, duplicate_key, at)
    if repeated is not None:
        remaining = _remaining_seconds(repeated.expires_at, at)
        raise CommentPostRejected(
            'duplicate',
            '该内容与你在 %d 秒内的评论重复，请在 %d 秒后再试.' % (duplicate_window, remaining),
            remaining,
        )

    interval_key = interval_state_key()
    cooled = _active_state(user_id, CommentPostState.SCOPE_INTERVAL, interval_key, at)
    if cooled is not None:
        remaining = _remaining_seconds(cooled.expires_at, at)
        raise CommentPostRejected(
            'rate_limited',
            '评论提交过于频繁，请在 %d 秒后再试.' % remaining,
            remaining,
        )

    expires_duplicate = at + timedelta(seconds=duplicate_window)
    expires_interval = at + timedelta(seconds=interval_seconds)

    if _reserve(user_id, CommentPostState.SCOPE_DUPLICATE,
                duplicate_key, expires_duplicate) is None:
        raise CommentPostRejected(
            'duplicate',
            '该内容与你在 %d 秒内的评论重复，请在 %d 秒后再试.'
            % (duplicate_window, duplicate_window),
            duplicate_window,
        )
    if _reserve(user_id, CommentPostState.SCOPE_INTERVAL, interval_key, expires_interval) is None:
        raise CommentPostRejected(
            'rate_limited',
            '评论提交过于频繁，请在 %d 秒后再试.' % interval_seconds,
            interval_seconds,
        )
