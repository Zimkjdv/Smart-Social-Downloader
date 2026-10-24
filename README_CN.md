# Smart Social Downloader

[English](README.md) | 繁體中文

在自己電腦執行的影片與圖片下載管理工具。貼上網址即可排隊下載，媒體依平台分類保存。使用 **yt-dlp**、**gallery-dl** 與 **FFmpeg**。

**Windows · Python 3.12 · MIT · 預覽版 0.1.0-preview.2（尚未發布）**

![Smart Social Downloader 介面示意](docs/images/dashboard-preview.svg)

*展示圖使用虛構帳號、網址與插畫，不包含個人下載紀錄。*

## 核心功能

- **影片與圖片下載**：多平台網址、原生 HLS／DASH、可取得的原尺寸圖片，以及平台／帳號資料夾。
- **畫質選擇**：預設最高可用畫質，可選 2160p～144p 高度上限；合併影音串流時不重新編碼。
- **選配 JavaScript 捕捉**：使用臨時 Chrome 工作階段發現動態影音來源，再交給原有下載流程。[啟用方法](docs/DYNAMIC_CAPTURE.md)。
- **X 帳號媒體**：先掃描可存取的圖片與影片並顯示總數，核對原位置檔案，再補抓新增或缺少的內容。
- **Pixiv 作者作品**：OAuth 登入設定、先掃描總數、插畫／漫畫原圖與動圖原始影格、`pixiv/作者名(ID)/` 資料夾，以及核對檔案後的增量補抓。[操作說明](docs/PIXIV.md) · [實際作者驗收](docs/PIXIV_ACCEPTANCE.md)。
- **背景佇列**：單 worker、3～8 秒延時、可調每小時額度、獨立／共用平台冷卻，以及暫停、停止與重新下載。
- **清單管理**：本機縮圖、SIZE／TIME、播放／查看／開啟資料夾、篩選、分頁及保存紀錄。
- **本機操作**：繁中／英文介面、Windows 加密保存 X／Pixiv 登入、環境診斷與經遮蔽的診斷匯出。

## 快速開始

