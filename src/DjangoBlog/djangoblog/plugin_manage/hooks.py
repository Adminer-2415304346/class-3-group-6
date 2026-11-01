import logging

logger = logging.getLogger(__name__)

_hooks = {}

# GCY：register仅将回调加入指定名字的列表；run_action/apply_filters由业务代码显式调用，
# 才执行该名字下已注册的回调。
# SZX：区分注册与执行；Action顺序调用回调，Filter将每次返回值传给下一回调。
# GCY（关键逻辑补充）：_hooks 是进程内全局注册表（name -> callback 列表）。
# run_action 按注册顺序依次执行回调并吞掉单个回调异常，保证一个插件
# 出错不影响后续插件；apply_filters 则把 value 沿回调链传递，某回调抛
# 异常时该次转换被跳过、value 保持上一环的结果。执行边界：注册发生在
# 应用启动（插件 __init__），执行发生在业务代码显式调用处，二者解耦。
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
                logger.error(
                    "Error running action hook '%s' callback '%s': %s", hook_name,
                    getattr(callback, '__name__', type(callback).__name__), e, exc_info=True,
                )


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
                logger.error(
                    "Error applying filter hook '%s' callback '%s': %s", hook_name,
                    getattr(callback, '__name__', type(callback).__name__), e, exc_info=True,
                )
    return value
