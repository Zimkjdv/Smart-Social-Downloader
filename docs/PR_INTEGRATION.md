# PR 整合計畫與執行紀錄

更新：2026-10-27（Asia/Taipei）。本文件記錄這次九個 open PR 的處理順序、證據與結果；功能待辦仍以 [ROADMAP](../ROADMAP.md) 為準。使用者已授權依序合併；不建立 tag 或公開 Release。

## Summary

```text
main
  → #4 Chrome 配對驗收與 main 保護
  → #6 D01 共用 API／平台契約
  → #7 D02 後端監督與視窗擁有權
  → #8 D03 pywebview／WebView2
  → #9 D04 桌面驗收
  → #10 D05 Windows 安裝包
  → #5 Actions 更新（審查與驗收後）
  → #3 Python／瀏覽器依賴更新（審查與驗收後）

#2 pyee 14：依相容性結果延後
```

功能 PR 保留 merge commit 與原始提交關係，不逐個 squash/rebase。合併前先讓分支包含最新 main，核對新增差異，再等待該 head 的 CI。完成整合後才清理沒有未合併工作、也不再作為其他 PR base 的功能分支。

## Evidence：合併條件

- **Before：** 九個 PR 尚未合併；#6～#10 的 base 是前一階段功能分支。main 起點為 `d22c9a8fbca149527a6624fdfa1c86d905400aec`。
- **After：** 下表只在 GitHub 確認 merged 後填入合併 SHA／CI 連結；等待或失敗不當成完成。
- main 的 `Protect main` ruleset 保持啟用：禁止刪除／force push、透過 PR 合併、解決 review threads，且分支必須更新到最新 main。
- 必要 CI：`windows`、`install-windows`、`docker-runtime`。D05 與會影響發行包的更新另核對 `Windows distribution`。
- 合併呼叫帶入已核對的 head SHA；若 head／main 移動，重新檢查，不繞過保護或把失敗標成成功。
- 每步以 Git diff 檢查相對最新 main 的實際內容；純合併同步不得帶入額外程式更動。合併後核對 main 已包含該 head。
- 依賴更新按 [維護流程](MAINTENANCE.md) 另測：官方版本／SHA、完整 pins、pip check、來源 ZIP 回歸與實際引擎／瀏覽器影響；不能僅因 Dependabot 顯示可合併就通過。

## 執行表

