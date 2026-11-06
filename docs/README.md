# 文件總索引 / Documentation

從這裡依用途找文件。操作與契約描述目前行為；歷史區的版本、結果及待辦僅適用於記錄當時，現在的未完成工作集中在 [Roadmap](development/ROADMAP.md)。

Start here to find an operator guide, implementation contract or reproducible check. Dated results are kept separately from current instructions.

| 用途 / Purpose | 入口 / Start here |
| --- | --- |
| 日常下載與設定 | [繁體中文使用指南](guides/USAGE_CN.md) · [English usage guide](guides/USAGE.md) |
| Windows 啟動與桌面視窗 | [Windows source launches](guides/WINDOWS.md) |
| 安裝、登入或連線排錯 | [排錯指南](guides/TROUBLESHOOTING.md) |
| 部署與搬遷 | [Windows 發行／資料匯入](deployment/WINDOWS_DISTRIBUTION.md) · [Docker](deployment/DOCKER.md) |
| 開發與維護 | [架構與完整模組樹](reference/ARCHITECTURE.md) · [API 契約](reference/API_CONTRACT.md) · [維護與發布](development/MAINTENANCE.md) |
| 測試與驗收 | [測試方法與來源包](development/TESTING.md) · [驗收程序索引](testing/README.md) |
| 過去做過哪些驗證 | [有日期的實測紀錄](history/TEST_RESULTS.md) |

## 使用指南 / Guides

- [繁體中文](guides/USAGE_CN.md) / [English](guides/USAGE.md)：下載、設定、佇列與檔案操作。
- [Windows](guides/WINDOWS.md)：瀏覽器背景入口、選配桌面視窗、日誌、啟停與資料位置。
- [排錯](guides/TROUBLESHOOTING.md)：安裝診斷、本機 API 與登入問題。
- [Pixiv](guides/PIXIV.md)：連接帳號與作者作品同步。
- [影片畫質](guides/VIDEO_QUALITY.md)：上限、重試與既有下載。
- [動態媒體捕捉](guides/DYNAMIC_CAPTURE.md)：選配 Chrome 功能與限制。
- [Chrome 連接器](../chrome-extension/README.md)：與擴充功能程式碼一起維護的安裝說明。

## 部署 / Deployment

- [Windows 發行版](deployment/WINDOWS_DISTRIBUTION.md)：EXE／安裝程式、可寫資料、匯入與回復。
- [Docker 部署](deployment/DOCKER.md)：建置輸入、啟動與功能邊界。
- [Docker 登入](deployment/DOCKER_LOGIN.md)：主機 Chrome、工作階段保存及檔案操作。
- [Docker 備份與恢復](deployment/DOCKER_STORAGE.md)：volume、升級、還原及搬遷。

## 技術參考 / Reference

- [架構](reference/ARCHITECTURE.md)：完整目錄、模組責任、初始化與生命週期。
- [HTTP／桌面 API](reference/API_CONTRACT.md) · [後端 Supervisor](reference/DESKTOP_CONTROL.md)。
- [可靠性與安全邊界](reference/RELIABILITY.md)：取消、保存、網路與診斷遮蔽。
- [去重與來源識別](reference/DOWNLOAD_DEDUP.md)：原檔核對、畫質隔離、Pixiv 穩定 ID 及舊紀錄相容。
- [狀態與快取效能](reference/PERFORMANCE.md) · [保存效能](reference/PERSISTENCE_PERFORMANCE.md)。
- [容量限制](reference/CAPACITY.md) · [SQLite 維護與恢復](reference/DATABASE_MAINTENANCE.md)。

## 開發與維護 / Development

- [測試方法](development/TESTING.md)：共用 fixture、回歸指令、文件檢查與來源 ZIP 驗收。
- [維護與發布](development/MAINTENANCE.md)：版本、依賴審查、Action pins、發布及提交隱私檢查。
- [依賴與傳輸故障追蹤](development/DEPENDENCY_FAULTS.md)。
- [Roadmap](development/ROADMAP.md)：未完成工作；[Changelog](../CHANGELOG.md)：已完成變更。
- [代理工作規則](../AGENTS.md)：按條件讀取[需求釐清](development/agents/REQUIREMENTS.md)及[規則維護](development/agents/AGENTS-MAINTENANCE.md)。

## 歷史紀錄 / History

這些文件保留日期、當時版本、失敗觀察及驗收限制；不作為目前安裝或發布指令。

- [歷次測試與驗收結果](history/TEST_RESULTS.md)。
- [專案稽核](history/PROJECT_AUDIT.md) · [P2 實作紀錄](history/P2_COMPLETION.md)。
- [PR 整合紀錄](history/PR_INTEGRATION.md) · [首輪依賴審查](history/DEPENDENCY_ACCEPTANCE.md)。

## 研究 / Research

- [內容雜湊比對評估](research/CONTENT_HASH_ASSESSMENT.md)：設計取捨與合成量測，尚非已啟用功能。

本機產品比較可放在 `research/`；個人研究只有經審核並列入明確來源清單後才會納入散布。
