"""WZY（第9—10周）：隔离测试本地包装器。

完全沿用官方 `doc/week7-8/tools/run_isolated_tests.py` 的参数与断言口径，只多做一件事：
在 runner 安装“禁止外部命令”补丁之前，先预热导入 `compressor.filters.base`。

原因：`django-compressor` 的 `compressor/filters/base.py` 在**模块导入期**执行
`if platform.system() != "Windows":`，而 Windows 分支下 `platform.system()` 会通过
`platform.win32_ver()` → `subprocess.check_output` 调系统 `ver` 命令。
隔离 runner 为了杜绝真实 shell 执行，把 `subprocess.run/Popen/os.system/os.popen`
全部 patch 成抛 `AssertionError`，于是凡是渲染 `blog/article_detail.html`
（含 `{% compress %}` 标签）的用例都会在模板渲染阶段炸掉，
表现为“7 个失败”，与评论业务逻辑无关。

预热导入只让这段**与环境探测有关**的代码在补丁生效前正常跑一次，
之后测试期间的 subprocess 禁令依旧完整生效，不改变任何被测业务行为。
"""

import os
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
PROJECT = ROOT / 'src' / 'DjangoBlog'
RUNNER = ROOT / 'doc' / 'week7-8' / 'tools' / 'run_isolated_tests.py'

sys.path.insert(0, str(PROJECT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'djangoblog.settings')

if (ROOT / 'doc' / 'week7-8' / 'tools' / 'run_isolated_tests.py').exists():
    import compressor.filters.base  # noqa: F401  预热导入，避开 platform.system() 的子进程调用
    print('[WZY] warm import compressor.filters.base ok (platform detection does not fork)',
          file=sys.stderr)

sys.argv = ['run_isolated_tests.py'] + sys.argv[1:]
runpy.run_path(str(RUNNER), run_name='__main__')