| 順序 | PR | 起始 head | 處理狀態 | 合併／驗收證據 |
| --- | --- | --- | --- | --- |
| 1 | [#4](https://github.com/Zimkjdv/Smart-Social-Downloader/pull/4) Chrome 配對 | `a18565d` | 已合併 | merge [`c08cc05`](https://github.com/Zimkjdv/Smart-Social-Downloader/commit/c08cc05ebdb76c390bb1e5bd6a4cf8d8917d9b03)；[CI](https://github.com/Zimkjdv/Smart-Social-Downloader/actions/runs/40146910943) |
| 2 | [#6](https://github.com/Zimkjdv/Smart-Social-Downloader/pull/6) D01 | `a437206` | 已合併 | merge [`9928376`](https://github.com/Zimkjdv/Smart-Social-Downloader/commit/9928376165d70fe5495a589895b32debc2617aa4)；[CI](https://github.com/Zimkjdv/Smart-Social-Downloader/actions/runs/40369204513) |
| 3 | [#7](https://github.com/Zimkjdv/Smart-Social-Downloader/pull/7) D02 | `e71a13b` | 已合併 | merge [`fe682a3`](https://github.com/Zimkjdv/Smart-Social-Downloader/commit/fe682a3ee2afcd2d6fb260e3ff0d1679921183e9)；[CI](https://github.com/Zimkjdv/Smart-Social-Downloader/actions/runs/40370767494) |
| 4 | [#8](https://github.com/Zimkjdv/Smart-Social-Downloader/pull/8) D03 | `8266257` | 已合併 | merge [`b947523`](https://github.com/Zimkjdv/Smart-Social-Downloader/commit/b9475238a2ad1528d8c7818f20778249b2580ad6)；[CI](https://github.com/Zimkjdv/Smart-Social-Downloader/actions/runs/40372279727) |
| 5 | [#9](https://github.com/Zimkjdv/Smart-Social-Downloader/pull/9) D04 | `98adfbd` | 已合併 | merge [`ed45cf7`](https://github.com/Zimkjdv/Smart-Social-Downloader/commit/ed45cf73e446e54c1f4f9227967590a970209048)；[CI](https://github.com/Zimkjdv/Smart-Social-Downloader/actions/runs/40373685475) |
| 6 | [#10](https://github.com/Zimkjdv/Smart-Social-Downloader/pull/10) D05 | `0ff62a8` | 待同步最新 main 及重新驗收 | 本 PR 承接目前進度；合併後另補結果 |
| 7 | [#5](https://github.com/Zimkjdv/Smart-Social-Downloader/pull/5) setup-python 7.1 | `dbd4d2a` | 功能整合後審查；須同步所有工作流程 | — |
| 8 | [#3](https://github.com/Zimkjdv/Smart-Social-Downloader/pull/3) gallery-dl／Playwright | `42bc648` | Draft：隔離候選來源回歸通過；原生 GUI 待釐清 | 詳見下方候選審查 |
| 延後 | [#2](https://github.com/Zimkjdv/Smart-Social-Downloader/pull/2) pyee 14 | `7d1c727` | Draft：main 仍為 Playwright 1.63.0，#3 尚未整合 | 1.64.0 已允許 pyee 14；#3 通過後再另驗 #2 |

## 每步操作與紀錄

1. 重新取得 PR、head、base、review／mergeability 與該 head 的最新 CI。
2. 前一階段合併後，將下一個 PR 的 base 改成 main；在隔離 checkout 正常 merge 最新 main 並 push，保留既有歷史，不 force push。
3. 檢查相對 main 的差異與是否有意外內容；解決衝突後執行適當的本機檢查。
4. 等待必要 CI 全綠；D05／依賴變更同時等待發行包建置及 frozen／installer 驗收。
5. 以核對的 head SHA 執行 merge commit，記錄 merge SHA／CI 連結，核對 main ancestry，才進入下一個功能 PR。
6. CI 失敗時保留失敗紀錄，查明原因、修正並重跑；不降低驗收條件。不可合併的依賴提案記錄原因後延後。
7. 最後重查 open PR、main CI 與功能分支相依；有未合併工作或仍在本機使用的分支不直接刪除。

合併過程的即時分類紀錄保存在忽略的本機驗收資料；本文件會在後續可審查的提交中彙整實際結果。若最後彙整需要獨立文件 PR，照相同 main 保護通過 CI 後再合併。

## Merge Danger

**Door：** two-way。程式整合可用後續 revert PR 回復，仍須通過保護檢查；已公開的提交不改寫歷史。安裝版的使用者資料遷移仍是使用者明確操作，這次 GitHub 合併不啟動遷移。

**Blast Radius：** repository。

main 會納入 Chrome 配對與 D01～D05。合併不停止正式背景服務、不修改現有 Python 環境、不操作真實登入，也不自動安裝／更新正式版本。D05 乾淨 Windows 10／11、缺少 Runtime 與安裝版真人登入驗收仍保留在 ROADMAP；D06 不併入。依賴更新的合成測試不能代替所有線上平台抽樣。

## 依賴候選審查（尚未合併）

- #5 的 setup-python `v7.1.0` tag 已向官方核對為 `6d4fd22b20465ccc0f7354476588e8df7c9ca0e0`；執行環境仍為 Node 24，不新增 mirror／token 設定或權限。D05 新增的兩處呼叫也須同步更新，不能只處理原提案的三處。
- #3 的隔離新 venv 使用 gallery-dl 1.32.17、Playwright 1.64.0、pyee 13.0.1、pycryptodomex 3.24.1。已通過 469 Python／59 前端／116 故障案例的來源 ZIP 驗收。
- gallery-dl 對應 PyPI sdist SHA-256：舊版 `bacd7d63423ad45db98704fedafa1302343db6f250f9e9f69a9e142754ed9e37`；新版 `7e49b3140d23b88e020ff24049dfac59edd855d6fdfb11bc725ad44b0335bbb6`。兩份 LICENSE 的 SHA-256 均為 `8177f97513213526df2cf6184d8ff986c675afb514d4e68a404010521b880643`，保留 GPL-2.0-only。
- 新版先被警告審查門檻擋下：116 案例本身通過，但 `ssl_options_deprecated` 尚未接受新版本。核對上游相同 TLS 選項區塊及實際同來源／文字警告後，只在隔離候選接受 gallery-dl 1.32.17＋urllib3 2.8.0＋Python 3.12；新增未知 urllib3 版本仍失敗的回歸。此候選修改尚未進入 main，沒有改動應用程式 TLS 設定。
- 原生 GUI 初次候選執行失敗於 `webview_focus_return_failed`；相同程式／依賴的未修改重跑通過完整矩陣。焦點最小化探針完成 60 次操作，但不是完整驗收（省略後續外部分派，因此正常完整 harness 最後仍拒絕該探針）。不得把探針當成完整矩陣通過。
- 舊 gallery-dl／Playwright 的對照中，兩個 GUI session 通過，但同時啟動階段另失敗於 `gui_concurrent_dashboard_failed`。無法據此建立依賴升級與焦點失敗的因果，也沒有宣稱任何原生失敗已修復。完整與失敗報告均保留在忽略的本機 data；不降低斷言、加盲目重試或提高逾時來通過。
- 後續需建立穩定的原生焦點／同時啟動重現，釐清環境、fixture 或應用程式原因，再用原有斷言重新驗收 #3。其餘功能與 Actions 可獨立整合。
- #2 目前仍受 main 的 Playwright 1.63.0（pyee >=13,<14）限制；候選 1.64.0（pyee >=13,<15）已允許 14，但要先完成 #3，再另外驗收這個 major 更新，不綁在一起直接合併。

候選的八組 frozen／GUI smoke／安裝生命週期也已通過；fixture 清理因 profile 鎖而保留，與驗收結果分列。這不能取代仍有失敗紀錄的完整原生矩陣。實際 resolver 已確認 1.63.0＋pyee 14 會產生 ResolutionImpossible，1.64.0＋14 可解出，dry-run 前後安裝清單不變。兩個提案均已標 Draft，body 附明確恢復審查條件。

官方依據：[setup-python 7.1.0](https://github.com/actions/setup-python/releases/tag/v7.1.0)、[Action manifest](https://github.com/actions/setup-python/blob/6d4fd22b20465ccc0f7354476588e8df7c9ca0e0/action.yml)、[Playwright 1.64.0 metadata](https://pypi.org/pypi/playwright/1.64.0/json)、[gallery-dl 1.32.17 metadata](https://pypi.org/pypi/gallery-dl/1.32.17/json)。
