# Roadmap

更新：2026-10-11。此檔是**未完成工作與最新審查發現的唯一總清單**；完成紀錄移至 [CHANGELOG](CHANGELOG.md)。目前基準為 Windows／Python 3.12，沒有 Python 3.10 驗收工作。下列核取方塊均尚未完成，不代表已修正或已發布。N01～N05 已修正並移到 [CHANGELOG](CHANGELOG.md#unreleased)，回歸結果見 [TESTING](docs/TESTING.md)。

## 本輪整體審查

重新檢查 API／本機來源政策、Chrome 登入、下載與串流、排程／子程序、保存／去重、前端／設定、檔案架構、安裝與發布。既有 P0／P1／P2 的主要功能已實作，但仍有下列邊界缺陷及驗收工作；功能完成不等於沒有 bug。前輪六個已修正問題保留於 [歷史審查](docs/PROJECT_AUDIT.md)，不與本輪待修項目混用。

審查與回歸使用暫存目錄、隔離 HTTP 服務及合成資料重現。本機套用狀態另記於 CHANGELOG；測試沒有讀取真實 Cookie 或下載外部平台媒體。這是程式審查與有限的故障重現，不是完整滲透測試或所有依賴的漏洞掃描。

| 編號 | 優先度 | 狀態 | 問題／改善 |
| --- | --- | --- | --- |
| N06 | P2 | 架構改善建議 | 共用狀態與模組初始化副作用、前後端大型模組 |
| N07 | P2 | 待量測 | 保存鎖與大量檔案進度成本、SQLite 長期容量 |
| N08 | P2 | 維護改善建議 | 測試 fixture、來源打包規則與檔案結構配套 |

N01～N05 已完成；接下來可分批處理 N06～N08 的架構、量測及維護工作。HTTP 讀取期限、併發限制與輸入契約見 [可靠性文件](docs/RELIABILITY.md)。

## 架構與檔案結構

目前根目錄入口＋`ssdl/`／`static/`／`chrome-extension/`／`tools/`／`docs/`／`tests/` 的分層可以保留。以下是漸進調整建議，**尚未搬動程式或 runtime 目錄**；目前完整樹見 [ARCHITECTURE](docs/ARCHITECTURE.md)。

### N06：明確狀態擁有者與模組責任

- [ ] 建立具型別的 AppContext／服務介面。`app.py` 用 `sys.modules[__name__]` 注入 scheduler／repository，兩者大量存取私有全域欄位；搬檔已完成，但耦合仍高。改為明確傳入佇列、保存、下載執行與狀態發布所需能力。
- [ ] 把 XAuthManager／StateStore 等初始化移到明確的啟動生命週期。匯入 app 雖不開 HTTP／worker，但會建立管理器並嘗試恢復登入資料，測試目前須預先 mock `_restore`。驗收一般模組匯入不讀取使用者登入資料；重複建立測試 app 可獨立關閉。
- [ ] 漸進拆分 `ssdl/media.py`（本輪 1229 行）：先分開引擎 adapter、一般媒體協調、X 帳號同步；共用來源 identity／畫質／去重契約，避免各 adapter 再複製政策。
- [ ] 拆分 `static/app.js`（966 行）的設定、診斷、清單控制器，保留既有 API client／row reconciliation／i18n／focus 模組。`locales.js` 的 2507 行主要是雙語資料，不單憑行數視為效能缺陷。
- [ ] 清除拆檔後多餘 import，明列鎖擁有者、背景執行緒與 shutdown 順序。每次只改一個責任邊界，維持入口、API、資料路徑及 Chrome extension ID 相容。

### N07：保存成本與長期資料維護

- [ ] 量測 `StateRepository.save_locked` 在共用 condition 內序列化、驗證備份、fsync 的耗時；比較大型資料下 pause／cancel／summary 的延遲。尚未量測出 UI 卡頓，不把它列成已重現 bug。
- [ ] 依結果設計不可變 snapshot、單一保存 writer 與合併更新；保留關鍵狀態的落盤保證、錯誤提示、關機 flush 和恢復順序，避免僅延遲保存而增加資料遺失。
- [ ] 量測大帳號掃描、IPC 與 64 MiB 保存容量，對容量限制提供明確提示；檔案明細可改由索引分頁取得。
- [ ] 提供 SQLite 資料庫容量診斷、備份及使用者控制的整理；不得順便刪除媒體，也不得清掉有效去重紀錄。保留「原位置檔案已不存在就重新取得」規則。

### N08：測試與打包跟隨架構調整

- [ ] 從 `tests/test_queue_auth.py` 抽出共用隔離 app fixture；目前 `test_p2.py` 直接借用另一個測試類的 setUp，並大量 patch 模組全域狀態，跨測試耦合較高。
- [ ] 需要時再分成 unit／integration／browser；同步修改 unittest discovery 與打包允許清單。`tools/package_source.py` 目前的 `ssdl/*.py`、`tests/test_*.py` 只涵蓋最上層，新增子套件或 helpers 若不更新將漏入來源 ZIP。
- [ ] 加入「發行來源包解壓後可匯入並執行測試」的驗收，禁止以無差別遞迴整個 workspace 取代允許清單。
- [ ] 文件分工固定為 README（入口）、CHANGELOG（完成歷史）、Roadmap（未完成）、docs（操作與設計／測試證據）；完成項目移到 CHANGELOG，其他文件連回本清單，避免多份進度互相矛盾。

## 安裝、真實使用與 GitHub 發布驗收

- [ ] **乾淨 Windows／Python 3.12**：首次安裝、啟動、關閉、更新／基準恢復及 X 登入。先前已通過本機獨立來源副本與新 venv；那不是全新 Windows 系統。沒有要求補測 Python 3.10。
- [ ] **一般 Chrome 真實配對**：重新載入 connector 1.1.0、自訂 port、取消／過期／失敗後重配及重啟恢復。先前預設 port 曾成功配對，不代表新版自訂 port 已驗收。正常 Windows 使用者環境的 DPAPI 是前提，不能以受限工具環境的失敗宣稱 DPAPI 普遍失效。
- [ ] **線上平台抽樣**：實際 Best／指定畫質、登入失效、限流與恢復、帳號媒體掃描、缺檔補抓；先取得適合的測試素材。104＋10 合成測試不代表所有平台即時相容。
- [ ] **GitHub 設定與發布**：啟用並確認私人漏洞回報入口，執行 Windows／Python 3.12 CI，核對 tag、版本、來源 ZIP、release notes 後發布 preview。目前沒有 repo／tag／Release。
- [ ] **依賴維護**：評估固定 GitHub action commit SHA、建立明確更新與回歸流程，追蹤 SSL 棄用／socket ResourceWarning；未宣稱目前有已知第三方 CVE。引擎／Chrome／Playwright 升級後重跑相關驗收，二進位散布另行核對第三方授權。

## 後續功能

### Docker 化部署

- [ ] Python 3.12 Dockerfile／Compose 與可重現部署文件；目前沒有可使用的 Docker 映像。
- [ ] 設定／歷史／快取與下載媒體分開持久化，制定權限、備份、升級及回復流程。
- [ ] 容器監聽與 port 對應、Host／Origin、健康檢查，預設僅本機可存取；沿用下載來源的公開位址檢查。
- [ ] 處理 Linux 容器沒有 Windows DPAPI 的登入保存方式、本機 Chrome 配對及主機檔案／資料夾操作。
- [ ] FFmpeg／JavaScript runtime；動態 Chrome 捕捉維持選配，build context／映像排除私人資料。
- [ ] 完成安裝、重啟恢復、媒體持久化與登入驗收，再提供部署指令。Docker 不算目前已完成的 P0／P1／P2。

### 去重與匯入選配

- [ ] 擴充可靠的平台穩定 ID，保留畫質／媒體差異；簽章更新是否能合併須逐平台確認。
- [ ] 評估跨 URL／平台的內容雜湊比較；目前網址指紋不是內容雜湊。
- [ ] 為已清除清單、沒有可信成功紀錄的舊檔提供可確認完整性的匯入流程，不因同名就直接認定完成。背景見 [DOWNLOAD_DEDUP](docs/DOWNLOAD_DEDUP.md)。

## 名稱與發布資料建議

建議保留 **Smart Social Downloader**，repo 為 **`smart-social-downloader`**。目前沒有改名。備選 Local Media Queue（`local-media-queue`）較偏通用網頁媒體；MediaQueue（`mediaqueue`）較短但用途不夠直觀。這些名稱尚未查核衝突、帳號可用性或商標。

推薦 GitHub description：

> Local-first video and image downloader with a web UI, queued downloads, X account media sync, and HLS/DASH support. Powered by yt-dlp and gallery-dl.

中文：在本機執行的多平台影片與圖片下載工具，提供網頁介面、下載佇列、X 帳號媒體同步與 HLS／DASH 支援。

建議 topics：`python`、`yt-dlp`、`gallery-dl`、`video-downloader`、`image-downloader`、`download-manager`、`hls`、`local-first`。

若日後改名，須同步 README、頁面標題、語系、Chrome 顯示名稱與發布檔；不要順便更動 extension 公開金鑰／ID、runtime 路徑或配對協定。
