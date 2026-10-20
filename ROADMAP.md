# Roadmap

更新：2026-10-21。此檔是**未完成工作與最新審查發現的唯一總清單**；完成紀錄移至 [CHANGELOG](CHANGELOG.md)。目前基準為 Windows／Python 3.12，沒有 Python 3.10 驗收工作。下列核取方塊均尚未完成，不代表已修正或已發布。N01～N08 已完成並移到 [CHANGELOG](CHANGELOG.md#unreleased)，回歸結果見 [TESTING](docs/TESTING.md)。N07 的索引評估已記錄，實際索引／游標儲存列為後續選配，尚未實作。

## 本輪整體審查

重新檢查 API／本機來源政策、Chrome 登入、下載與串流、排程／子程序、保存／去重、前端／設定、檔案架構、安裝與發布。既有 P0／P1／P2 的主要功能與本輪 N01～N08 已實作，仍有下列環境驗收與選配工作；功能完成不等於沒有 bug。前輪六個已修正問題保留於 [歷史審查](docs/PROJECT_AUDIT.md)，不與本輪待辦項目混用。

審查與回歸使用暫存目錄、隔離 HTTP 服務及合成資料重現。本機套用狀態另記於 CHANGELOG；測試沒有讀取真實 Cookie 或下載外部平台媒體。這是程式審查與有限的故障重現，不是完整滲透測試或所有依賴的漏洞掃描。

N01～N08 已移至 [CHANGELOG](CHANGELOG.md#unreleased)。本輪列出的修正與維護改善已完成，仍需以下環境／發布驗收及選配功能；不代表沒有其他潛在缺陷。[N08 共用 fixture 與來源包驗收](docs/SOURCE_TESTING.md) 已實作，HTTP 讀取期限、併發限制與輸入契約見 [可靠性文件](docs/RELIABILITY.md)。

## 架構與檔案結構

目前根目錄入口＋`ssdl/`／`static/`／`chrome-extension/`／`tools/`／`docs/`／`tests/` 的分層保留。AppContext 與共用測試 fixture 已實作，runtime 位置保持相容；完整樹見 [ARCHITECTURE](docs/ARCHITECTURE.md)。

每次只改一個責任邊界，維持入口、API、資料路徑及 Chrome extension ID 相容；共用鎖與關閉順序已列於架構文件。

## 安裝、真實使用與 GitHub 發布驗收

- [ ] **一般桌面 Windows／互動驗收**：全新一般 Windows 的 Python／Node／Chrome 安裝、實際鍵盤／終端批次提示及授權 X 登入仍待驗收。新來源／新 venv 安裝、離線重啟、自動修復、更新／基準恢復，以及獨立控制台真正 Ctrl+C 的閒置／下載中關閉、程序清理及待辦恢復已自動化並移至 [CHANGELOG](CHANGELOG.md#unreleased)，見 [安裝驗收](docs/INSTALLATION_ACCEPTANCE.md) 與 [控制台驗收](docs/CONSOLE_ACCEPTANCE.md)。這些隔離副本／程式產生的事件不等於出廠桌面或人手按鍵；沒有 Python 3.10 工作。
- [ ] **一般 Chrome 真實配對**：重新載入 connector 1.1.0、自訂 port、取消／過期／失敗後重配及重啟恢復。先前預設 port 曾成功配對，不代表新版自訂 port 已驗收。正常 Windows 使用者環境的 DPAPI 是前提，不能以受限工具環境的失敗宣稱 DPAPI 普遍失效。
- [ ] **線上平台抽樣**：實際 Best／指定畫質、登入失效、限流與恢復、帳號媒體掃描、缺檔補抓；先取得適合的測試素材。104＋10 合成測試不代表所有平台即時相容。
- [ ] **GitHub 設定與發布**：啟用並確認私人漏洞回報入口，核對 tag、版本、來源 ZIP、release notes 後發布 preview。repo 已公開、Windows／Python 3.12 CI 已通過，目前沒有 tag／Release。
- [ ] **後續依賴更新提案驗收**：首輪 Python 提案審查與 pycryptodomex 3.24.1 修補驗收已完成，移至 [CHANGELOG](CHANGELOG.md#unreleased)；[審查紀錄](docs/DEPENDENCY_ACCEPTANCE.md)記錄 PR #1／#2 的版本、相容性及恢復驗證。目前尚未收到 Actions 更新提案；收到後仍須核對官方版本／完整 SHA 與兩個 Windows CI 工作。pyee 14 與目前 Playwright 1.63.0 的 `pyee>=13,<14` 要求不相容，延後至相容的 Playwright／瀏覽器更新一起驗收；不能因 Python 3.12 支援就單獨強裝。後續提案不自動合併，也未宣稱完成 CVE 掃描。

依賴故障追蹤工具、CI／來源包檢查及本輪 HTTP 錯誤回應資源修正已完成，移至 [CHANGELOG](CHANGELOG.md#unreleased)。後續每次引擎／Chrome／Playwright 升級仍須重跑；已知 SSL 棄用、10053 的驗證範圍與故障處置維護在[追蹤文件](docs/DEPENDENCY_FAULTS.md)，不代表所有上游問題已消失。未來二進位散布仍須逐版核對第三方授權。

## 後續功能

### 大型媒體清單索引（選配）

- [ ] 實作獨立的工作檔案索引及游標分頁，配套增量 IPC、snapshot generation 發布、恢復／回退、舊資料遷移及精確檔案操作。N07 的[評估與取捨](docs/DATABASE_MAINTENANCE.md#indexed-file-detail-assessment)已完成；此實作是後續功能，屬於未來選配。
- [ ] 工作清單生命週期與有效去重紀錄分開；原位置檔案不存在就重新取得。現有 HTTP 分頁仍從記憶體清單取得，64 MiB 限制維持，不以直接提高上限取代索引設計。

### Docker 化部署

第 1～4 項的來源實作、第 5 項的隔離 runtime 驗收及第 2／3 項的本機 Compose 驗收已完成並移至 [CHANGELOG](CHANGELOG.md#unreleased)。2026-10-21 已實際通過 9 項 FFmpeg／Node／來源排除及 14 項服務／儲存驗收，含 UID 權限、資料保留、故障健康狀態、備份校驗、真正還原中斷、跨專案搬遷及保留映像回復。範圍見 [Docker 文件](docs/DOCKER.md)、[服務驗收](docs/DOCKER_SERVICE_ACCEPTANCE.md)及[實測紀錄](docs/TESTING.md)。動態 Chrome 仍為選配，沒有發布預建映像；同機隔離驗收不代表以下跨主機／登入工作完成。

- [ ] **跨實體主機與實際版本升級**：在另一台主機驗收備份搬遷、主機 bind 權限／Docker Desktop 目錄分享；有真實新版本時驗收資料遷移與匹配舊版本回復。本輪已測同一引擎上的獨立 volumes／專案與經主機傳輸的備份，以及僅加標籤的不同映像；不能據此宣稱跨硬體或實際版本遷移已完成。
- [ ] 實際驗收第 4 項：記憶體登入、獨立金鑰的權限／加密保存／重啟／遺失或錯誤金鑰／斷開連接，主機 Chrome 的首次安裝、預設／自訂 port、取消／過期／重配，以及網頁檔案清單、原始位元組／HEAD／Range、搬移或刪檔／路徑拒絕／併發讀取與 Windows 原生操作回歸。第 5 項的 runtime 驗收未涵蓋這些流程，尚無真實配對或播放驗收證據。
- [ ] 完成安裝、重啟恢復、媒體持久化與登入驗收，再將文件中的實驗操作程序升格為正式部署指引。Docker 不算目前已驗收的 P0／P1／P2。

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