1. 在 Windows 安裝 **Python 3.12**，下載並解壓專案原始碼。
2. 執行 **`setup.bat`**，建立 `.venv` 並安裝鎖定版本的基準套件。
3. 執行 **`start.bat`**，服務會在背景運行，就緒後自動開啟網頁。
4. 在瀏覽器開啟 [http://127.0.0.1:8765](http://127.0.0.1:8765)，貼上媒體網址並按 **加入下載佇列**。

尚未完成安裝時，`start.bat` 會先安裝；後續啟動只檢查本機環境，不安裝或更新套件。保持後端執行，重新整理或關閉網頁不會停止下載。

YouTube 等部分網站需要 **Node.js 22+ 或 Deno 2.3+**。環境診斷提示需要 runtime 時，安裝並重新啟動服務。詳見 [安裝與排錯](docs/TROUBLESHOOTING.md)。

下載需要登入的 X 內容時，先在一般 Chrome 登入 X，再使用 **設定 → X 登入**。如需連接器，依 [首次安裝步驟](chrome-extension/README.md) 載入。工具連接既有登入狀態，不代為執行 Google／Apple 登入。

Pixiv 請使用 **設定 → Pixiv 登入** 按「一鍵連接 Pixiv」，在一般 Chrome 完成登入後自動連接。首次需載入／更新並重新載入 1.2.0 連接器；再選 **Pixiv 作者作品** 貼上作者網址或數字 ID。詳見 [Pixiv 說明](docs/PIXIV.md)；Windows 作者下載／恢復主流程已通過實際驗收，其他授權與平台情境仍待完成。

### Windows 背景啟動與停止

- **`start.bat`**：檢查／安裝環境後，在背景啟動並自動開啟網頁。重複執行會開啟既有服務，不重複啟動。
- **`stop.bat`**：正常停止背景服務，保存佇列並清理下載子程序。關閉瀏覽器不會停止背景服務。
- 啟動失敗請查看 **`data/background.log`**。若原本有前景服務，請先在原控制台按 **Ctrl+C**，再改用背景模式。
- 如需顯示控制台，執行 **`.venv\Scripts\python.exe -X utf8 tools\manage.py start`**，並用 Ctrl+C 停止。Docker 啟動方式不變。

自訂連接埠、停止逾時與程序管理詳見 [桌面背景服務](docs/DESKTOP_SERVICE.md)，測試情境與限制見 [原生背景啟停驗收](docs/DESKTOP_ACCEPTANCE.md)。

### Chrome 連接器：首次安裝

請使用你平常登入 X 或 Pixiv 的一般 Chrome 個人檔案，安裝時保持下載工具運行。

1. 在已解壓的專案中找到 **`chrome-extension`** 資料夾；也可在工具的連接頁按 **下載 Chrome 連接器**，下載後先解壓 ZIP。
2. 在 Chrome 網址列輸入 **`chrome://extensions`**。
3. 開啟右上角的 **開發人員模式**。
4. 按 **載入未封裝項目**，選擇 **內含 `manifest.json` 的 `chrome-extension` 資料夾**。不要選 ZIP、`manifest.json` 檔案本身或整個專案根目錄。
5. 確認 **Smart Social Downloader · X / Pixiv 連接器** 已啟用；Chrome 若要求批准網站存取權限，請依提示確認。
6. 回到本機連接頁並重新整理，讓頁面偵測已載入的連接器。
7. 在工具使用 **設定 → X 登入** 連接既有 X 登入狀態，或按 **設定 → Pixiv 登入 → 一鍵連接 Pixiv**。在 Chrome 完成 Pixiv 登入／驗證後會自動接回，不用 F12 或複製 code。

**已安裝者更新：** 更新原本載入資料夾內的檔案，到 `chrome://extensions` 按連接器的 **重新載入**，再重新整理連接頁。**1.2.0** 新增 Pixiv 網站／`webRequest` 權限，若 Chrome 要求請重新批准。擴充功能 ID 維持不變，不需要移除既有安裝。

**自訂連接埠／Docker：** 工具使用非 `8765` 連接埠時，請先在擴充功能視窗的 **本機連接設定** 選擇相同數字。Docker 使用者需在 **主機 Chrome** 安裝，選擇主機已解壓的連接器資料夾。權限與排錯詳見 [連接器說明](chrome-extension/README.md)及 [Pixiv 說明](docs/PIXIV.md)。

## 限制與支援範圍

- 可下載內容取決於平台、解析器及帳號存取權限；不能保證任何網址都可下載。已刪除、無法存取或 DRM 內容可能無法取得。
- 「原尺寸／最高畫質」指平台提供的版本，無法還原平台壓縮前的上傳原檔。
- 通用解析支援靜態 HTML、播放器資料及嵌入頁面；多播放器可先選擇再下載。選配動態捕捉需要 Playwright 與一般 Chrome；互動、登入專用或 DRM 傳輸仍可能無法取得。
- 延時與限流不能保證不受平台限制。預設最近 60 分鐘最多啟動 40 個工作，失敗與重試也計入；每次最多 30 個網址，清單最多 200 個工作紀錄。
- 目前優先支援 Windows；macOS／Linux、乾淨 Windows／Chrome 配對及所有預覽版流程尚未完整驗收。未完成工作與驗收進度見 [Roadmap](ROADMAP.md)。

## 詳細文件

| 文件 | 內容 |
| --- | --- |
| [繁體中文操作指南](docs/USAGE_CN.md)／[English usage](docs/USAGE.md) | 設定、畫質、檔案操作、X 同步、限流與 CLI |
| [操作與排錯](docs/TROUBLESHOOTING.md) | 安裝、診斷、本機 API 與登入問題 |
| [Chrome 連接器](chrome-extension/README.md) | 安裝、配對、自訂連接埠及重新載入 |
| [影片畫質](docs/VIDEO_QUALITY.md) · [已下載檔案檢查](docs/DOWNLOAD_DEDUP.md) · [內容雜湊評估](docs/CONTENT_HASH_ASSESSMENT.md) | 畫質、保存位置與避免重複下載 |
| [JavaScript 捕捉](docs/DYNAMIC_CAPTURE.md) · [測試紀錄](docs/TESTING.md) | 選配安裝、捕捉限制、回歸與瀏覽器驗收 |
| [專案複查](docs/PROJECT_AUDIT.md) | 本輪重現問題、修正與剩餘驗收 |
| [可靠性](docs/RELIABILITY.md) · [效能](docs/PERFORMANCE.md) | 恢復、停止、串流完整性、分頁與快取 |
| [架構](docs/ARCHITECTURE.md) · [P2 實作](docs/P2_COMPLETION.md) | 模組分工、語系 key、播放器選擇與冷卻 |
| [發布與隱私](docs/RELEASE.md) · [維護指南](docs/MAINTENANCE.md) | 原始碼包、版本規則及發布清單 |
| [安裝驗收](docs/INSTALLATION_ACCEPTANCE.md) · [控制台驗收](docs/CONSOLE_ACCEPTANCE.md) | 全新來源／venv、更新恢復、真正 Ctrl+C 與 Windows CI |
| [Docker 部署](docs/DOCKER.md) · [儲存與回復](docs/DOCKER_STORAGE.md) | 實驗性 Linux amd64 設定、健康檢查、持久化、備份與回復；仍待主機／瀏覽器驗收 |
| [Docker 登入與檔案](docs/DOCKER_LOGIN.md) | 主機 Chrome 配對、記憶體／獨立金鑰登入及瀏覽器媒體操作 |
| [Docker runtime 驗收](docs/DOCKER_ACCEPTANCE.md) | 隔離映像／建置內容、合成 FFmpeg／Node 檢查與 Linux CI |
| [Docker 服務驗收](docs/DOCKER_SERVICE_ACCEPTANCE.md) | 隔離 Compose 啟動、儲存、備份還原、故障恢復與本機連線檢查 |
| [Docker 登入／媒體驗收](docs/DOCKER_INTERACTION_ACCEPTANCE.md) | 合成登入、加密重啟／金鑰恢復及原始位元組 HTTP 檔案讀取 |
| [Docker 主機儲存驗收](docs/DOCKER_HOST_ACCEPTANCE.md) | 真正私有主機掛載、檔案型 secret 及加密登入備份／恢復 |
| [Docker 主機 Chrome 驗收](docs/DOCKER_BROWSER_ACCEPTANCE.md) | 實際檔案 UI／鍵盤操作、PNG 解碼與 H.264 播放 |

首頁及操作指南提供中英文；維護、貢獻與安全回報文件以英文為主。

## 專案結構

```text
smart-social-downloader/
├── app.py                         服務啟動入口
├── stop.bat                       正常停止這個專案的背景服務
├── setup.bat / start.bat           安裝及啟動
├── update.bat                     主動更新引擎
├── Dockerfile / compose.yaml      實驗性 Linux amd64 部署
├── compose.login.yaml             選配：獨立金鑰加密保存 X／Pixiv 登入
├── .dockerignore / docker/        建置允許清單、快照、入口、健康及儲存工具
├── requirements*.txt              更新相容範圍／鎖定基準／選配捕捉
├── README.md / README_CN.md        英文／繁體中文首頁
├── CHANGELOG.md                   應用程式更新紀錄
├── SECURITY.md / CONTRIBUTING.md   私人安全回報／貢獻說明
├── LICENSE / THIRD_PARTY_NOTICES.md
├── ROADMAP.md               未完成工作與驗收進度
├── ssdl/                          Python 後端套件
│   ├── version.py                 唯一應用程式版本來源
│   ├── app.py                     組裝入口
│   ├── desktop_service.py  Windows background ownership / graceful stop
│   ├── app_context.py             具型別的狀態、服務與生命週期
│   ├── session_storage.py         DPAPI／獨立金鑰／記憶體登入保存
│   ├── local_media.py             限定工作檔案的有界網頁媒體讀取
│   ├── state_writer.py            不可變快照、合併更新及保存確認
│   ├── database_maintenance.py    SQLite 診斷、有效備份及 VACUUM
│   ├── json_budget.py             保存及 IPC 的 UTF-8 JSON 容量限制
│   ├── media.py                   相容的下載入口
│   ├── media_contracts.py         共用來源識別、路徑與錯誤
│   ├── media_coordinator.py       引擎調度、通用解析與去重
│   ├── media_engines.py           選配引擎與共用設定
│   ├── video_adapter.py          yt-dlp 畫質與原始串流下載
│   ├── gallery_adapter.py        gallery-dl 設定與媒體下載
│   ├── image_adapter.py          圖片原始位元組與保存紀錄
│   ├── x_account_media.py        X 帳號掃描／同步及公開貼文
│   ├── profiles.py  作者網址、平台模式與標準化
│   ├── pixiv_auth.py  Pixiv PKCE 授權及加密登入保存
│   ├── pixiv_auth_exchange.py  隔離、固定端點的 Token 交換
│   ├── pixiv_profiles.py  作者原圖掃描與核對後增量補抓
│   ├── pixiv_paths.py  共用作者名／ID 資料夾及跨平台安全命名
│   ├── browser_media.py           選配臨時 Chrome 捕捉
│   └── *.py                       API、排程、保存及下載模組
├── static/                        網頁介面、樣式及語系 key
│   ├── app.js                     組裝、狀態發布與刷新排程
│   ├── settings_controller.js     設定草稿、分頁及 Rate 確認
│   ├── diagnostics_controller.js  環境診斷、健康與快取維護
│   ├── database_controller.js     SQLite 狀態、整理確認與輪詢
│   ├── jobs_controller.js         清單操作、篩選、分頁及檔案選擇
│   └── controller_lifecycle.js    事件、計時器與清理
├── chrome-extension/              Chrome X 登入連接器
├── tools/                         安裝、診斷、量測及原始碼打包
│   ├── package_source.py           允許清單原始碼 ZIP
│   ├── check_source_archive.py     解壓來源包後執行完整回歸
│   ├── check_workflows.py          已審查 Action 來源／完整 SHA 檢查
│   ├── check_installation.py       Windows 新來源／venv 安裝驗收
│   ├── check_desktop.py            Windows 原生背景啟停驗收
│   ├── check_dependency_faults.py  版本、警告與傳輸故障回歸門檻
│   ├── check_docker.py             隔離 Docker 映像及建置內容驗收
│   ├── docker_runtime_probe.py     經標準輸入執行的合成 FFmpeg／Node 檢查
│   ├── docker_service_acceptance.py  隔離 Compose 儲存、連線及回復驗收
│   ├── docker_storage_probe.py     receipt 限定的合成歷史／媒體及故障注入
│   ├── docker_interaction_acceptance.py  容器登入及媒體 HTTP 驗收
│   ├── docker_interaction_probe.py  合成登入／金鑰／媒體資料操作
│   ├── docker_host_acceptance.py   真正主機掛載／ACL／檔案型 secret 驗收
│   ├── docker_host_probe.py        receipt 限定的主機權限與備份檢查
│   ├── docker_browser_acceptance.py 主機 Chrome 檔案操作、PNG 解碼與 H.264 播放
│   ├── docker_pixiv_acceptance.py Linux 隔離 Pixiv 目錄／恢復與授權驗收
│   ├── measure_persistence.py      隔離合成保存與 API 延遲量測
│   ├── measure_capacity.py         帳號掃描、IPC 及 64 MiB 邊界驗收
│   └── measure_hashing.py          合成檔案內容雜湊成本評估
├── docs/                          操作、架構與維護文件
│   └── images/dashboard-preview.svg  可公開的虛構介面示意
├── tests/                         可匯入的本機回歸測試套件
│   ├── helpers/app.py             共用隔離 AppContext fixture
│   ├── helpers/install_runner.py  需 receipt 的安裝驗收子程序
│   ├── helpers/console_runner.py  隔離 Windows Ctrl+C／下載程序 fixture
│   └── test_*.py / frontend.test.cjs  Python／Node 測試
├── .github/
│   ├── dependabot.yml             依賴更新 PR 提案
│   ├── ISSUE_TEMPLATE/            錯誤、安裝、功能及私人聯絡表單
│   ├── pull_request_template.md   修改及驗證摘要
│   └── workflows/                 Windows CI 設定
└── data/ downloads/ .venv/ dist/   本機／生成內容，排除於原始碼包
```

`ssdl` 是 **Smart Social Downloader** 的縮寫，作為 Python 套件名稱。執行資料仍相對於專案根目錄保存，媒體下載位置可在設定中修改。匯入入口模組不會恢復登入／歷史或啟動 worker；每個明確建立的 AppContext 各自擁有佇列與服務。完整模組用途與生命週期見 [架構文件](docs/ARCHITECTURE.md)。

## 更新、回報與發布

**應用程式版本**顯示在頂部名稱下方及設定 → 診斷；引擎版本另列於環境診斷。`update.bat` 更新引擎，不更新應用程式原始碼。詳見 [維護指南](docs/MAINTENANCE.md) 與 [CHANGELOG](CHANGELOG.md)。

CI Actions 已固定完整 commit SHA。Dependabot 每週提出 Actions／Python 依賴更新 PR，由維護者審查並要求回歸與來源包驗收，流程見 [依賴維護](docs/MAINTENANCE.md#dependency-updates-and-action-pins)。

[首輪依賴審查](docs/DEPENDENCY_ACCEPTANCE.md)採納 pycryptodomex 3.24.1，瀏覽器依賴保留相容版本。更新原始碼若涉及依賴 pin 變更，請先停止服務、執行 `setup.bat` 套用已審查基線，再重新啟動。更新原始碼或單純重啟不會安裝新套件；`update.bat` 則明確在相容範圍內更新。

維護者可在引擎／瀏覽器更新後執行 `python tools/check_dependency_faults.py --report data/dependency-faults.json`。CI 與來源包也會執行[依賴故障追蹤](docs/DEPENDENCY_FAULTS.md)，記錄版本與安全分類；新警告、socket 資源未關閉或傳輸驗收失敗會阻擋通過。

Windows CI 另以全新來源與 venv 驗證安裝、離線啟動／重啟、原生背景啟停及更新／恢復。維護者可執行 `python tools/check_installation.py --browser`，它會下載依賴到隔離暫存位置。批次程序清理、正常關閉與真實桌面／X 驗收的分工見 [安裝驗收](docs/INSTALLATION_ACCEPTANCE.md)。

保存採用獨立背景 writer 與不可變快照；關鍵變更等待落盤時不持有佇列鎖，失敗仍有提示並可在診斷中重新保存。維護者可用 `python tools/measure_persistence.py` 重現快照／保存／API 延遲量測，結果及限制見 [保存效能文件](docs/PERSISTENCE_PERFORMANCE.md)。指令使用暫存資料，不下載媒體或恢復登入。

設定 → 診斷會顯示已保存紀錄容量，達到 **64 MiB** 上限的 80% 時提醒。超限保存保留最後有效紀錄；子程序訊息超限有明確錯誤，後續佇列仍可繼續，已下載原檔保留。限制針對 JSON 資料，不是影片／圖片檔案大小。處理方式、合成帳號／IPC 量測及 `python tools/measure_capacity.py --full-limits` 見 [容量與限制](docs/CAPACITY.md)。

同一個診斷分頁也能檢查 SQLite 容量、建立一致性備份及手動整理。備份／整理前需暫停佇列並等待目前下載結束；整理會先建立有效備份，保留去重紀錄與媒體原檔。備份保存在 `data/database-backups/` 並占用額外空間。操作與恢復方式見 [資料庫維護](docs/DATABASE_MAINTENANCE.md)；索引檔案保存仍是 [ROADMAP](ROADMAP.md) 中的後續選配。

GitHub repo 發布後，可使用 Issue 表單回報錯誤、安裝問題或功能建議。分享前先檢視診斷與截圖，避免個人資料外洩；流程見 [CONTRIBUTING](CONTRIBUTING.md)。漏洞請依 [SECURITY](SECURITY.md) 使用私人回報方式。

原始碼 ZIP 包含程式、文件、公開展示圖及授權，排除下載檔案、歷史、Cookie 與 Python 環境。檔名包含應用程式版本；它不是可執行安裝程式。原始碼 repo 為 [Zimkjdv/Smart-Social-Downloader](https://github.com/Zimkjdv/Smart-Social-Downloader)。啟用 GitHub 私人漏洞回報及發布有 tag 的預覽 Release 仍待進行。

## 未來規劃

維護者可執行 `python tools/check_source_archive.py`，在隔離目錄建立、核對並解壓來源 ZIP，再用目前環境的依賴執行完整回歸。打包邊界與 fixture 用法見 [來源包與測試驗收](docs/SOURCE_TESTING.md)。

待修問題、架構改善與發布驗收統一列於 [Roadmap](ROADMAP.md)，已完成里程碑見 [CHANGELOG](CHANGELOG.md)。

**Docker 部署設定**已提供 Python 3.12／Compose、三個持久化 volume、本機健康檢查、[備份回復](docs/DOCKER_STORAGE.md)及[主機 Chrome 登入／瀏覽器檔案操作](docs/DOCKER_LOGIN.md)。Linux 預設僅保留記憶體登入，可選配獨立金鑰加密保存。實驗性 Linux amd64 已通過實際建置、[9 項 runtime 檢查](docs/DOCKER_ACCEPTANCE.md)、[14 項服務／儲存驗收](docs/DOCKER_SERVICE_ACCEPTANCE.md)、[15 項合成登入／媒體 HTTP 驗收](docs/DOCKER_INTERACTION_ACCEPTANCE.md)及 [8 項真實主機儲存驗收](docs/DOCKER_HOST_ACCEPTANCE.md)。選配的 [7 項主機 Chrome 驗收](docs/DOCKER_BROWSER_ACCEPTANCE.md)補上實際 UI、PNG 解碼與 H.264 播放／跳轉，Linux CI 改用完整 `--browser` 工具。跨實體主機（目前先跳過）、真實版本遷移與真人 Chrome／登入操作仍列於[未來清單](ROADMAP.md#docker-化部署)，尚未發布預建映像。

## 授權

專案自有程式碼與文件使用 [MIT](LICENSE)，第三方套件保留各自授權，見 [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)。
