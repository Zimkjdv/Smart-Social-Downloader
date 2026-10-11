# 專案結構與維護

後端模組集中到 `ssdl/`。根目錄 `app.py` 是簡單入口，`python app.py`、`start.bat` 及既有瀏覽器網址仍可使用。

`ssdl` 是 **Smart Social Downloader** 的縮寫，作為 Python 套件名稱，方便使用 `from ssdl import media` 等匯入。它不代表下載媒體的分類資料夾；平台分類仍使用 `youtube/`、`twitter/` 等名稱。中英文 README 均提供目錄結構及用途。

這份文件描述目前結構。下一階段的 AppContext、初始化生命週期、引擎 adapter、前端控制器與測試 fixture 拆分尚未實作，見 [Roadmap：架構與檔案結構](../ROADMAP.md#架構與檔案結構)。目前 `app` 匯入不啟動 HTTP／worker，但會建立管理器並嘗試恢復登入資料；不應將它視為完全沒有副作用的匯入。

```text
smart-social-downloader/
├── app.py                    # 啟動入口
├── setup.bat                 # 首次安裝／恢復基準依賴
├── start.bat                 # 本機檢查與啟動
├── update.bat                # 主動更新下載引擎
├── requirements.txt          # 引擎更新的相容範圍
├── requirements.lock.txt     # 發布基準依賴
├── requirements-browser.txt  # 選配 Playwright 鎖定版本
├── README.md                 # 英文首頁
├── README_CN.md              # 繁體中文說明
├── CHANGELOG.md              # 應用程式更新紀錄
├── SECURITY.md               # 私人安全回報政策
├── CONTRIBUTING.md           # 貢獻與回報說明
├── ROADMAP.md         # 未完成工作與最新審查
├── LICENSE
├── THIRD_PARTY_NOTICES.md
├── ssdl/                     # Python 後端套件
│   ├── version.py            # 唯一應用程式版本來源
│   ├── app.py                # 狀態擁有者、組裝與啟動
│   ├── http_api.py           # HTTP 路由與本機來源檢查
│   ├── http_server.py        # HTTP 連線上限、讀取期限與 socket 清理
│   ├── scheduler.py          # 排程、額度及生命週期
│   ├── state_repository.py   # 狀態載入、遷移及保存
│   ├── media_selection.py    # 受限播放器選擇
│   ├── job_views.py          # 工作摘要、分頁與檔案明細
│   ├── config.py             # 共用 SSDL_PORT 驗證
│   ├── environment.py        # 啟動／介面共用本機診斷
│   ├── diagnostics.py        # 錯誤／提醒共用遮蔽
│   ├── persistence.py        # schema、原子保存及有效備份恢復
│   ├── media_manifest.py     # 一般媒體來源及完成檔案核對
│   ├── job_runtime.py        # 下載子程序監督、停止及無進度期限
│   ├── job_runner.py         # 下載子程序與匿名管線通訊
│   ├── ipc.py                # 16 MiB frame／64 MiB 訊息分段與驗證
│   ├── process_group.py      # 所屬程序樹／合併工具清理
│   ├── network.py            # 公開 HTTP 目標及實際連線檢查
│   ├── media.py              # 引擎調度、影片／圖片／帳號下載
│   ├── video_quality.py       # 來源尺寸辨識及畫質顯示
│   ├── web_media.py          # 通用 HTML／播放器媒體發現
│   ├── browser_media.py      # 選配臨時 Chrome／受檢查傳輸
│   ├── x_auth.py             # X 登入連接與加密保存
│   ├── x_profiles.py         # 帳號網址及媒體保存紀錄
│   ├── image_history.py      # 圖片直連保存紀錄
│   ├── request_policy.py     # 延時、節流及冷卻
│   ├── download_stats.py     # 容量統計
│   └── thumbnails.py         # 本機縮圖
├── static/                   # HTML、CSS、JavaScript 與語系
│   ├── locales.js            # 固定中英文 key
│   ├── ui_state.js           # 共用頁面狀態
│   ├── job_presentation.js   # 工作格式與列表呈現
│   ├── x_login.js            # X 登入操作
│   ├── media_selection.js    # 播放器選擇
│   ├── ui_accessibility.js   # 彈窗焦點與鍵盤
│   ├── ui_accessibility.css  # 焦點與窄視窗
│   ├── api.js                # 請求期限、JSON 與回應結構驗證
│   ├── app.js                # 介面狀態、操作及呈現
│   ├── job_rows.js           # 資料列保留與變動欄位更新
│   ├── settings.css          # 設定分頁、固定導覽與內容捲動
│   └── i18n.js               # 繁中／英文訊息
├── chrome-extension/         # Chrome X 本機連接器
├── tools/                    # 環境管理與原始碼打包
├── docs/                     # 使用、發布、去重及架構說明
├── tests/                    # 本機 API、下載、串流及發布測試
├── .github/workflows/        # Windows CI
├── data/                     # 本機歷史、設定、登入及快取，排除 Git
├── downloads/                # 預設下載檔，排除 Git
├── .venv/                    # 本機 Python 環境，排除 Git
└── dist/                     # 產生的發布 ZIP，排除 Git
```

## 路徑與匯入規則

- `ssdl.app.ROOT` 固定指向專案根目錄，不取決於呼叫時的工作目錄。整理套件後，既有 `data/`、下載位置及 Chrome 連接器位置保持一致。
- 後端模組採套件內相對匯入；測試使用 `from ssdl import media` 等明確匯入。
- 啟動入口只呼叫 `ssdl.app.main()`；匯入模組不會自動開啟 HTTP 服務或啟動下載 worker。
- `tools/manage.py` 檢查／安裝第三方環境，不讀取正式登入 Cookie 或下載歷史。
- `ssdl/environment.py` 共用於命令列與介面；服務啟動時在獨立執行緒檢查，API 輪詢只讀快取，使用者按「重新檢查」才啟動下一次診斷。外部命令各有逾時，不占用下載 worker。
- `static/api.js` 共用於主介面與 Chrome 連接頁，檢查 JSON 格式與各路由必要欄位；主介面請求期限為 15 秒。只有有效回應會取代主介面的狀態快取，未確認的寫入不自動重送。
- `http_server.py` 限制同時處理 32 條連線；`http_api.py` 使用 BufferedReader／DeadlineReader，標頭與 body 共用 10 秒絕對期限，零碎資料不重設時限。過載先回覆 503，不建立新 handler 執行緒；socket 寫入期限 5 秒，斷線／shutdown 回收服務所屬連線。讀取期限不限制背景下載總耗時，也不承諾 API 內部磁碟操作的總耗時。
- API 狀態在鎖內產生 `state_instance`／`state_sequence`，供介面忽略較舊及已退役服務的回應。服務重啟使用新的實例 ID；序號不保存至紀錄，也不是授權票證。
- Chrome 連接器只接受擴充功能視窗明確選定的本機連接埠，網頁不能更改接收登入資料的目標。設定方式見 [操作與排錯](TROUBLESHOOTING.md)。
- 原始碼打包器使用允許清單；新增來源檔或文件時須確認已被納入。私人檔不應放在原始碼目錄。

## 維護驗證

狀態介面使用後端分頁與全域摘要，按需讀取完整檔案／診斷；資料列依 ID 保留。容量索引與縮圖快取維護獨立於清單呈現，原始媒體不由快取清理刪除。API、量測與限制見 [PERFORMANCE.md](PERFORMANCE.md)。

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
node --test tests/frontend.test.cjs
.\.venv\Scripts\python.exe tools/package_source.py --check
```

測試使用暫存資料夾與本機 HTTP fixture，不需要 X 登入或真實平台下載。API 測試會阻止恢復作者的登入資料。

已拆出共用設定、環境診斷、保存、manifest、程序監督、網路政策、遮蔽及瀏覽器 API 客戶端。`ssdl/app.py` 的 HTTP 路由、排程與保存現已拆出獨立元件；`ssdl/media.py` 的引擎調度仍可視未來需求進一步拆分。

## 工作與資料邊界

HTTP 服務保留佇列、Rate、冷卻、設定及狀態；一個排程 worker 依序啟動 `python -m ssdl.job_runner`。子程序透過匿名管線傳回進度／結果，並向父程序請求 pacing／checkpoint。Cookie 只透過此管線交付，不放進命令列或紀錄。

Windows Job Object 在傳入工作前綁定子程序，其啟動的 FFmpeg／JS helper 由同一組管理。取消、無進度逾時或例外結束只清理此組；排程等待不受無進度時計限制。HTTP 網路 patch 只存在下載子程序，伺服器仍可接受 loopback API。

狀態與有效備份由 `StateStore` 處理，來源完成紀錄使用 SQLite manifest；X 帳號仍使用逐篇 archive。診斷輸出共用遮蔽器且匯出省略歷史網址／檔案路徑。詳細恢復與傳輸限制見 [RELIABILITY.md](RELIABILITY.md)。

歷史候選須先完成離線語法驗證、工作／佇列正規化及設定／冷卻重建，才在 condition 內交換所有狀態。主檔正規化失敗也會嘗試有效備份；損壞輸入另行保留，沒有可恢復候選時阻止自動覆寫。

排程只傳入相同來源／畫質／播放器／保存位置的成功紀錄；X 帳號同步只帶該作者或作者未知的 `i/status` 單篇歷史。`ipc.py` 使用 UTF-8 binary JSON，正常小訊息單 frame、大訊息以 256 KiB 原始資料分段；單 frame 上限 16 MiB，重組後單訊息上限 64 MiB。輸入、RPC、進度、結果與錯誤共用同一協定，容量超限與錯序／中斷分別回報，取消仍由父程序監督。

## P2 模組邊界（2026-10-11）

後端元件明確注入同一 app context，不反向匯入 app；既有入口與回呼保留綁定別名。前端將狀態、列表呈現、X 登入、播放器選擇分離，固定語系 key 放在 `static/locales.js`，焦點管理放在 `ui_accessibility.js`。仍是漸進拆分，沒有切換框架。完整規則與驗收狀態見 [P2_COMPLETION.md](P2_COMPLETION.md)。

## 發布文件與版本

`ssdl/version.py` 提供 `__version__`，由執行中後端輸出至 API 的 `app_version`，前端據此顯示，並供 CLI、診斷匯出及 ZIP 名稱使用。既有 `version` API 欄位仍指 yt-dlp，以維持相容性；引擎、Chrome manifest 及保存 schema 的版本獨立維護。

README 是中英文精簡首頁；完整操作移至 `docs/USAGE.md`、`docs/USAGE_CN.md`。`docs/MAINTENANCE.md` 定義發布流程，`docs/images/dashboard-preview.svg` 為虛構公開示意；`.github/ISSUE_TEMPLATE/` 與 `.github/pull_request_template.md` 定義回報與 PR 內容。原始碼包以允許清單納入這些檔案，排除 runtime 資料。
