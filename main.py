"""StoreApp 入口。

运行方式：
    python main.py
打包为 exe 后直接双击 StoreApp.exe 即可。
"""

import sys

from storeapp.ui.main_window import run


def main() -> int:
    run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
