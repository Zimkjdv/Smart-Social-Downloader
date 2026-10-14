# Roadmap

更新：2026-10-14。此檔是**未完成工作與最新審查發現的唯一總清單**；完成紀錄移至 [CHANGELOG](CHANGELOG.md)。目前基準為 Windows／Python 3.12，沒有 Python 3.10 驗收工作。下列核取方塊均尚未完成，不代表已修正或已發布。N01～N06 及 N07 的保存量測／writer 已完成並移到 [CHANGELOG](CHANGELOG.md#unreleased)，回歸結果見 [TESTING](docs/TESTING.md)。

## 本輪整體審查

重新檢查 API／本機來源政策、Chrome 登入、下載與串流、排程／子程序、保存／去重、前端／設定、檔案架構、安裝與發布。既有 P0／P1／P2 的主要功能已實作，但仍有下列邊界缺陷及驗收工作；功能完成不等於沒有 bug。前輪六個已修正問題保留於 [歷史審查](docs/PROJECT_AUDIT.md)，不與本輪待修項目混用。

審查與回歸使用暫存目錄、隔離 HTTP 服務及合成資料重現。本機套用狀態另記於 CHANGELOG；測試沒有讀取真實 Cookie 或下載外部平台媒體。這是程式審查與有限的故障重現，不是完整滲透測試或所有依賴的漏洞掃描。

| 編號 | 優先度 | 狀態 | 問題／改善 |
| --- | --- | --- | --- |
| N07 | P2 | 保存 writer 完成；容量待辦 | 大帳號掃描／IPC／保存容量、SQLite 長期維護 |
| N08 | P2 | 維護改善建議 | 測試 fixture、來源打包規則與檔案結構配套 |

N01～N06 及 N07 的保存量測／writer 已移至 [CHANGELOG](CHANGELOG.md#unreleased)。[N07 量測與 writer](docs/PERSISTENCE_PERFORMANCE.md) 使用隔離合成歷史驗證等待成本與改造，不宣稱真實使用者資料已出現卡頓。下一項是大帳號掃描／IPC／64 MiB 保存容量及明確提示；SQLite 維護與 N08 的 fixture／來源包驗收仍待辦。HTTP 讀取期限、併發限制與輸入契約見 [可靠性文件](docs/RELIABILITY.md)。

## 架構與檔案結構

目前根目錄入口＋`ssdl/`／`static/`／`chrome-extension/`／`tools/`／`docs/`／`tests/` 的分層保留。AppContext 已實作，runtime 位置保持相容；以下列出剩餘調整，目前完整樹見 [ARCHITECTURE](docs/ARCHITECTURE.md)。

每次只改一個責任邊界，維持入口、API、資料路徑及 Chrome extension ID 相容；共用鎖與關閉順序已列於架構文件。

### N07：保存成本與長期資料維護

- [ ] 量測大帳號掃描、IPC 與 64 MiB 保存容量，對容量限制提供明確提示；檔案明細可改由索引分頁取得。
- [ ] 提供 SQLite 資料庫容量診斷、備份及使用者控制的整理；不得順便刪除媒體，也不得清掉有效去重紀錄。保留「原位置檔案已不存在就重新取得」規則。

### N08：測試與打包跟隨架構調整

- [ ] 從 `tests/test_queue_auth.py` 抽出共用隔離 app fixture；目前 `test_p2.py` 仍直接借用另一個測試類的 setUp。fixture 已改為獨立 AppContext，不再 patch app 模組全域，但測試類間耦合仍需整理。
- [ ] 需要時再分成 unit／integration／browser；同步修改 unittest discovery 與打包允許清單。`tools/package_source.py` 目前的 `ssdl/*.py`、`tests/test_*.py` 只涵蓋最上層，新增子套件或 helpers 若不更新將漏入來源 ZIP。
- [ ] 加入「發行來源包解壓後可匯入並執行測試」的驗收，禁止以無差別遞迴整個 workspace 取代允許清單。
- [ ] 加強 Windows 在拒絕含 body 的未授權 POST 時的回應／fixture 覆蓋。本輪一次隔離請求出現 10053，後續單獨及完整回歸均通過，尚未穩定重現；先保留紀錄，不視為已修正或確定的安全缺陷。
- [ ] 文件分工固定為 README（入口）、CHANGELOG（完成歷史）、Roadmap（未完成）、docs（操作與設計／測試證據）；完成項目移到 CHANGELOG，其他文件連回本清單，避免多份進度互相矛盾。

## 安裝、真實使用與 GitHub 發布驗收

- [ ] **乾淨 Windows／Python 3.12**：首次安裝、啟動、關閉、更新／基準恢復及 X 登入。先前已通過本機獨立來源副本與新 venv；那不是全新 Windows 系統。沒有要求補測 Python 3.10。
- [ ] **一般 Chrome 真實配對**：重新載入 connector 1.1.0、自訂 port、取消／過期／失敗後重配及重啟恢復。先前預設 port 曾成功配對，不代表新版自訂 port 已驗收。正常 Windows 使用者環境的 DPAPI 是前提，不能以受限工具環境的失敗宣稱 DPAPI 普遍失效。
- [ ] **線上平台抽樣**：實際 Best／指定畫質、登入失效、限流與恢復、帳號媒體掃描、缺檔補抓；先取得適合的測試素材。104＋10 合成測試不代表所有平台即時相容。
- [ ] **GitHub 設定與發布**：啟用並確認私人漏洞回報入口，核對 tag、版本、來源 ZIP、release notes 後發布 preview。repo 已公開、Windows／Python 3.12 CI 已通過，目前沒有 tag／Release。
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
