# X 本機連接器

第一次：在一般 Chrome 開啟 chrome://extensions → 開啟開發人員模式 → 載入未封裝項目 → 選擇此資料夾。

在日常使用的 Chrome 確認 X 已登入，從下載工具按「連接 Chrome 登入」，或打開此擴充功能並按「連接已登入的 X」。連接器只讀取 X 登入 Cookie，傳到這台電腦上的 `http://127.0.0.1:8765`（預設），工具以 Windows 加密保存。不使用受控登入瀏覽器，不讀取 Google、Apple 或其他網站登入資料。

## 自訂連接埠

後端以 `SSDL_PORT` 設定其他連接埠時，打開擴充功能視窗，展開「本機連接設定」，填入相同的數字再按連接。例如後端使用 `8877`，連接器也填入 `8877`。視窗顯示實際目的地並提供開啟工具的連結；此設定只改變連接器，不替後端變更連接埠。

只有使用者在擴充功能視窗操作，才能更改保存的目的地；工具網頁無法自動選定其他連接埠。連接頁來源不符時，在讀取 Cookie 前拒絕，顯示兩邊的數字及修正方式。所有目的地固定使用 `127.0.0.1`，不接受任意遠端伺服器。數字範圍 1～65535，預設為 8765。

## 更新現有連接器

目前版本 **1.1.0**。檔案更新後，在 `chrome://extensions` 按此連接器的重新載入按鈕，再重新整理本機連接頁。公開 manifest key 與 extension ID 保持不變。

本版增加 `storage` 權限，僅用於保存選定的本機連接埠；擴充功能不保存 X Cookie 副本。Cookie 仍只在使用者連接時傳送到本機，由 Windows 加密保存。首次安裝則直接載入新版資料夾即可。

## 權限與排錯

Chrome 要求擴充功能具有 cookies 與相應網站權限，才能透過正式 API 讀取登入 Cookie。首次載入需由使用者操作。若 X 限制帳號登入，需先依 X 官方說明解除限制；連接器無法解除帳號限制。

從 Chrome 擴充功能頁移除此連接器，可撤回瀏覽器端 Cookie 權限。工具設定中的「停用連接」移除工具已保存的加密登入狀態。

若連接頁顯示 Windows 無法使用登入資料加密，請關閉下載工具服務，從一般 Windows 桌面執行 `start.bat`，再重新整理連接頁並按連接。受限制的自動化程序或沙箱可能無法使用目前使用者的 Windows 加密金鑰；此錯誤不代表 X 帳號登入失敗。失敗的配對會清除頁面上的一次性票證，下次點擊會重新取得；主介面在連接或等待期間每兩秒更新狀態，也可以取消等待。

官方文件：

- [Chrome cookies API](https://developer.chrome.com/docs/extensions/reference/api/cookies)
- [載入未封裝擴充功能](https://developer.chrome.com/docs/extensions/get-started/tutorial/hello-world#load-unpacked)
- [Chrome storage API](https://developer.chrome.com/docs/extensions/reference/api/storage)

完整排錯：[安裝、狀態更新與 X 登入](../docs/TROUBLESHOOTING.md)。本輪新版的自訂連接埠配對尚未實際驗證。
