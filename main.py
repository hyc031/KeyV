"""StoreApp 入口：pywebview 本地窗口加载内置网页界面。

运行方式：
    python main.py            （开发调试可加 --debug）
打包为 exe 后直接双击 StoreApp.exe。
"""

import sys
from pathlib import Path


def assets_dir() -> Path:
    """界面资源目录：开发时在 storeapp/web，打包后在临时解包目录。"""
    if getattr(sys, "frozen", False):  # PyInstaller onefile
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        base = Path(__file__).resolve().parent
    return base / "storeapp" / "web"


def main() -> int:
    import webview

    from storeapp.api import Api

    api = Api()
    index = assets_dir() / "index.html"
    if not index.exists():
        raise SystemExit(f"界面资源缺失：{index}")

    window = webview.create_window(
        "StoreApp · 密钥与密码本地存储",
        url=index.as_uri(),
        js_api=api,
        width=1120,
        height=720,
        min_size=(900, 560),
        background_color="#FAFAFA",
    )
    api.bind_window(window)

    def on_closing():
        api.shutdown()
        return True  # 允许关闭

    window.events.closing += on_closing

    webview.start(debug="--debug" in sys.argv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
