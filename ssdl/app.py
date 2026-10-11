"""Application composition and entry point. Importing this module does not restore data."""
from pathlib import Path

from .app_context import AppContext
from .http_server import BoundedHTTPServer as Server
from .version import APP_NAME, __version__

ROOT = Path(__file__).resolve().parents[1]


def create_app(root: Path = ROOT, **services) -> AppContext:
    return AppContext(root, **services)


def main() -> int:
    with create_app() as app:
        try:
            with Server(("127.0.0.1", app.PORT), app.Handler) as server:
                app.start()
                print(f"{APP_NAME} v{__version__}: http://127.0.0.1:{app.PORT}")
                print(f"儲存位置: {app.state.download_dir}")
                if not app._state()["ready"]:
                    print("尚未安裝完整下載引擎；請執行 setup.bat。")
                server.serve_forever()
        except KeyboardInterrupt:
            print("\n下載工具已停止。")
        except OSError as exc:
            print(f"無法啟動服務：連接埠 {app.PORT} 可能已有下載工具執行。請先關閉原服務。({type(exc).__name__})")
            return 1
    return 0
