# SZX（第9—10周）：集中定义维护任务配置；各App复用入口，共享设置由组长集成。
from types import MappingProxyType

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

DEFAULT_OPTIONS = MappingProxyType({
    "RESET_CODE_TTL_SECONDS": 300,
    "RESET_SEND_COOLDOWN_SECONDS": 60,
    "RESET_MAX_FAILURES": 5,
    "RESET_LOCK_SECONDS": 900,
    "COMMENT_MAX_LENGTH": 2000,
    "COMMENT_INTERVAL_SECONDS": 30,
    "COMMENT_DUPLICATE_WINDOW_SECONDS": 120,
    "OAUTH_STATE_TTL_SECONDS": 300,
    "OAUTH_BIND_TTL_SECONDS": 600,
    "ROBOT_SESSION_TTL_SECONDS": 900,
    "ROBOT_CONFIRM_TTL_SECONDS": 60,
    "ROBOT_COMMAND_TIMEOUT_SECONDS": 10,
    "ROBOT_OUTPUT_MAX_CHARS": 4096,
    "UPLOAD_MAX_BYTES": 5 * 1024 * 1024,
    "UPLOAD_MAX_PIXELS": 20_000_000,
    "UPLOAD_ALLOWED_FORMATS": ("JPEG", "PNG", "WEBP"),
    "ROBOT_ALLOWED_ACTIONS": ("python_version",),
})

_CHOICES = {
    "UPLOAD_ALLOWED_FORMATS": frozenset({"JPEG", "PNG", "WEBP"}),
    "ROBOT_ALLOWED_ACTIONS": frozenset({"python_version"}),
}


def get_maintenance_options():
    """Return validated defaults plus partial settings.MAINTENANCE_OPTIONS overrides."""
    overrides = getattr(settings, "MAINTENANCE_OPTIONS", {})
    if not isinstance(overrides, dict):
        raise ImproperlyConfigured("MAINTENANCE_OPTIONS must be a dictionary")
    if set(overrides) - set(DEFAULT_OPTIONS):
        raise ImproperlyConfigured("Unknown MAINTENANCE_OPTIONS key")

    options = {**DEFAULT_OPTIONS, **overrides}
    for name, value in options.items():
        if name not in _CHOICES:
            if type(value) is not int or value <= 0:
                raise ImproperlyConfigured(f"{name} must be a positive integer")
            continue
        if not isinstance(value, (tuple, list)):
            raise ImproperlyConfigured(f"{name} must be a list or tuple")
        if any(not isinstance(item, str) or item not in _CHOICES[name] for item in value):
            raise ImproperlyConfigured(f"{name} contains an unsupported value")
        if len(set(value)) != len(value):
            raise ImproperlyConfigured(f"{name} must not contain duplicate values")
        if name == "UPLOAD_ALLOWED_FORMATS" and not value:
            raise ImproperlyConfigured("UPLOAD_ALLOWED_FORMATS must not be empty")
        options[name] = tuple(value)
    return options


def get_maintenance_option(name):
    """Read one agreed option without caching overrides across Django settings contexts."""
    if not isinstance(name, str) or name not in DEFAULT_OPTIONS:
        raise ImproperlyConfigured("Unknown maintenance option")
    return get_maintenance_options()[name]
