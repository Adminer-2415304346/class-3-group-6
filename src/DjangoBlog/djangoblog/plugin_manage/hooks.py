import logging

logger = logging.getLogger(__name__)

_hooks = {}

# GCY：register 仅将回调加入指定名字的钩子列表；业务代码显式调用 run_action 或 apply_filters 时，才执行该名字下已注册的回调。
# SZX：审校区分注册与执行；Action 顺序调用回调，Filter 将每次返回值传给下一回调，不是由事件名自动触发。
def register(hook_name: str, callback: callable):
    """
    注册一个钩子回调。
    """
    if hook_name not in _hooks:
        _hooks[hook_name] = []
    _hooks[hook_name].append(callback)
    logger.debug(f"Registered hook '{hook_name}' with callback '{callback.__name__}'")


def run_action(hook_name: str, *args, **kwargs):
    """
    执行一个 Action Hook。
    它会按顺序执行所有注册到该钩子上的回调函数。
    """
    if hook_name in _hooks:
        logger.debug(f"Running action hook '{hook_name}'")
        for callback in _hooks[hook_name]:
            try:
                callback(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error running action hook '{hook_name}' callback '{callback.__name__}': {e}", exc_info=True)


def apply_filters(hook_name: str, value, *args, **kwargs):
    """
    执行一个 Filter Hook。
    它会把 value 依次传递给所有注册的回调函数进行处理。
    """
    if hook_name in _hooks:
        logger.debug(f"Applying filter hook '{hook_name}'")
        for callback in _hooks[hook_name]:
            try:
                value = callback(value, *args, **kwargs)
            except Exception as e:
                logger.error(f"Error applying filter hook '{hook_name}' callback '{callback.__name__}': {e}", exc_info=True)
    return value
