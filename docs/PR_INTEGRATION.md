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
| 1 | [#4](https://github.com/Zimkjdv/Smart-Social-Downloader/pull/4) Chrome 配對 | `a18565d` | 待確認 CI 與合併 | — |
| 2 | [#6](https://github.com/Zimkjdv/Smart-Social-Downloader/pull/6) D01 | `a437206` | 等待 #4 | — |
| 3 | [#7](https://github.com/Zimkjdv/Smart-Social-Downloader/pull/7) D02 | `e71a13b` | 等待 #6 | — |
| 4 | [#8](https://github.com/Zimkjdv/Smart-Social-Downloader/pull/8) D03 | `8266257` | 等待 #7 | — |
| 5 | [#9](https://github.com/Zimkjdv/Smart-Social-Downloader/pull/9) D04 | `98adfbd` | 等待 #8 | — |
| 6 | [#10](https://github.com/Zimkjdv/Smart-Social-Downloader/pull/10) D05 | `0ff62a8` | 等待 #9；此 PR 亦承接本文件 | — |
| 7 | [#5](https://github.com/Zimkjdv/Smart-Social-Downloader/pull/5) setup-python 7.1 | `dbd4d2a` | 功能整合後審查；須同步所有工作流程 | — |
| 8 | [#3](https://github.com/Zimkjdv/Smart-Social-Downloader/pull/3) gallery-dl／Playwright | `42bc648` | 功能整合後審查版本、傳遞依賴與授權 | — |
| 延後 | [#2](https://github.com/Zimkjdv/Smart-Social-Downloader/pull/2) pyee 14 | `7d1c727` | 現有 Playwright 1.63.0 要求 pyee <14；不能直接合併 | [既有依賴驗收](DEPENDENCY_ACCEPTANCE.md)；更新 #3 後重查實際限制 |

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
