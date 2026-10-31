from django.apps import AppConfig

class DjangoblogAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'djangoblog'

    def ready(self):
        # GCY（类/函数层）：Django 应用就绪钩子，进程启动时由应用注册表
        # 调用一次（含 manage.py、WSGI、测试 runner）。此处延迟导入插件
        # 加载器以避免循环依赖（loader 依赖 settings），并保证在模型和
        # URL 系统就绪后再注册插件钩子。若插件目录缺失或个别插件导入
        # 失败，load_plugins 内部捕获异常，不会阻断应用启动。
        super().ready()
        # Import and load plugins here
        from .plugin_manage.loader import load_plugins
        load_plugins() 