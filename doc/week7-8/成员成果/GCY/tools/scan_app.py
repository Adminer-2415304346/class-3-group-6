"""GCY原自建入口；SZX集成后转发组长统一驱动，避免不同扫描口径。"""

import runpy
from pathlib import Path

if __name__ == '__main__':
    # SZX：所有参数（包括--output-dir）交统一驱动处理；既有证据目录拒绝覆盖。
    driver = Path(__file__).resolve().parents[3] / 'tools' / 'scan_app.py'
    runpy.run_path(str(driver), run_name='__main__')
