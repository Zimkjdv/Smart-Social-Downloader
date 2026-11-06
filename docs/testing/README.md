# 驗收程序 / Acceptance procedures

先看[測試指南](../development/TESTING.md)建立依賴與合成回歸基準，再依變更範圍選擇下列 gate。各文件定義自己的輸入、所有權、實際斷言與剩餘環境限制；工具存在或曾在別的版本通過，不代表本次已驗收。

## Windows 與 Chrome

| 程序 | 用途 |
| --- | --- |
| [Installation](INSTALLATION_ACCEPTANCE.md) | 新來源／venv、安裝、更新與基準恢復 |
| [Console](CONSOLE_ACCEPTANCE.md) | 真正 Ctrl+C、worker 清理與佇列恢復 |
| [Background lifecycle](DESKTOP_ACCEPTANCE.md) | 背景服務、重複啟動、停止與專案隔離 |
| [Desktop GUI](DESKTOP_GUI_ACCEPTANCE.md) | Browser／WebView2 契約、原生視窗、媒體與人工操作 |
| [Chrome pairing](CHROME_PAIRING_ACCEPTANCE.md) | 一般 Chrome、票證生命週期、登入回接與保存 |

## Docker

| 程序 | 用途 |
| --- | --- |
| [Runtime](DOCKER_ACCEPTANCE.md) | FFmpeg／Node、來源排除與 runtime |
| [Service and storage](DOCKER_SERVICE_ACCEPTANCE.md) | Compose、健康、持久化、備份與恢復 |
| [Login and media](DOCKER_INTERACTION_ACCEPTANCE.md) | 合成登入、加密保存與 HTTP 媒體 |
| [Host storage](DOCKER_HOST_ACCEPTANCE.md) | 真正 host bind、權限與檔案型 secret |
| [Host browser](DOCKER_BROWSER_ACCEPTANCE.md) | Chrome 操作、PNG 解碼、H.264 播放及跳轉 |
| [Upgrade and rollback](DOCKER_UPGRADE_ACCEPTANCE.md) | 不同來源映像升級、時間保存與備份回復 |

## Pixiv

| 程序 | 用途 |
| --- | --- |
| [Author works](PIXIV_ACCEPTANCE.md) | 已授權真實作者同步與檔案核對 |
| [Authorization](PIXIV_AUTH_ACCEPTANCE.md) | PKCE、取消／過期、callback、保存與失效登入 |
| [Directories](PIXIV_PATH_ACCEPTANCE.md) | 作者名稱、舊路徑、換根目錄與部分重用 |
| [Recovery](PIXIV_RECOVERY_ACCEPTANCE.md) | 新增、缺頁、停止、限流及部分傳輸 |

依賴警告／傳輸 gate 見[故障追蹤](../development/DEPENDENCY_FAULTS.md)。Pixiv 單篇 URL 身份的合成驗證歸在[去重契約](../reference/DOWNLOAD_DEDUP.md#reproduction-and-scope)。日期與結果見[歷史紀錄](../history/TEST_RESULTS.md)，尚未完成的跨環境工作見 [Roadmap](../development/ROADMAP.md)。
