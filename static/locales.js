/* Stable message keys: edit copy here without renaming keys. */
window.SSDLMessages = {
  "ui.pixiv_engine_missing": {"zh-Hant": "缺少 Pixiv 下載引擎，請恢復基準依賴。", "en": "The Pixiv download engine is missing. Restore the baseline dependencies."},
  "ui.pixiv_engine_unsupported": {"zh-Hant": "目前的 Pixiv 引擎不支援作者作品，請更新引擎。", "en": "The current Pixiv engine does not support author works. Update the engine."},
  "ui.pixiv_pages_incomplete": {"zh-Hant": "Pixiv 作品頁數不完整，請稍後同步重試。", "en": "The Pixiv work has an incomplete page list. Sync again later."},
  "ui.pixiv_identity_mismatch": {"zh-Hant": "Pixiv 作者或作品頁數不一致，已停止以避免保存錯誤內容。", "en": "The Pixiv author or page count did not match. Stopped to avoid saving the wrong content."},
  "ui.pixiv_originals_incomplete": {"zh-Hant": "Pixiv 原圖清單不完整。", "en": "The Pixiv original-image list is incomplete."},
  "ui.pixiv_duplicate_page": {"zh-Hant": "Pixiv 回傳了重複頁碼。", "en": "Pixiv returned a duplicate page number."},
  "ui.pixiv_unknown_listing": {"zh-Hant": "Pixiv 回傳未知清單類型，請更新引擎後重試。", "en": "Pixiv returned an unknown listing type. Update the engine and retry."},
  "ui.pixiv_auth_response": {"zh-Hant": "Pixiv 授權回應格式不正確，請重新授權。", "en": "Invalid Pixiv authorization response. Authorize again."},
  "ui.pixiv_author_required": {"zh-Hant": "請輸入 Pixiv 作者網址或作者 ID。", "en": "Enter a Pixiv author URL or user ID."},
  "ui.pixiv_author_invalid": {"zh-Hant": "請輸入 Pixiv 作者首頁、作品頁網址或數字作者 ID。", "en": "Enter a Pixiv author homepage, author works URL or numeric user ID."},
  "ui.pixiv_auth_method": {"zh-Hant": "請選擇授權 code 或 Refresh Token 其中一種方式。", "en": "Choose either an authorization code or a refresh token."},
  "ui.pixiv_unavailable_originals": {"zh-Hant": "{count} 個作品未提供可取得的原圖，已略過；其他可取得原圖仍正常處理。", "en": "Skipped {count} works without accessible originals. Other accessible originals were processed normally."},
  "ui.pixiv_incomplete_media": {"zh-Hant": "Pixiv 作品媒體未完整保存，請稍後同步重試。", "en": "The Pixiv work was not fully saved. Sync again later."},
  "ui.author_best_quality": {"zh-Hant": "作者媒體模式使用原圖／最高畫質。", "en": "Author media mode uses originals and the highest video quality."},
  "ui.author_already_pending": {"zh-Hant": "此作者已有等待中或下載中的工作。", "en": "This author already has a queued or active job."},
  "ui.pixiv_author_media": {"zh-Hant": "Pixiv 作者作品", "en": "Pixiv author works"},
  "ui.pixiv_author_title": {"zh-Hant": "Pixiv 作者 · {account}", "en": "Pixiv author · {account}"},
  "ui.pixiv_sign_in": {"zh-Hant": "Pixiv 登入", "en": "Pixiv sign-in"},
  "ui.pixiv_connected": {"zh-Hant": "Pixiv 登入已連接", "en": "Pixiv session connected"},
  "ui.pixiv_connect_required": {"zh-Hant": "需要連接 Pixiv 登入", "en": "Connect a Pixiv session to continue"},
  "ui.pixiv_expired": {"zh-Hant": "Pixiv 登入已失效，請重新授權。", "en": "Pixiv session expired. Authorize again."},
  "ui.pixiv_paste_author": {"zh-Hant": "貼上 Pixiv 作者網址或作者 ID", "en": "Paste a Pixiv author URL or user ID"},
  "ui.pixiv_author_urls": {"zh-Hant": "要下載作品的 Pixiv 作者", "en": "Pixiv authors to download"},
  "ui.pixiv_placeholder": {"zh-Hant": "貼上 Pixiv 作者，每行一個\n\nhttps://www.pixiv.net/users/35692440\n35692440", "en": "Paste Pixiv authors, one per line\n\nhttps://www.pixiv.net/users/35692440\n35692440"},
  "ui.pixiv_profile_description": {"zh-Hant": "先掃描此作者的可存取作品，統計原圖總數，再下載缺少的頁面。包含插畫、多頁漫畫及動圖原始影格；再次同步會補抓新增、缺失或已變更的檔案。", "en": "Scan accessible works to count originals before downloading missing pages. Includes illustrations, manga pages and original animation frames. Sync again to fetch new, missing or changed files."},
  "ui.pixiv_auth_help": {"zh-Hant": "在一般瀏覽器完成 Pixiv 登入。登入前按 F12 開啟 Network，完成後複製 callback 請求的完整網址或 code，立即貼回這裡。code 約 30 秒有效；本工具不讀取帳號密碼。", "en": "Sign into Pixiv in your regular browser. Before signing in, open F12 → Network. Copy the callback request URL or its code and paste it here immediately. The code expires in about 30 seconds. This tool does not read your password."},
  "ui.pixiv_begin": {"zh-Hant": "開啟 Pixiv 授權頁", "en": "Open Pixiv authorization"},
  "ui.pixiv_disconnect": {"zh-Hant": "取消授權／清除登入", "en": "Cancel / clear Pixiv session"},
  "ui.pixiv_reopen": {"zh-Hant": "重新開啟授權頁 ↗", "en": "Reopen authorization page ↗"},
  "ui.pixiv_callback_label": {"zh-Hant": "授權回呼網址或 code", "en": "Authorization callback URL or code"},
  "ui.pixiv_complete": {"zh-Hant": "完成連接", "en": "Complete connection"},
  "ui.pixiv_advanced": {"zh-Hant": "進階：使用既有 Refresh Token", "en": "Advanced: use an existing refresh token"},
  "ui.pixiv_validate_token": {"zh-Hant": "驗證並連接", "en": "Validate and connect"},
  "ui.pixiv_memory": {"zh-Hant": "Pixiv 登入僅保留於記憶體，服務重啟後需要重新連接。", "en": "The Pixiv session stays in memory. Reconnect after restarting the service."},
  "ui.pixiv_dpapi": {"zh-Hant": "Pixiv 登入以 Windows 加密保存，不會寫入工作清單或瀏覽器儲存空間。", "en": "The Pixiv session is encrypted with Windows protection. It is not stored in job history or browser storage."},
  "ui.pixiv_aes": {"zh-Hant": "Pixiv 登入使用現有外部金鑰加密保存；重啟與還原時需要同一金鑰。", "en": "The Pixiv session is encrypted with the existing external key. Retain the same key for restart and recovery."},
  "ui.pixiv_working": {"zh-Hant": "正在處理 Pixiv 登入…", "en": "Processing Pixiv sign-in…"},
  "ui.pixiv_invalid_authorization": {"zh-Hant": "Pixiv 授權網址不正確。", "en": "Invalid Pixiv authorization URL."},
  "ui.pixiv_opened": {"zh-Hant": "授權頁已就緒；若未自動開啟，請按上方連結。登入後立即貼上 callback 網址或 code。", "en": "Authorization is ready. Use the link above if no tab opened. Paste the callback URL or code immediately after signing in."},
  "ui.pixiv_disconnected": {"zh-Hant": "Pixiv 登入已清除，未刪除下載檔案。", "en": "Pixiv session cleared. Downloaded files are retained."},
  "ui.pixiv_paste_code": {"zh-Hant": "請貼上這次 Pixiv 授權的回呼網址或 code。", "en": "Paste the callback URL or code from this authorization attempt."},
  "ui.pixiv_paste_token": {"zh-Hant": "請貼上 Pixiv Refresh Token。", "en": "Paste a Pixiv refresh token."},
  "ui.pixiv_scanning": {"zh-Hant": "正在掃描 Pixiv 作者作品清單", "en": "Scanning Pixiv author works"},
  "ui.pixiv_quality": {"zh-Hant": "Pixiv 原圖／動圖原始影格 · 保留原格式", "en": "Pixiv originals / original animation frames · source format"},
  "ui.pixiv_account_quality": {"zh-Hant": "作者媒體模式使用原圖／最高畫質。", "en": "Author mode uses original images / best quality."},
  "ui.pixiv_pending_author": {"zh-Hant": "此作者已有等待中或下載中的工作。", "en": "This author already has a queued or active job."},
  "ui.pixiv_auth_failed": {"zh-Hant": "Pixiv 授權失敗或 code 已過期，請重新授權；既有登入仍保留。", "en": "Pixiv authorization failed or the code expired. Authorize again. Your existing session is retained."},
  "ui.pixiv_code_expired": {"zh-Hant": "Pixiv 授權已過期，請重新開啟授權頁。", "en": "Pixiv authorization expired. Open a new authorization page."},
  "ui.pixiv_token_format": {"zh-Hant": "Pixiv Refresh Token 格式不正確。", "en": "Invalid Pixiv refresh-token format."},
  "ui.pixiv_code_format": {"zh-Hant": "Pixiv 授權 code 格式不正確。", "en": "Invalid Pixiv authorization-code format."},
  "ui.pixiv_callback_invalid": {"zh-Hant": "Pixiv 回呼網址不正確，請重新授權。", "en": "Invalid Pixiv callback URL. Authorize again."},
  "ui.pixiv_auth_busy": {"zh-Hant": "Pixiv 登入處理中，請稍候。", "en": "Pixiv sign-in is in progress. Please wait."},
  "ui.pixiv_auth_cancelled": {"zh-Hant": "Pixiv 授權已取消，請重新連接。", "en": "Pixiv authorization was cancelled. Connect again."},
  "ui.pixiv_auth_network": {"zh-Hant": "Pixiv 授權無法完成，請確認連線後重新授權。", "en": "Pixiv authorization could not complete. Check your connection and authorize again."},
  "ui.pixiv_auth_storage": {"zh-Hant": "Pixiv 登入無法保存或清除，請檢查儲存權限。", "en": "Cannot save or clear the Pixiv session. Check storage permissions."},
  "ui.pixiv_login_required": {"zh-Hant": "下載 Pixiv 需要登入，請先在設定完成 Pixiv 授權。", "en": "Pixiv downloads require sign-in. Complete Pixiv authorization in settings."},
  "ui.pixiv_login_first": {"zh-Hant": "請先在設定完成 Pixiv 授權。", "en": "Complete Pixiv authorization in settings first."},
  "ui.pixiv_empty": {"zh-Hant": "這位作者目前沒有帳號可存取的圖片作品。", "en": "This author currently has no image works accessible to this account."},
  "ui.pixiv_scope": {"zh-Hant": "已同步 Pixiv 目前允許此登入帳號取得的原圖；動圖以原始影格保存。", "en": "Synced originals currently accessible to this Pixiv account. Animations are saved as original frames."},
  "ui.pixiv_invalid_media": {"zh-Hant": "Pixiv 未提供完整原圖清單；不使用預覽圖代替原檔。", "en": "Pixiv did not provide a complete original-image list. Preview images are not used as originals."},
  "ui.pixiv_scan_incomplete": {"zh-Hant": "Pixiv 作者清單未完整取得，請稍後同步重試。", "en": "The Pixiv author list was incomplete. Sync again later."},

  "ui.x_storage_pending": {"zh-Hant":"X 登入僅傳送至這台電腦的工具，保存方式會依目前設定顯示。不讀取 Google 或 Apple 的登入資料。", "en":"X sessions go only to the tool on this computer. The storage method is shown for your configuration. Google and Apple sessions are not read."},
  "ui.x_connector_download_failed": {"zh-Hant":"無法建立連接器下載檔，請確認公開來源檔案完整。", "en":"Cannot create the connector download. Check that its public source files are intact."},
  "ui.x_open_pairing": {"zh-Hant":"開啟 Chrome 配對頁", "en":"Open Chrome pairing page"},
  "ui.x_pairing_ready": {"zh-Hant":"Chrome 配對已就緒，請在主機 Chrome 完成連接。", "en":"Pairing is ready. Complete the connection in host Chrome."},
  "ui.x_memory_storage": {"zh-Hant":"本次 X 登入僅保留於記憶體，服務重啟後需重新連接。不讀取 Google 或 Apple 的登入資料。", "en":"This X session stays in memory only. Reconnect after a service restart. Google and Apple sessions are not read."},
  "ui.x_key_storage": {"zh-Hant":"X 登入使用獨立金鑰加密保存，重啟時需提供相同金鑰。不讀取 Google 或 Apple 的登入資料。", "en":"The X session is encrypted with a separate key. Provide the same key after restart. Google and Apple sessions are not read."},
  "ui.x_host_pairing": {"zh-Hant":"請在已登入 X 的主機 Chrome 開啟這個工具，再按連接。首次可在配對頁下載並載入 Chrome 連接器。", "en":"Open this tool in host Chrome where X is signed in, then connect. Download and load the connector from the pairing page on first use."},
  "ui.x_host_extension_folder": {"zh-Hant":"下載並解壓連接器，在主機 Chrome 載入 chrome-extension 資料夾；容器內的路徑不能用於主機 Chrome。", "en":"Download and extract the connector, then load its chrome-extension folder in host Chrome. Container paths cannot be used by host Chrome."},
  "ui.x_invalid_pairing": {"zh-Hant":"配對網址不正確，請重新連接。", "en":"Invalid pairing address. Reconnect to try again."},
  "ui.x_use_pairing_link": {"zh-Hant":"請按設定中的「開啟 Chrome 配對頁」繼續。", "en":"Use Open Chrome pairing page in settings to continue."},
  "ui.download_chrome_connector": {"zh-Hant":"下載 Chrome 連接器", "en":"Download Chrome connector"},
  "ui.browser_job_files": {"zh-Hant":"瀏覽工作檔案", "en":"Browse job files"},
  "ui.browser_media_view": {"zh-Hant":"在瀏覽器播放或查看", "en":"Play or view in browser"},
  "ui.browser_media_copy": {"zh-Hant":"選擇檔案後會在瀏覽器開啟；瀏覽器不支援的格式會提供下載。", "en":"Select a file to open it in your browser. Formats without inline support are offered as downloads."},
  "ui.container_file_browser_hint": {"zh-Hant":"請按下載項目的資料夾圖示瀏覽檔案；容器無法開啟主機檔案總管。", "en":"Use a job's folder icon to browse its files. The container cannot launch the host file manager."},
  "ui.x_key_invalid": {"zh-Hant":"X 登入金鑰設定無效；請掛載獨立的 32 位元組金鑰檔案。", "en":"Invalid X session key configuration. Mount a separate 32-byte key file."},
  "ui.x_key_mount": {"zh-Hant":"容器的 X 登入金鑰必須使用獨立的 Docker secret 掛載。", "en":"The container X session key must use its separate Docker secret mount."},
  "ui.x_key_unreadable": {"zh-Hant":"無法讀取 X 登入金鑰；請確認掛載、權限及 32 位元組長度。", "en":"Cannot read the X session key. Check the mount, permissions and exact 32-byte size."},
  "ui.x_key_dependency": {"zh-Hant":"缺少登入加密依賴，請重新建置映像或恢復基準套件。", "en":"Session encryption dependency is missing. Rebuild the image or restore the baseline packages."},
  "ui.x_key_decrypt": {"zh-Hant":"保存的 X 登入無法解密；請使用原金鑰或重新連接，原檔會保留。", "en":"Cannot decrypt the saved X session. Use the original key or reconnect; the original file is retained."},
  "ui.x_host_chrome": {"zh-Hant":"請在主機 Chrome 載入 X 連接器；容器不需要安裝 Chrome。", "en":"Load the X connector in host Chrome. Chrome is not required inside the container."},
  "ui.x_host_origin": {"zh-Hant":"在主機 Chrome 開啟工具的本機網址進行配對。", "en":"Pair from the tool's loopback address in host Chrome."},
  "ui.x_memory_restart": {"zh-Hant":"登入僅保留於記憶體，重啟後請重新連接。", "en":"The session stays in memory; reconnect after restart."},
  "ui.x_key_ready": {"zh-Hant":"獨立金鑰加密保存已就緒。", "en":"External-key encrypted storage is ready."},
  "ui.x_key_check": {"zh-Hant":"無法使用登入金鑰，請檢查掛載、權限及長度。", "en":"The session key is unavailable. Check the mount, permissions and size."},
  "ui.x_storage": {"zh-Hant":"X 登入保存", "en":"X session storage"},
  "ui.media_busy": {"zh-Hant":"媒體讀取忙碌，請稍後再試。", "en":"Media reading is busy. Try again shortly."},
  "ui.x_host_browser_instruction": {"zh-Hant":"請在目前的 Chrome 開啟 X，或在網址列輸入 chrome://extensions 管理連接器。", "en":"Open X in host Chrome, or enter chrome://extensions in its address bar to manage the connector."},
  "ui.x_container_folder_instruction": {"zh-Hant":"請使用網頁中的工作檔案清單；容器無法開啟主機檔案總管。", "en":"Use the web job file list; the container cannot launch the host file manager."},
  "ui.databases": {"zh-Hant":"下載紀錄資料庫", "en":"Download history databases"},
  "ui.database_needs_attention": {"zh-Hant":"資料庫需要注意", "en":"Database needs attention"},
  "ui.database_check": {"zh-Hant":"檢查資料庫", "en":"Check databases"},
  "ui.database_backup": {"zh-Hant":"建立備份", "en":"Create backup"},
  "ui.database_compact": {"zh-Hant":"整理空間", "en":"Compact databases"},
  "ui.database_not_checked": {"zh-Hant":"尚未檢查資料庫。", "en":"Databases have not been checked yet."},
  "ui.database_running": {"zh-Hant":"正在處理資料庫，請稍候…", "en":"Database operation in progress…"},
  "ui.database_complete": {"zh-Hant":"資料庫操作已完成。", "en":"Database operation completed."},
  "ui.database_capacity": {"zh-Hant":"資料庫與日誌共 {size}；預估可回收空間 {free}。", "en":"Databases and journals: {size}; estimated reusable free pages: {free}."},
  "ui.database_entry": {"zh-Hant":"{count} 筆紀錄 · 主檔 {size} · WAL {wal} · 可回收 {free}", "en":"{count} records · database {size} · WAL {wal} · free pages {free}"},
  "ui.database_backup_location": {"zh-Hant":"最近備份：data/database-backups/{name}（{size}）。", "en":"Latest backup: data/database-backups/{name} ({size})."},
  "ui.database_missing": {"zh-Hant":"尚未建立；首次相關下載時會自動建立。", "en":"Not created yet; relevant downloads create it automatically."},
  "ui.database_wal_busy": {"zh-Hant":"讀取者仍在使用 WAL，未強制縮減日誌。", "en":"A reader still needs the WAL; journal truncation was deferred."},
  "ui.database_no_files": {"zh-Hant":"目前沒有資料庫需要處理。", "en":"There are no databases to process yet."},
  "ui.database_maintenance_hint": {"zh-Hant":"備份或整理前請暫停佇列，等待下載結束。整理會先建立備份，再回收資料庫未使用空間，保留去重紀錄與媒體原檔。備份含私人來源與路徑，請勿公開分享。", "en":"Pause the queue and wait for downloads to finish before backup or compaction. Compaction first creates a backup and then reclaims unused database space, preserving dedup records and original media. Backups contain private sources and paths; keep them private."},
  "ui.database_confirm_title": {"zh-Hant":"整理資料庫空間？", "en":"Compact database space?"},
  "ui.database_confirm_copy": {"zh-Hant":"將先備份全部現有資料庫，再回收未使用空間。保留全部紀錄與媒體原檔；備份需要額外磁碟空間，維護期間不會開始新下載。", "en":"Back up all existing databases, then reclaim unused space. All records and original media are retained. Backups need additional disk space; new downloads wait until maintenance finishes."},
  "ui.database_confirm": {"zh-Hant":"備份並整理", "en":"Back up and compact"},
  "ui.database_busy": {"zh-Hant":"資料庫維護正在進行，請稍後再試。", "en":"Database maintenance is already running. Please try again later."},
  "ui.database_pause_required": {"zh-Hant":"請先暫停佇列，並等待目前下載結束，再備份或整理資料庫。", "en":"Pause the queue and wait for active downloads to finish before backing up or compacting databases."},
  "ui.database_closed": {"zh-Hant":"資料庫維護已關閉，請重新啟動工具。", "en":"Database maintenance is closed. Restart the tool."},
  "ui.database_path_blocked": {"zh-Hant":"資料庫路徑不是一般檔案或資料夾，已停止操作。", "en":"A database path is not a regular file or directory. The operation was stopped."},
  "ui.database_locked": {"zh-Hant":"資料庫正在使用中，請稍後重新檢查。", "en":"A database is locked. Check again later."},
  "ui.database_invalid": {"zh-Hant":"資料庫無法通過完整性檢查；原檔保留，請查看備份與修復說明。", "en":"A database failed its integrity check. The original is preserved; see the backup and recovery guide."},
  "ui.database_schema": {"zh-Hant":"資料庫結構無法辨識，已保留原檔並停止整理。", "en":"The database structure is unfamiliar. The original is preserved and compaction was stopped."},
  "ui.database_io": {"zh-Hant":"資料庫操作失敗，請檢查磁碟空間與存取權限。", "en":"Database I/O failed. Check disk space and permissions."},
  "ui.database_error": {"zh-Hant":"資料庫操作未完成；原檔與已完成的備份保留。", "en":"The database operation did not finish. Originals and completed backups are preserved."},
  "ui.database_timeout": {"zh-Hant":"資料庫操作超過時間限制，請稍後再試。", "en":"Database maintenance reached its time limit. Try again later."},
  "ui.database_cancelled": {"zh-Hant":"資料庫維護已取消，已完成的備份保留。", "en":"Database maintenance was cancelled. Completed backups are preserved."},
  "ui.database_arguments": {"zh-Hant":"資料庫操作參數不正確。", "en":"Invalid database operation parameters."},
  "ui.database_confirmation_required": {"zh-Hant":"請先確認資料庫整理操作。", "en":"Confirm database compaction first."},
  "ui.state_too_large": {
    "zh-Hant": "下載紀錄超過 64 MiB 保存容量；變更僅在記憶體中。請先備份，再清理不需要的下載項目並重新保存；媒體原檔不會刪除。",
    "en": "Download history exceeds the 64 MiB save limit; changes are only in memory. Back up the history, clear unneeded jobs, then save again. Original media files will not be deleted."
  },
  "ui.state_read_too_large": {
    "zh-Hant": "下載紀錄或備份超過 64 MiB 讀取上限；原檔保留，請先備份並修復紀錄後重新啟動。",
    "en": "Download history or its backup exceeds the 64 MiB read limit. Original records are preserved. Back up and repair the history before restarting."
  },
  "ui.history_capacity": {
    "zh-Hant": "已保存紀錄：{size} / {limit}。",
    "en": "Saved history: {size} / {limit}."
  },
  "ui.not_yet_saved": {
    "zh-Hant": "尚無已保存容量",
    "en": "size not yet available"
  },
  "ui.history_capacity_warning": {
    "zh-Hant": "紀錄接近或超過保存上限；請先備份並清理不需要的下載項目。",
    "en": "History is near or above the save limit. Back it up and clear unneeded jobs."
  },
  "ui.pause_requires_boolean": {
    "zh-Hant": "暫停設定必須是 true 或 false。",
    "en": "The pause setting must be true or false."
  },
  "ui.http_read_timeout": {
    "zh-Hant": "請求讀取逾時，請重新操作。",
    "en": "Request input timed out. Please try again."
  },
  "ui.http_incomplete": {
    "zh-Hant": "請求內容不完整，請重新操作。",
    "en": "The request was incomplete. Please try again."
  },
  "ui.http_busy": {
    "zh-Hant": "本機服務忙碌，請稍後重試。",
    "en": "The local service is busy. Please try again shortly."
  },
  "ui.worker_message_too_large": {
    "zh-Hant": "下載工作資料超過 64 MiB 通訊容量；此工作已停止，已下載原檔保留，後續佇列會繼續。",
    "en": "Job data exceeds the 64 MiB communication limit. This job has stopped; downloaded originals are preserved and the queue will continue."
  },
  "ui.worker_protocol_error": {
    "zh-Hant": "下載工作通訊不完整或格式錯誤，請重試；後續佇列會繼續。",
    "en": "Job communication was incomplete or invalid. Retry the download; the queue will continue."
  },
  "ui.history_restore_failed": {
    "zh-Hant": "下載紀錄無法完整恢復；原檔與備份保留，請修復紀錄後重新啟動。",
    "en": "Download history could not be fully restored. The original and backup are preserved; repair the history and restart."
  },
  "ui.application_version": {
    "zh-Hant": "應用程式版本",
    "en": "Application version"
  },
  "ui.platform_cooldown_mode": {
    "zh-Hant": "平台冷卻模式",
    "en": "Platform cooldown mode"
  },
  "ui.per_platform_cooldowns_default": {
    "zh-Hant": "各平台獨立冷卻（預設）",
    "en": "Per-platform cooldowns (default)"
  },
  "ui.shared_cooldown_for_all_platforms": {
    "zh-Hant": "全部平台共用冷卻",
    "en": "Shared cooldown for all platforms"
  },
  "ui.per_platform_mode_lets_other_platforms_continue": {
    "zh-Hant": "各平台模式可繼續其他平台的工作；全域 Rate 上限、單 worker 與請求間隔仍共同遵守。切換模式不會清除既有冷卻。",
    "en": "Per-platform mode lets other platforms continue. The global hourly limit, single worker and request interval still apply. Changing modes preserves existing cooldowns."
  },
  "ui.platform_cooling_down_for_seconds_s": {
    "zh-Hant": "{platform}：冷卻 {seconds} 秒",
    "en": "{platform}: cooling down for {seconds}s"
  },
  "ui.shared_cooldown_seconds_s": {
    "zh-Hant": "共用冷卻 {seconds} 秒",
    "en": "Shared cooldown: {seconds}s"
  },
  "ui.no_platform_cooldowns": {
    "zh-Hant": "目前沒有平台冷卻",
    "en": "No platform cooldowns"
  },
  "ui.invalid_platform_cooldown_mode": {
    "zh-Hant": "平台冷卻模式不正確",
    "en": "Invalid platform cooldown mode"
  },
  "ui.choose_media_to_download": {
    "zh-Hant": "選擇要下載的媒體",
    "en": "Choose media to download"
  },
  "ui.this_page_contains_multiple_players_choose_one": {
    "zh-Hant": "此頁有多個播放器。選擇其中一個後加入佇列；同一播放器的畫質版本會依畫質設定選擇。",
    "en": "This page contains multiple players. Choose one to queue it. Renditions within the same player follow your video quality setting."
  },
  "ui.to_choose": {
    "zh-Hant": "待選擇",
    "en": "To choose"
  },
  "ui.choose_media": {
    "zh-Hant": "待選擇媒體",
    "en": "Choose media"
  },
  "ui.choose_media_to_download_2": {
    "zh-Hant": "請選擇要下載的媒體",
    "en": "Choose media to download"
  },
  "ui.choose_later": {
    "zh-Hant": "稍後選擇",
    "en": "Choose later"
  },
  "ui.player_count": {
    "zh-Hant": "播放器 {count}",
    "en": "Player {count}"
  },
  "ui.count_source_variants_found": {
    "zh-Hant": "發現 {count} 個來源版本",
    "en": "{count} source variants found"
  },
  "ui.media_selected_and_queued": {
    "zh-Hant": "已選擇媒體並加入下載佇列。",
    "en": "Media selected and queued."
  },
  "ui.this_page_contains_multiple_media_items_choose": {
    "zh-Hant": "此網頁有多個媒體，請先選擇要下載的播放器。",
    "en": "This page contains multiple media items. Choose a player to download."
  },
  "ui.the_media_selection_changed_refresh_the_status": {
    "zh-Hant": "媒體選擇已更新，請重新整理狀態。",
    "en": "The media selection changed. Refresh the status."
  },
  "ui.choose_media_from_this_list": {
    "zh-Hant": "請選擇清單中的媒體。",
    "en": "Choose media from this list."
  },
  "ui.the_selected_player_changed_extract_the_url": {
    "zh-Hant": "選擇的播放器已變更，請重新解析網址。",
    "en": "The selected player changed. Extract the URL again."
  },
  "ui.too_many_media_players_paste_an_individual": {
    "zh-Hant": "網頁媒體數量超過解析上限，請改貼單一播放器網址。",
    "en": "Too many media players. Paste an individual player URL."
  },
  "ui.smart_social_downloader_home": {
    "zh-Hant": "Smart Social Downloader 首頁",
    "en": "Smart Social Downloader home"
  },
  "ui.runs_on_this_device": {
    "zh-Hant": "僅在這台裝置執行",
    "en": "Runs on this device"
  },
  "ui.download_rate_and_file_statistics": {
    "zh-Hant": "下載速率與檔案統計",
    "en": "Download rate and file statistics"
  },
  "ui.jobs_started_in_the_last_60_minutes": {
    "zh-Hant": "最近 60 分鐘啟動的下載工作數／每小時上限",
    "en": "Jobs started in the last 60 minutes / hourly limit"
  },
  "ui.open_download_folder": {
    "zh-Hant": "開啟下載資料夾",
    "en": "Open download folder"
  },
  "ui.calculating": {
    "zh-Hant": "統計中",
    "en": "Calculating…"
  },
  "ui.connect_your_x_session_from_chrome": {
    "zh-Hant": "連接 Chrome 中的 X 登入狀態",
    "en": "Connect your X session from Chrome"
  },
  "ui.connect_chrome": {
    "zh-Hant": "連接 Chrome 登入",
    "en": "Connect Chrome"
  },
  "ui.pause_upcoming_jobs_the_current_download_will": {
    "zh-Hant": "暫停後續工作，正在下載的工作會繼續完成",
    "en": "Pause upcoming jobs; the current download will finish"
  },
  "ui.download_settings": {
    "zh-Hant": "下載設定",
    "en": "Download settings"
  },
  "ui.download_workspace": {
    "zh-Hant": "下載工作區",
    "en": "Download workspace"
  },
  "ui.checking_engines": {
    "zh-Hant": "引擎檢查中",
    "en": "Checking engines"
  },
  "ui.engines_ready": {
    "zh-Hant": "引擎已就緒",
    "en": "Engines ready"
  },
  "ui.update_engines": {
    "zh-Hant": "引擎待更新",
    "en": "Update engines"
  },
  "ui.service_offline": {
    "zh-Hant": "服務未連線",
    "en": "Service offline"
  },
  "ui.checking_download_engines": {
    "zh-Hant": "下載引擎檢查中",
    "en": "Checking download engines"
  },
  "ui.checking_the_local_service": {
    "zh-Hant": "正在確認本機服務狀態",
    "en": "Checking the local service"
  },
  "ui.safe_queue_status": {
    "zh-Hant": "安全佇列狀態",
    "en": "Safe queue status"
  },
  "ui.queue_idle": {
    "zh-Hant": "佇列閒置",
    "en": "Queue idle"
  },
  "ui.waiting_for_new_jobs": {
    "zh-Hant": "等待新任務",
    "en": "Waiting for new jobs"
  },
  "ui.ready_to_download": {
    "zh-Hant": "準備下載",
    "en": "Ready to download"
  },
  "ui.processing": {
    "zh-Hant": "正在處理",
    "en": "Processing"
  },
  "ui.local_service_offline": {
    "zh-Hant": "本機服務未連線",
    "en": "Local service offline"
  },
  "ui.queue_ready_idle": {
    "zh-Hant": "Queue Ready / Idle · 佇列準備就緒",
    "en": "Queue Ready / Idle"
  },
  "ui.add_a_video_image_or_post_url": {
    "zh-Hant": "等待加入影片、圖片或貼文網址",
    "en": "Add a video, image or post URL to begin"
  },
  "ui.queue_is_idle_waiting_for_jobs": {
    "zh-Hant": "佇列閒置，等待新任務",
    "en": "Queue is idle, waiting for jobs"
  },
  "ui.request_interval_1s": {
    "zh-Hant": "請求間隔 ≥ 1 秒",
    "en": "Request interval ≥ 1s"
  },
  "ui.download_overview": {
    "zh-Hant": "下載概覽",
    "en": "Download overview"
  },
  "ui.add_downloads": {
    "zh-Hant": "新增下載",
    "en": "Add Downloads"
  },
  "ui.download_mode": {
    "zh-Hant": "下載模式",
    "en": "Download mode"
  },
  "ui.media_urls": {
    "zh-Hant": "媒體網址",
    "en": "Media URLs"
  },
  "ui.x_account_media": {
    "zh-Hant": "X 帳號媒體",
    "en": "X Account Media"
  },
  "ui.scan_the_media_list_first_to_show": {
    "zh-Hant": "先掃描媒體清單，顯示總檔案數、需要下載與已存在數量，再依序下載。包含此帳號發布的圖片、影片及回覆媒體，不含轉發或引述；再次執行會補抓新增及未完成的內容。",
    "en": "Scan the media list first to show total files, files to download and existing files, then download in order. Includes images, videos and reply media posted by this account; excludes reposted and quoted media. Run again to fetch new and unfinished content."
  },
  "ui.x_account_media_counts": {
    "zh-Hant": "X 帳號媒體數量",
    "en": "X account media counts"
  },
  "ui.total_files": {
    "zh-Hant": "總檔案數",
    "en": "Total files"
  },
  "ui.to_download": {
    "zh-Hant": "需要下載",
    "en": "To download"
  },
  "ui.existing": {
    "zh-Hant": "已存在",
    "en": "Existing"
  },
  "ui.found_so_far": {
    "zh-Hant": "已找到",
    "en": "Found so far"
  },
  "ui.waiting_to_scan_the_media_list": {
    "zh-Hant": "等待掃描媒體清單",
    "en": "Waiting to scan the media list"
  },
  "ui.scanning_the_x_account_media_list": {
    "zh-Hant": "正在掃描 X 帳號媒體清單",
    "en": "Scanning the X account media list"
  },
  "ui.scan_finished_preparing_to_download_account_media": {
    "zh-Hant": "掃描完成，準備下載帳號媒體",
    "en": "Scan finished; preparing to download account media"
  },
  "ui.files_files_found_so_far_total_available": {
    "zh-Hant": "已找到 {files} 個檔案 · 總數待掃描完成",
    "en": "{files} files found so far · total available after scanning"
  },
  "ui.files_total_files_done_files_completed_remaining": {
    "zh-Hant": "共 {files} 個檔案 · 已完成 {done}/{files} · 待下載 {remaining}",
    "en": "{files} total files · {done}/{files} completed · {remaining} remaining"
  },
  "ui.the_total_is_based_on_the_accessible": {
    "zh-Hant": "總數以本次 X 提供的可存取媒體清單為準",
    "en": "The total is based on the accessible media returned by X during this scan"
  },
  "ui.scanning_is_incomplete_showing_the_number_found": {
    "zh-Hant": "掃描尚未完成，目前顯示已找到的數量",
    "en": "Scanning is incomplete; showing the number found so far"
  },
  "ui.refresh_download_status": {
    "zh-Hant": "更新下載狀態",
    "en": "Refresh download status"
  },
  "ui.refresh_download_status_automatically_every_30_seconds": {
    "zh-Hant": "更新下載狀態：閒置每 30 秒、處理中每 2 秒自動更新",
    "en": "Refresh download status: automatically every 30 seconds when idle and every 2 seconds while processing"
  },
  "ui.refreshing_status": {
    "zh-Hant": "正在更新狀態…",
    "en": "Refreshing status…"
  },
  "ui.download_status_refreshed": {
    "zh-Hant": "下載狀態已更新",
    "en": "Download status refreshed"
  },
  "ui.could_not_refresh_status_check_that_the": {
    "zh-Hant": "無法更新狀態，請確認本機服務仍在執行。",
    "en": "Could not refresh status. Check that the local service is running."
  },
  "ui.paste_an_x_profile_url_or_username": {
    "zh-Hant": "貼上 X 帳號網址或 @帳號",
    "en": "Paste an X profile URL or @username"
  },
  "ui.x_accounts_to_download_media_from": {
    "zh-Hant": "要下載媒體的 X 帳號",
    "en": "X accounts to download media from"
  },
  "ui.paste_x_accounts_one_per_line_https": {
    "zh-Hant": "貼上 X 帳號，每行一個\n\nhttps://x.com/username\n@username",
    "en": "Paste X accounts, one per line\n\nhttps://x.com/username\n@username"
  },
  "ui.download_images_and_videos_posted_by_this": {
    "zh-Hant": "下載此帳號發布的圖片與影片，包含回覆中的媒體；不含轉發或引述的媒體。再次執行會補抓新增及未完成的內容。",
    "en": "Download images and videos posted by this account, including media in replies. Reposted and quoted media are excluded. Run again to fetch new and unfinished content."
  },
  "ui.connect_an_x_session_to_continue": {
    "zh-Hant": "需要連接 X 登入",
    "en": "Connect an X session to continue"
  },
  "ui.x_session_connected": {
    "zh-Hant": "X 登入已連接",
    "en": "X session connected"
  },
  "ui.count_accounts": {
    "zh-Hant": "{count} 個帳號",
    "en": "{count} accounts"
  },
  "ui.x_account_media_account": {
    "zh-Hant": "X 帳號媒體 · @{account}",
    "en": "X account media · @{account}"
  },
  "ui.posts_posts_processed_files_files_skipped_downloaded": {
    "zh-Hant": "已處理 {posts} 則貼文 · {files} 個檔案 · 略過 {skipped} 則已下載",
    "en": "{posts} posts processed · {files} files · {skipped} downloaded posts skipped"
  },
  "ui.size_of_saved_account_files_plus_bytes": {
    "zh-Hant": "帳號已保存檔案的容量，加上目前檔案已接收的容量",
    "en": "Size of saved account files plus bytes received for the current file"
  },
  "ui.sync_account_media_fetch_new_or_unfinished": {
    "zh-Hant": "同步帳號媒體：補抓新增或未完成的內容，略過已下載貼文",
    "en": "Sync account media: fetch new or unfinished content and skip downloaded posts"
  },
  "ui.stop_account_download_after_the_current_post": {
    "zh-Hant": "停止帳號下載：完成目前貼文後停止，保留檔案",
    "en": "Stop account download after the current post; keep saved files"
  },
  "ui.stopping_keeping_downloaded_files": {
    "zh-Hant": "正在停止，保留已下載檔案",
    "en": "Stopping; keeping downloaded files"
  },
  "ui.pause_upcoming_posts_the_current_post_will": {
    "zh-Hant": "暫停後續貼文，正在下載的貼文會繼續完成",
    "en": "Pause upcoming posts; the current post will finish"
  },
  "ui.paste_an_x_profile_url_or_username_2": {
    "zh-Hant": "請先貼上 X 帳號網址或 @帳號。",
    "en": "Paste an X profile URL or @username first."
  },
  "ui.enter_an_x_profile_url_media_page": {
    "zh-Hant": "請輸入 X 帳號首頁、媒體頁網址或 @帳號。",
    "en": "Enter an X profile URL, media-page URL, or @username."
  },
  "ui.x_usernames_must_contain_1_15_letters": {
    "zh-Hant": "X 帳號名稱需為 1～15 個英文字母、數字或底線。",
    "en": "X usernames must contain 1–15 letters, digits, or underscores."
  },
  "ui.post_media_was_not_saved_completely_sync": {
    "zh-Hant": "X 貼文媒體未完整保存，請稍後同步重試。",
    "en": "Post media was not saved completely. Sync again to retry."
  },
  "ui.an_x_session_is_required_for_account": {
    "zh-Hant": "下載 X 帳號媒體需要登入，請先按「連接 Chrome 登入」。",
    "en": "An X session is required for account media. Connect Chrome first."
  },
  "ui.this_x_engine_does_not_support_account": {
    "zh-Hant": "目前的 X 引擎不支援帳號媒體，請重新執行 start.bat 更新。",
    "en": "This X engine does not support account media. Run start.bat to update."
  },
  "ui.reading_x_account_media": {
    "zh-Hant": "正在讀取 X 帳號媒體",
    "en": "Reading X account media"
  },
  "ui.downloading_account_media": {
    "zh-Hant": "下載帳號媒體中",
    "en": "Downloading account media"
  },
  "ui.x_returned_an_incomplete_media_list_sync": {
    "zh-Hant": "X 回傳的貼文媒體清單不完整，請稍後同步重試。",
    "en": "X returned an incomplete media list. Sync again to retry."
  },
  "ui.x_account_extraction_did_not_finish_sync": {
    "zh-Hant": "X 帳號媒體解析未完成，請稍後同步重試。",
    "en": "X account extraction did not finish. Sync again to retry."
  },
  "ui.processed_currently_accessible_x_media_the_platform": {
    "zh-Hant": "已處理 X 目前可存取的媒體；平台可能未提供完整歷史內容。",
    "en": "Processed currently accessible X media. The platform may not expose the full history."
  },
  "ui.no_accessible_media_was_found_for_this": {
    "zh-Hant": "此帳號目前沒有可取得的媒體，或 X 未提供可見內容。",
    "en": "No accessible media was found for this account, or X did not expose visible content."
  },
  "ui.account_download_stopped_saved_files_are_kept": {
    "zh-Hant": "帳號下載已停止；已保存的檔案保留，可按同步繼續。",
    "en": "Account download stopped. Saved files are kept; sync again to continue."
  },
  "ui.account_download_paused": {
    "zh-Hant": "帳號下載已暫停",
    "en": "Account download paused"
  },
  "ui.account_download_waiting_for_hourly_quota": {
    "zh-Hant": "帳號下載等待每小時額度",
    "en": "Account download waiting for hourly quota"
  },
  "ui.safe_delay_wait_seconds_s": {
    "zh-Hant": "安全延時，等待 {seconds} 秒",
    "en": "Safe delay: wait {seconds}s"
  },
  "ui.account_media_sync_finished": {
    "zh-Hant": "帳號媒體同步完成",
    "en": "Account media sync finished"
  },
  "ui.no_downloadable_media": {
    "zh-Hant": "沒有可下載媒體",
    "en": "No downloadable media"
  },
  "ui.stop_and_remove_after_the_current_post": {
    "zh-Hant": "目前貼文完成後停止並移出清單",
    "en": "Stop and remove after the current post finishes"
  },
  "ui.count_more_files_use_play_view_to": {
    "zh-Hant": "另有 {count} 個檔案，可按播放／查看選擇",
    "en": "{count} more files; use Play / View to choose a file"
  },
  "ui.show_more_files_count_remaining": {
    "zh-Hant": "顯示更多檔案（還有 {count} 個）",
    "en": "Show more files ({count} remaining)"
  },
  "ui.stopped": {
    "zh-Hant": "已停止",
    "en": "Stopped"
  },
  "ui.skipped_file_already_exists": {
    "zh-Hant": "已略過，檔案已存在",
    "en": "Skipped; file already exists"
  },
  "ui.last_check_the_file_already_existed_so": {
    "zh-Hant": "上次檢查：檔案已存在，已略過下載。",
    "en": "Last check: the file already existed, so downloading was skipped."
  },
  "ui.queued_to_check_existing_files": {
    "zh-Hant": "等待檢查已下載檔案",
    "en": "Queued to check existing files"
  },
  "ui.reusing_count_items_to_check_files_at": {
    "zh-Hant": "已沿用 {count} 個項目，檢查原位置檔案。",
    "en": "Reusing {count} items to check files at their original paths."
  },
  "ui.count_items_are_already_queued_no_duplicates": {
    "zh-Hant": "{count} 個項目已在佇列中，未重複加入。",
    "en": "{count} items are already queued; no duplicates were added."
  },
  "ui.new_added_reused_reused_already_queued_pending": {
    "zh-Hant": "新增 {added} 個 · 沿用 {reused} 個 · 已在佇列 {pending} 個。",
    "en": "New: {added} · Reused: {reused} · Already queued: {pending}."
  },
  "ui.new_added_reused_reused_already_queued_pending_2": {
    "zh-Hant": "新增 {added} 個 · 沿用 {reused} 個 · 已在佇列 {pending} 個；{rejected} 個網址未加入。",
    "en": "New: {added} · Reused: {reused} · Already queued: {pending}; {rejected} URLs were not added."
  },
  "ui.could_not_read_the_image_download_history": {
    "zh-Hant": "無法讀取已下載圖片紀錄，本次會重新下載。",
    "en": "Could not read the image download history. Downloading again."
  },
  "ui.the_file_was_saved_but_its_download": {
    "zh-Hant": "檔案已保存，但無法更新已下載紀錄；下次可能重新下載。",
    "en": "The file was saved, but its download history could not be updated. It may be downloaded again next time."
  },
  "ui.the_file_path_is_outside_this_job": {
    "zh-Hant": "檔案路徑不在此項目的下載資料夾內。",
    "en": "The file path is outside this job’s download directory."
  },
  "ui.invalid_download_mode": {
    "zh-Hant": "下載模式不正確",
    "en": "Invalid download mode"
  },
  "ui.this_x_account_already_has_a_queued": {
    "zh-Hant": "此 X 帳號已有等待中或下載中的工作。",
    "en": "This X account already has a queued or active job."
  },
  "ui.only_an_active_x_account_download_can": {
    "zh-Hant": "只有進行中的 X 帳號下載可以停止。",
    "en": "Only an active X account download can be stopped."
  },
  "ui.add_to_download_queue": {
    "zh-Hant": "加入下載佇列",
    "en": "Add to Download Queue"
  },
  "ui.paste_video_image_or_post_urls": {
    "zh-Hant": "貼上影片、圖片或貼文網址",
    "en": "Paste video, image, or post URLs"
  },
  "ui.platforms": {
    "zh-Hant": "常見平台",
    "en": "Platforms"
  },
  "ui.more": {
    "zh-Hant": "+ 更多",
    "en": "+ More"
  },
  "ui.original_size_images_best_available_video_original": {
    "zh-Hant": "原尺寸圖片 · 最高可用影片畫質 · 保留來源編碼",
    "en": "Original-size images · Best available video · Original encoding"
  },
  "ui.urls_to_download": {
    "zh-Hant": "要下載的網址",
    "en": "URLs to download"
  },
  "ui.paste_media_urls_one_per_line_https": {
    "zh-Hant": "貼上媒體網址，每行一個\n\nhttps://x.com/使用者/status/貼文編號\nhttps://www.instagram.com/p/...",
    "en": "Paste media URLs, one per line\n\nhttps://x.com/username/status/post_id\nhttps://www.instagram.com/p/..."
  },
  "ui.0_urls": {
    "zh-Hant": "0 個網址",
    "en": "0 URLs"
  },
  "ui.count_urls": {
    "zh-Hant": "{count} 個網址",
    "en": "{count} URLs"
  },
  "ui.random_3_8_second_delay_between_jobs": {
    "zh-Hant": "每項工作間隨機延時 3～8 秒",
    "en": "Random 3–8 second delay between jobs"
  },
  "ui.active_queue_monitor": {
    "zh-Hant": "即時佇列監控",
    "en": "Active Queue Monitor"
  },
  "ui.current_download_activity": {
    "zh-Hant": "目前下載狀態",
    "en": "Current download activity"
  },
  "ui.queue_is_ready": {
    "zh-Hant": "佇列準備就緒",
    "en": "Queue is ready"
  },
  "ui.add_links_to_start_your_media_collection": {
    "zh-Hant": "加入連結，開始整理你的媒體收藏",
    "en": "Add links to start your media collection"
  },
  "ui.queued": {
    "zh-Hant": "等待中",
    "en": "Queued"
  },
  "ui.downloading": {
    "zh-Hant": "下載中",
    "en": "Downloading"
  },
  "ui.completed": {
    "zh-Hant": "已完成",
    "en": "Completed"
  },
  "ui.failed": {
    "zh-Hant": "失敗",
    "en": "Failed"
  },
  "ui.processing_2": {
    "zh-Hant": "處理中",
    "en": "Processing"
  },
  "ui.downloads": {
    "zh-Hant": "下載項目",
    "en": "Downloads"
  },
  "ui.manage_media_in_your_download_queue": {
    "zh-Hant": "管理目前工作階段的媒體",
    "en": "Manage media in your download queue"
  },
  "ui.retry_failed": {
    "zh-Hant": "重試失敗",
    "en": "Retry failed"
  },
  "ui.pause_queue": {
    "zh-Hant": "暫停佇列",
    "en": "Pause queue"
  },
  "ui.resume_queue": {
    "zh-Hant": "繼續佇列",
    "en": "Resume queue"
  },
  "ui.clear_completed": {
    "zh-Hant": "清除已完成",
    "en": "Clear completed"
  },
  "ui.clear_all": {
    "zh-Hant": "清除全部",
    "en": "Clear all"
  },
  "ui.clear_queued_and_previous_jobs_remove_the": {
    "zh-Hant": "清除等待中及歷史項目；目前工作完成後移除，保留下載檔案",
    "en": "Clear queued and previous jobs; remove the active job when it finishes. Keep downloaded files."
  },
  "ui.filter_downloads": {
    "zh-Hant": "篩選下載項目",
    "en": "Filter downloads"
  },
  "ui.all": {
    "zh-Hant": "全部",
    "en": "All"
  },
  "ui.all_jobs": {
    "zh-Hant": "全部項目",
    "en": "All Jobs"
  },
  "ui.filter_by_platform": {
    "zh-Hant": "平台篩選",
    "en": "Filter by platform"
  },
  "ui.all_platforms": {
    "zh-Hant": "所有平台",
    "en": "All platforms"
  },
  "ui.search_downloads": {
    "zh-Hant": "搜尋項目…",
    "en": "Search downloads…"
  },
  "ui.search_downloads_2": {
    "zh-Hant": "搜尋項目",
    "en": "Search downloads"
  },
  "ui.media_source": {
    "zh-Hant": "媒體 / 來源",
    "en": "MEDIA / SOURCE"
  },
  "ui.media_thumbnail": {
    "zh-Hant": "媒體縮圖",
    "en": "Media thumbnail"
  },
  "ui.platform": {
    "zh-Hant": "平台",
    "en": "PLATFORM"
  },
  "ui.added": {
    "zh-Hant": "加入時間",
    "en": "ADDED"
  },
  "ui.status_progress": {
    "zh-Hant": "狀態 / 進度",
    "en": "STATUS / PROGRESS"
  },
  "ui.file_size_download_elapsed_time": {
    "zh-Hant": "容量／下載耗時",
    "en": "File size / download elapsed time"
  },
  "ui.files": {
    "zh-Hant": "檔案",
    "en": "FILES"
  },
  "ui.action": {
    "zh-Hant": "操作",
    "en": "ACTION"
  },
  "ui.no_downloads_to_show": {
    "zh-Hant": "這裡還沒有下載項目",
    "en": "No downloads to show"
  },
  "ui.paste_links_above_to_add_media_to": {
    "zh-Hant": "在上方貼上連結，讓你的收藏開始排隊。",
    "en": "Paste links above to add media to your queue."
  },
  "ui.paste_your_first_link": {
    "zh-Hant": "＋ 貼上第一個連結",
    "en": "+ Paste your first link"
  },
  "ui.showing_0_items": {
    "zh-Hant": "顯示 0 個項目",
    "en": "Showing 0 items"
  },
  "ui.showing_count_items": {
    "zh-Hant": "顯示 {count} 個項目",
    "en": "Showing {count} items"
  },
  "ui.showing_start_end_of_total_items": {
    "zh-Hant": "顯示 {start}–{end}，共 {total} 個項目",
    "en": "Showing {start}–{end} of {total} items"
  },
  "ui.download_list": {
    "zh-Hant": "下載項目清單",
    "en": "Download list"
  },
  "ui.download_list_pagination": {
    "zh-Hant": "下載清單分頁",
    "en": "Download list pagination"
  },
  "ui.per_page": {
    "zh-Hant": "每頁",
    "en": "Per page"
  },
  "ui.items_per_page": {
    "zh-Hant": "每頁項目數",
    "en": "Items per page"
  },
  "ui.previous_page": {
    "zh-Hant": "上一頁",
    "en": "Previous page"
  },
  "ui.next_page": {
    "zh-Hant": "下一頁",
    "en": "Next page"
  },
  "ui.page_page": {
    "zh-Hant": "第 {page} 頁",
    "en": "Page {page}"
  },
  "ui.local_service_online": {
    "zh-Hant": "本機服務運作中",
    "en": "Local service online"
  },
  "ui.close": {
    "zh-Hant": "關閉",
    "en": "Close"
  },
  "ui.manage_downloads_sign_in_and_your_local": {
    "zh-Hant": "管理下載、登入與本機環境。",
    "en": "Manage downloads, sign-in, and your local environment."
  },
  "ui.settings_sections": {
    "zh-Hant": "設定分頁",
    "en": "Settings sections"
  },
  "ui.general": {
    "zh-Hant": "一般設定",
    "en": "General"
  },
  "ui.x_sign_in": {
    "zh-Hant": "X 登入",
    "en": "X sign-in"
  },
  "ui.diagnostics": {
    "zh-Hant": "診斷",
    "en": "Diagnostics"
  },
  "ui.storage_and_thumbnail_cache": {
    "zh-Hant": "容量與縮圖快取",
    "en": "Storage and thumbnail cache"
  },
  "ui.rescan_storage": {
    "zh-Hant": "重新掃描容量",
    "en": "Rescan storage"
  },
  "ui.clear_thumbnail_cache": {
    "zh-Hant": "清理縮圖快取",
    "en": "Clear thumbnail cache"
  },
  "ui.storage_totals_update_incrementally_after_downloads_external": {
    "zh-Hant": "容量在下載完成後增量更新，外部搬移、刪除或新增檔案由每 10 分鐘或手動重掃校正。",
    "en": "Storage totals update incrementally after downloads. External moves, deletions, and additions are reconciled every 10 minutes or by a manual rescan."
  },
  "ui.the_thumbnail_cache_holds_up_to_128": {
    "zh-Hant": "縮圖快取最多 128 MB、1000 個預覽，30 天未使用會回收。清理只移除生成的預覽，需要時會重新產生。",
    "en": "The thumbnail cache holds up to 128 MB and 1,000 previews. Previews unused for 30 days are reclaimed. Clearing removes generated previews; they are regenerated when needed."
  },
  "ui.scanning_the_download_folder_in_the_background": {
    "zh-Hant": "正在背景掃描下載資料夾…",
    "en": "Scanning the download folder in the background…"
  },
  "ui.last_full_scan_time": {
    "zh-Hant": "上次完整掃描：{time}",
    "en": "Last full scan: {time}"
  },
  "ui.thumbnail_cache_size_limit_count_previews": {
    "zh-Hant": "縮圖快取：{size} / {limit} · {count} 個預覽",
    "en": "Thumbnail cache: {size} / {limit} · {count} previews"
  },
  "ui.loading_thumbnail_cache_status": {
    "zh-Hant": "正在取得縮圖快取狀態…",
    "en": "Loading thumbnail cache status…"
  },
  "ui.some_cached_previews_could_not_be_removed": {
    "zh-Hant": " · 部分快取無法清理",
    "en": " · Some cached previews could not be removed"
  },
  "ui.background_storage_scan_started": {
    "zh-Hant": "已開始背景容量掃描",
    "en": "Background storage scan started"
  },
  "ui.thumbnail_cache_cleanup_queued": {
    "zh-Hant": "已排入縮圖快取清理",
    "en": "Thumbnail cache cleanup queued"
  },
  "ui.loading_files": {
    "zh-Hant": "正在載入檔案…",
    "en": "Loading files…"
  },
  "ui.loading_failed_click_to_retry": {
    "zh-Hant": "載入失敗，點擊重試",
    "en": "Loading failed; click to retry"
  },
  "ui.choose_your_save_location_and_x_sign": {
    "zh-Hant": "選擇儲存位置與 X 貼文的登入方式。",
    "en": "Choose your save location and X sign-in method."
  },
  "ui.download_folder_path": {
    "zh-Hant": "下載資料夾路徑",
    "en": "Download folder path"
  },
  "ui.enter_a_full_folder_path_on_this": {
    "zh-Hant": "請輸入這台電腦上的資料夾完整路徑。資料夾不存在時會自動建立。",
    "en": "Enter a full folder path on this computer. Missing folders will be created."
  },
  "ui.safe_queue": {
    "zh-Hant": "安全佇列",
    "en": "Safe queue"
  },
  "ui.hourly_job_limit": {
    "zh-Hant": "每小時工作上限",
    "en": "Hourly job limit"
  },
  "ui.current_usage_40_jobs": {
    "zh-Hant": "目前已用 —/40 個工作",
    "en": "Current usage: —/40 jobs"
  },
  "ui.current_usage_used_limit_jobs": {
    "zh-Hant": "目前已用 {used}/{limit} 個工作",
    "en": "Current usage: {used}/{limit} jobs"
  },
  "ui.reset_rate": {
    "zh-Hant": "重設 Rate",
    "en": "Reset Rate"
  },
  "ui.click_to_confirm_a_rate_reset": {
    "zh-Hant": "點擊確認重設 Rate",
    "en": "Click to confirm a Rate reset"
  },
  "ui.reset_rate_2": {
    "zh-Hant": "重設 Rate？",
    "en": "Reset Rate?"
  },
  "ui.cancel_reset": {
    "zh-Hant": "取消重設",
    "en": "Cancel reset"
  },
  "ui.confirm_reset": {
    "zh-Hant": "確認重設",
    "en": "Confirm reset"
  },
  "ui.clear_the_job_count_for_the_last": {
    "zh-Hant": "確定要清除最近 60 分鐘的工作計數嗎？",
    "en": "Clear the job count for the last 60 minutes?"
  },
  "ui.current_usage_used_limit_after_confirmation_the": {
    "zh-Hant": "目前已用 {used}/{limit}，確認後從 0 重新累計。",
    "en": "Current usage: {used}/{limit}. After confirmation, the count starts again from 0."
  },
  "ui.the_hourly_limit_download_history_job_delays": {
    "zh-Hant": "每小時上限、下載紀錄、工作延時與平台冷卻都會保留。",
    "en": "The hourly limit, download history, job delays and platform cooldown will stay in effect."
  },
  "ui.after_confirmation_clear_the_usage_count_and": {
    "zh-Hant": "確認後將已用計數歸零，後續工作重新累計。每小時上限不變，工作延時與平台冷卻仍會保留。",
    "en": "After confirmation, clear the usage count and count new job starts from now on. The hourly limit, job delays and platform cooldown stay in effect."
  },
  "ui.reset_rate_current_usage_used_limit_jobs": {
    "zh-Hant": "重設 Rate，目前已用 {used}/{limit} 個工作",
    "en": "Reset Rate, current usage: {used}/{limit} jobs"
  },
  "ui.resetting": {
    "zh-Hant": "重設中…",
    "en": "Resetting…"
  },
  "ui.resetting_rate": {
    "zh-Hant": "正在重設 Rate…",
    "en": "Resetting Rate…"
  },
  "ui.rate_reset_new_job_starts_will_be": {
    "zh-Hant": "Rate 已重設，後續工作重新累計。",
    "en": "Rate reset. New job starts will be counted from now on."
  },
  "ui.jobs_60_minutes": {
    "zh-Hant": "個／60 分鐘",
    "en": "jobs / 60 minutes"
  },
  "ui.default_40_range_1_1000_counts_jobs": {
    "zh-Hant": "預設 40，可設定 1～1000。以最近 60 分鐘啟動的工作計算，失敗與重新下載也會計入。儲存後立即套用，保留目前已用計數。",
    "en": "Default: 40. Range: 1–1000. Counts jobs started in the last 60 minutes, including failures and retries. Saving applies the limit immediately and preserves the current usage count."
  },
  "ui.x_session_connection": {
    "zh-Hant": "X 登入連接",
    "en": "X session connection"
  },
  "ui.use_your_existing_x_session_in_chrome": {
    "zh-Hant": "使用平常 Chrome 中已登入的 X。無法直接讀取時，會開啟一般 Chrome 的本機連接頁；第一次載入連接器後，便可一鍵同步並自動重試失敗的 X 項目。",
    "en": "Use your existing X session in Chrome. If it cannot be read directly, the connection page opens in regular Chrome. Load the connector once, then sync with one click and automatically retry failed X jobs."
  },
  "ui.connect_chrome_2": {
    "zh-Hant": "一鍵連接 Chrome",
    "en": "Connect Chrome"
  },
  "ui.reconnect_chrome": {
    "zh-Hant": "重新連接 Chrome",
    "en": "Reconnect Chrome"
  },
  "ui.disconnect": {
    "zh-Hant": "停用連接",
    "en": "Disconnect"
  },
  "ui.cancel_connection": {
    "zh-Hant": "取消登入",
    "en": "Cancel connection"
  },
  "ui.x_session_not_connected": {
    "zh-Hant": "尚未連接 X 登入",
    "en": "X session not connected"
  },
  "ui.open_x_in_regular_chrome": {
    "zh-Hant": "在一般 Chrome 開啟 X",
    "en": "Open X in regular Chrome"
  },
  "ui.chrome_connector_setup": {
    "zh-Hant": "Chrome 連接器安裝步驟",
    "en": "Chrome connector setup"
  },
  "ui.only_x_session_cookies_are_saved_encrypted": {
    "zh-Hant": "只保留 X 登入 Cookie，在這台電腦以 Windows 加密保存。不需要匯出檔案，也不讀取 Google 或 Apple 的登入資料。",
    "en": "Only X session cookies are saved, encrypted by Windows on this computer. No cookie export is needed; Google and Apple sign-in data is not read."
  },
  "ui.if_x_temporarily_restricts_sign_in_stop": {
    "zh-Hant": "X 顯示暫時限制登入時，請停止反覆嘗試，待限制解除後在一般 Chrome 登入。連接器不能解除帳號限制。",
    "en": "If X temporarily restricts sign-in, stop repeated attempts and sign in through regular Chrome after the restriction ends. The connector cannot remove account restrictions."
  },
  "ui.advanced_use_a_cookie_file": {
    "zh-Hant": "進階：使用 Cookie 檔案",
    "en": "Advanced: use a cookie file"
  },
  "ui.x_cookie_file_path_optional": {
    "zh-Hant": "X Cookie 檔案路徑（選填）",
    "en": "X cookie file path (optional)"
  },
  "ui.e_g_d_cookies_cookies_txt": {
    "zh-Hant": "例如 D:\\Cookies\\cookies.txt",
    "en": "e.g. D:\\Cookies\\cookies.txt"
  },
  "ui.supports_netscape_format_cookies_txt_to_use": {
    "zh-Hant": "支援 Netscape 格式 cookies.txt。如需改用檔案，請先停用 Chrome 連接，再填入完整路徑並儲存。兩者皆未設定時使用公開貼文資料。",
    "en": "Supports Netscape-format cookies.txt. To use a file, disconnect Chrome first, enter the full path and save. Public post data is used when neither option is configured."
  },
  "ui.cancel": {
    "zh-Hant": "取消",
    "en": "Cancel"
  },
  "ui.save_settings": {
    "zh-Hant": "儲存設定",
    "en": "Save settings"
  },
  "ui.download_failure_details": {
    "zh-Hant": "下載失敗原因",
    "en": "Download failure details"
  },
  "ui.raw_engine_diagnostics": {
    "zh-Hant": "引擎詳細訊息",
    "en": "Raw engine diagnostics"
  },
  "ui.download_warnings": {
    "zh-Hant": "下載提醒",
    "en": "Download warnings"
  },
  "ui.close_download_warnings": {
    "zh-Hant": "關閉下載提醒",
    "en": "Close download warnings"
  },
  "ui.messages_from_the_source_and_download_engine": {
    "zh-Hant": "下載來源與引擎的提醒內容",
    "en": "Messages from the source and download engine"
  },
  "ui.choose_a_file": {
    "zh-Hant": "選擇檔案",
    "en": "Choose a file"
  },
  "ui.close_file_selection": {
    "zh-Hant": "關閉檔案選擇",
    "en": "Close file selection"
  },
  "ui.seconds_s": {
    "zh-Hant": "{seconds} 秒",
    "en": "{seconds}s"
  },
  "ui.this_job_will_be_removed_from_the": {
    "zh-Hant": "此工作完成後會自動移出清單",
    "en": "This job will be removed from the list when it finishes"
  },
  "ui.view_details": {
    "zh-Hant": "查看詳細原因",
    "en": "View details"
  },
  "ui.estimated_size_of_the_current_media_received": {
    "zh-Hant": "目前媒體的預估容量；來源未提供總量時顯示已接收容量",
    "en": "Estimated size of the current media; received bytes are shown if the total is unavailable"
  },
  "ui.total_size_of_saved_files_for_this": {
    "zh-Hant": "此項目已保存檔案的總容量",
    "en": "Total size of saved files for this job"
  },
  "ui.elapsed_time_is_not_available": {
    "zh-Hant": "尚無下載耗時紀錄",
    "en": "Elapsed time is not available"
  },
  "ui.elapsed_time_from_start_to_finish_including": {
    "zh-Hant": "下載耗時，從啟動到結束；包含解析與合併，不含排隊時間",
    "en": "Elapsed time from start to finish, including extraction and merging; excludes queue wait"
  },
  "ui.no_file_is_available_yet": {
    "zh-Hant": "尚未有可開啟的檔案",
    "en": "No file is available yet"
  },
  "ui.choose_a_file_to_play_or_view": {
    "zh-Hant": "選擇檔案播放／查看",
    "en": "Choose a file to play or view"
  },
  "ui.view_image_in_the_default_app": {
    "zh-Hant": "查看圖片（使用預設程式）",
    "en": "View image in the default app"
  },
  "ui.play_video_or_audio_in_the_default": {
    "zh-Hant": "播放影片／音訊（使用預設程式）",
    "en": "Play video or audio in the default app"
  },
  "ui.no_saved_file_folder_is_available_yet": {
    "zh-Hant": "尚未有檔案所在資料夾",
    "en": "No saved file folder is available yet"
  },
  "ui.choose_a_file_and_open_its_folder": {
    "zh-Hant": "選擇檔案並開啟所在資料夾",
    "en": "Choose a file and open its folder"
  },
  "ui.open_this_file_s_folder": {
    "zh-Hant": "開啟此檔案所在資料夾",
    "en": "Open this file’s folder"
  },
  "ui.download_again_and_overwrite_files_with_the": {
    "zh-Hant": "重新下載：重新取得媒體並覆寫同名檔案",
    "en": "Download again and overwrite files with the same name"
  },
  "ui.download_in_progress_retry_after_it_finishes": {
    "zh-Hant": "下載中，完成後可重新下載",
    "en": "Download in progress; retry after it finishes"
  },
  "ui.this_job_is_already_queued": {
    "zh-Hant": "此項目已在下載佇列中",
    "en": "This job is already queued"
  },
  "ui.wait_for_this_download_to_finish_before": {
    "zh-Hant": "下載中的項目完成後才能移除",
    "en": "Wait for this download to finish before removing it"
  },
  "ui.remove_from_the_list_and_keep_files": {
    "zh-Hant": "從清單移除，保留檔案",
    "en": "Remove from the list and keep files"
  },
  "ui.remove_from_the_list": {
    "zh-Hant": "從清單移除",
    "en": "Remove from the list"
  },
  "ui.count_media_files": {
    "zh-Hant": "{count} 個媒體檔案",
    "en": "{count} media files"
  },
  "ui.waiting_for_files": {
    "zh-Hant": "等待檔案",
    "en": "Waiting for files"
  },
  "ui.waiting_to_download": {
    "zh-Hant": "等待下載",
    "en": "Waiting to download"
  },
  "ui.original_size_images_best_available_video": {
    "zh-Hant": "原尺寸圖片 / 最高可用影片",
    "en": "Original-size images / best available video"
  },
  "ui.view_all_download_warnings": {
    "zh-Hant": "查看完整下載提醒",
    "en": "View all download warnings"
  },
  "ui.view_count_download_warnings": {
    "zh-Hant": "查看 {count} 個下載提醒",
    "en": "View {count} download warnings"
  },
  "ui.warnings_count": {
    "zh-Hant": "⚠ {count} 個下載提醒",
    "en": "⚠ Warnings: {count}"
  },
  "ui.view": {
    "zh-Hant": "查看 ›",
    "en": "View ›"
  },
  "ui.elapsed_time": {
    "zh-Hant": "耗時 {time}",
    "en": "Elapsed {time}"
  },
  "ui.remaining_time": {
    "zh-Hant": "剩餘 {time}",
    "en": "Remaining {time}"
  },
  "ui.queued_again_resume_the_queue_to_start": {
    "zh-Hant": "已加入重新下載佇列；請按繼續佇列開始",
    "en": "Queued again. Resume the queue to start."
  },
  "ui.queued_for_another_download": {
    "zh-Hant": "已加入重新下載佇列",
    "en": "Queued for another download"
  },
  "ui.download_warnings_count": {
    "zh-Hant": "下載提醒（{count}）",
    "en": "Download warnings ({count})"
  },
  "ui.waiting_for_x": {
    "zh-Hant": "等待 X 登入…",
    "en": "Waiting for X…"
  },
  "ui.x_connected": {
    "zh-Hant": "X 已連接",
    "en": "X connected"
  },
  "ui.x_connected_failed_jobs_have_been_queued": {
    "zh-Hant": "X 登入已連接，失敗項目已排入佇列；請按繼續佇列",
    "en": "X connected. Failed jobs have been queued; resume the queue to start."
  },
  "ui.x_connected_failed_x_jobs_will_be": {
    "zh-Hant": "X 登入已連接，失敗項目將自動重試",
    "en": "X connected. Failed X jobs will be retried automatically."
  },
  "ui.x_connection_failed": {
    "zh-Hant": "X 登入連接失敗",
    "en": "X connection failed"
  },
  "ui.connection_page_opened_in_regular_chrome_load": {
    "zh-Hant": "已開啟一般 Chrome 連接頁；首次使用請載入 Chrome 連接器",
    "en": "Connection page opened in regular Chrome. Load the connector for first-time setup."
  },
  "ui.used_jobs_started_in_the_last_60": {
    "zh-Hant": "最近 60 分鐘已啟動 {used} 個工作，上限 {limit} 個；失敗與重新下載也計入",
    "en": "{used} jobs started in the last 60 minutes, limit {limit}. Failures and retries also count."
  },
  "ui.next_slot_in_about_minutes_minutes": {
    "zh-Hant": "。約 {minutes} 分鐘後釋出下一個名額",
    "en": " Next slot in about {minutes} minutes."
  },
  "ui.count_files": {
    "zh-Hant": "({count} 檔)",
    "en": "({count} files)"
  },
  "ui.some_files_could_not_be_read_statistics": {
    "zh-Hant": " · 部分項目無法讀取，統計可能不完整",
    "en": " · Some files could not be read; statistics may be incomplete"
  },
  "ui.resume_upcoming_jobs_using_safe_queue_rules": {
    "zh-Hant": "繼續依安全佇列規則啟動後續工作",
    "en": "Resume upcoming jobs using safe queue rules"
  },
  "ui.pause": {
    "zh-Hant": "Pause",
    "en": "Pause"
  },
  "ui.resume": {
    "zh-Hant": "Resume",
    "en": "Resume"
  },
  "ui.queue_ready": {
    "zh-Hant": "Queue Ready · 準備下載",
    "en": "Queue Ready"
  },
  "ui.jobs_waiting_count": {
    "zh-Hant": "還有 {count} 個項目等待處理",
    "en": "Jobs waiting: {count}"
  },
  "ui.safe_queue_waiting": {
    "zh-Hant": "Safe Queue · 安全延時中",
    "en": "Safe Queue · Waiting"
  },
  "ui.next_job_starts_in_about_seconds_s": {
    "zh-Hant": "下一個工作約 {seconds} 秒後開始 · {count} 個項目等待中",
    "en": "Next job starts in about {seconds}s · Queued: {count}"
  },
  "ui.safe_queue_rate_limit_cooldown": {
    "zh-Hant": "Safe Queue · 平台限流冷卻中",
    "en": "Safe Queue · Rate-limit cooldown"
  },
  "ui.about_seconds_s_remaining_queued_jobs_will": {
    "zh-Hant": "剩餘約 {seconds} 秒；冷卻結束後依序處理等待項目",
    "en": "About {seconds}s remaining; queued jobs will resume after cooldown"
  },
  "ui.rate_limit_hourly_limit_reached": {
    "zh-Hant": "Rate Limit · 每小時額度已滿",
    "en": "Rate Limit · Hourly limit reached"
  },
  "ui.used_limit_jobs_started_next_slot_in": {
    "zh-Hant": "已啟動 {used}/{limit} 個工作 · 約 {seconds} 秒後釋出下一個名額",
    "en": "{used}/{limit} jobs started · Next slot in about {seconds}s"
  },
  "ui.queue_paused": {
    "zh-Hant": "Queue Paused · 佇列已暫停",
    "en": "Queue Paused"
  },
  "ui.queued_count": {
    "zh-Hant": "{count} 個等待項目",
    "en": "Queued: {count}"
  },
  "ui.cooldown_about_seconds_s_remaining": {
    "zh-Hant": " · 限流冷卻剩餘約 {seconds} 秒",
    "en": " · Cooldown: about {seconds}s remaining"
  },
  "ui.hourly_limit_reached": {
    "zh-Hant": " · 每小時額度已滿",
    "en": " · Hourly limit reached"
  },
  "ui.press_resume_to_continue": {
    "zh-Hant": " · 按 Resume 恢復",
    "en": " · Press Resume to continue"
  },
  "ui.queue_active": {
    "zh-Hant": "Queue Active · 正在處理",
    "en": "Queue Active"
  },
  "ui.current_job_is_waiting_for_cooldown_about": {
    "zh-Hant": "目前工作等待限流冷卻，剩餘約 {seconds} 秒",
    "en": "Current job is waiting for cooldown: about {seconds}s remaining"
  },
  "ui.downloading_sequentially": {
    "zh-Hant": "逐項下載",
    "en": "Downloading sequentially"
  },
  "ui.upcoming_jobs_paused": {
    "zh-Hant": " · 後續工作已暫停",
    "en": " · Upcoming jobs paused"
  },
  "ui.queued_count_2": {
    "zh-Hant": " · {count} 個項目等待中",
    "en": " · Queued: {count}"
  },
  "ui.downloading_2": {
    "zh-Hant": "正在下載",
    "en": "Downloading"
  },
  "ui.queue_paused_2": {
    "zh-Hant": "佇列已暫停",
    "en": "Queue paused"
  },
  "ui.rate_limit_cooldown": {
    "zh-Hant": "平台限流冷卻中",
    "en": "Rate-limit cooldown"
  },
  "ui.hourly_limit_reached_2": {
    "zh-Hant": "每小時額度已滿",
    "en": "Hourly limit reached"
  },
  "ui.waiting_between_jobs": {
    "zh-Hant": "安全延時中",
    "en": "Waiting between jobs"
  },
  "ui.ready_to_download_2": {
    "zh-Hant": "準備開始下載",
    "en": "Ready to download"
  },
  "ui.starts_in_about_seconds_s": {
    "zh-Hant": " · 約 {seconds} 秒後開始",
    "en": " · Starts in about {seconds}s"
  },
  "ui.completed_count": {
    "zh-Hant": "已完成 {count} 個項目",
    "en": "Completed: {count}"
  },
  "ui.failed_count": {
    "zh-Hant": " · {count} 個失敗",
    "en": " · Failed: {count}"
  },
  "ui.original_size_best_quality_downloads_ready": {
    "zh-Hant": "原尺寸 / 最高畫質下載已就緒",
    "en": "Original-size / best-quality downloads ready"
  },
  "ui.download_engines_need_an_update": {
    "zh-Hant": "需要更新下載引擎",
    "en": "Download engines need an update"
  },
  "ui.image_and_video_engines_ready_original_encoding": {
    "zh-Hant": "圖片與影片引擎已連線 · 保留來源編碼",
    "en": "Image and video engines ready · Original encoding"
  },
  "ui.run_start_bat_again_to_install_dependencies": {
    "zh-Hant": "請重新執行 start.bat 安裝相依套件",
    "en": "Run start.bat again to install dependencies"
  },
  "ui.cannot_connect_to_the_local_service": {
    "zh-Hant": "無法連線到本機服務",
    "en": "Cannot connect to the local service"
  },
  "ui.restart_start_bat_and_refresh_this_page": {
    "zh-Hant": "請重新啟動 start.bat 後重整頁面",
    "en": "Restart start.bat and refresh this page"
  },
  "ui.queue_offline_local_service_unavailable": {
    "zh-Hant": "Queue Offline · 本機服務未連線",
    "en": "Queue Offline · Local service unavailable"
  },
  "ui.restart_the_service_and_refresh_this_page": {
    "zh-Hant": "請重新啟動服務後重新整理",
    "en": "Restart the service and refresh this page"
  },
  "ui.paste_one_or_more_media_urls_first": {
    "zh-Hant": "先貼上一個或多個媒體網址。",
    "en": "Paste one or more media URLs first."
  },
  "ui.adding": {
    "zh-Hant": "正在加入…",
    "en": "Adding…"
  },
  "ui.added_added_invalid_urls_rejected": {
    "zh-Hant": "已加入 {added} 個；{rejected} 個網址格式不符。",
    "en": "Added: {added}. Invalid URLs: {rejected}."
  },
  "ui.download_jobs_added_count": {
    "zh-Hant": "已加入 {count} 個下載項目。",
    "en": "Download jobs added: {count}."
  },
  "ui.items_added_count": {
    "zh-Hant": "已加入 {count} 個項目",
    "en": "Items added: {count}"
  },
  "ui.items_cleared_count": {
    "zh-Hant": "已清除 {count} 個項目",
    "en": "Items cleared: {count}"
  },
  "ui.no_completed_jobs_to_clear": {
    "zh-Hant": "目前沒有已完成項目",
    "en": "No completed jobs to clear"
  },
  "ui.cleared_count_items_the_current_job_will": {
    "zh-Hant": "已清除 {count} 個項目；目前工作完成後會自動移除，檔案保留",
    "en": "Cleared {count} items. The current job will be removed when it finishes; files are kept."
  },
  "ui.cleared_count_items_downloaded_files_are_kept": {
    "zh-Hant": "已清除 {count} 個項目，下載檔案保留",
    "en": "Cleared {count} items. Downloaded files are kept."
  },
  "ui.failed_jobs_queued_again_count": {
    "zh-Hant": "已重新排入 {count} 個失敗項目",
    "en": "Failed jobs queued again: {count}"
  },
  "ui.failed_jobs_queued_again_count_resume_the": {
    "zh-Hant": "已重新排入 {count} 個失敗項目；請按繼續佇列",
    "en": "Failed jobs queued again: {count}; resume the queue to start"
  },
  "ui.resume_the_queue_to_start": {
    "zh-Hant": "；請按繼續佇列",
    "en": "; resume the queue to start"
  },
  "ui.no_failed_jobs_to_retry": {
    "zh-Hant": "目前沒有失敗項目",
    "en": "No failed jobs to retry"
  },
  "ui.choose_a_file_to_open_its_folder": {
    "zh-Hant": "選擇檔案所在資料夾",
    "en": "Choose a file to open its folder"
  },
  "ui.choose_a_file_to_play_or_view_2": {
    "zh-Hant": "選擇要播放／查看的檔案",
    "en": "Choose a file to play or view"
  },
  "ui.open_the_selected_file_s_folder": {
    "zh-Hant": "開啟所選檔案的所在資料夾。",
    "en": "Open the selected file’s folder."
  },
  "ui.videos_images_and_audio_open_in_this": {
    "zh-Hant": "影片、圖片與音訊會使用這台電腦的預設程式開啟。",
    "en": "Videos, images and audio open in this computer’s default apps."
  },
  "ui.x_session_disconnected": {
    "zh-Hant": "已停用 X 登入連接",
    "en": "X session disconnected"
  },
  "ui.saving": {
    "zh-Hant": "正在儲存…",
    "en": "Saving…"
  },
  "ui.settings_saved_the_hourly_limit_is_now": {
    "zh-Hant": "設定已更新，每小時上限立即套用",
    "en": "Settings saved. The hourly limit is now applied."
  },
  "ui.settings_saved": {
    "zh-Hant": "設定已更新",
    "en": "Settings saved"
  },
  "ui.request_failed_status": {
    "zh-Hant": "請求失敗 ({status})",
    "en": "Request failed ({status})"
  },
  "ui.service_restarted_waiting_to_retry": {
    "zh-Hant": "服務重啟，等待重試",
    "en": "Service restarted; waiting to retry"
  },
  "ui.waiting_to_download_again": {
    "zh-Hant": "等待重新下載",
    "en": "Waiting to download again"
  },
  "ui.connecting": {
    "zh-Hant": "正在連線",
    "en": "Connecting"
  },
  "ui.discovering_media_on_the_webpage": {
    "zh-Hant": "正在使用通用網頁解析",
    "en": "Discovering media on the webpage"
  },
  "ui.reading_the_embedded_player": {
    "zh-Hant": "正在解析嵌入播放器",
    "en": "Reading the embedded player"
  },
  "ui.downloading_discovered_media": {
    "zh-Hant": "正在下載通用解析找到的媒體",
    "en": "Downloading discovered media"
  },
  "ui.merging_audio_and_video_original_encoding": {
    "zh-Hant": "合併影音中（保留編碼）",
    "en": "Merging audio and video (original encoding)"
  },
  "ui.downloading_original_size_media": {
    "zh-Hant": "下載原尺寸媒體",
    "en": "Downloading original-size media"
  },
  "ui.media_files_saved": {
    "zh-Hant": "媒體檔案已儲存",
    "en": "Media files saved"
  },
  "ui.reading_public_x_post": {
    "zh-Hant": "讀取 X 公開貼文",
    "en": "Reading public X post"
  },
  "ui.download_failed": {
    "zh-Hant": "下載失敗",
    "en": "Download failed"
  },
  "ui.some_files_failed_to_download": {
    "zh-Hant": "部分下載失敗",
    "en": "Some files failed to download"
  },
  "ui.downloading_source_image": {
    "zh-Hant": "正在下載圖片來源檔",
    "en": "Downloading source image"
  },
  "ui.x_original_size_image_orig": {
    "zh-Hant": "X 原尺寸圖片（orig）",
    "en": "X original-size image (orig)"
  },
  "ui.direct_image_original_format_and_content": {
    "zh-Hant": "圖片直連原格式 · 保留來源內容",
    "en": "Direct image · Original format and content"
  },
  "ui.best_available_quality_original_encoding": {
    "zh-Hant": "最高可用畫質 · 保留影音編碼",
    "en": "Best available quality · Original encoding"
  },
  "ui.video_quality": {
    "zh-Hant": "影片畫質",
    "en": "Video quality"
  },
  "ui.best_quality_default": {
    "zh-Hant": "最高畫質（預設）",
    "en": "Best quality (default)"
  },
  "ui.automatically_choose_the_best_available_quality_images": {
    "zh-Hant": "自動選擇最高可用畫質；圖片保留原尺寸。",
    "en": "Automatically choose the best available quality; images keep their original dimensions."
  },
  "ui.choose_the_best_version_at_or_below": {
    "zh-Hant": "選擇最高且不超過上限的版本；圖片保留原尺寸。",
    "en": "Choose the best version at or below the selected limit; images keep their original dimensions."
  },
  "ui.quality_limit_height_p": {
    "zh-Hant": "畫質上限 {height}p",
    "en": "Quality limit: {height}p"
  },
  "ui.original_size_images_original_encoding": {
    "zh-Hant": "原尺寸圖片 · 保留來源編碼",
    "en": "Original-size images · Original encoding"
  },
  "ui.original_size_images_video_limit_height_p": {
    "zh-Hant": "原尺寸圖片 / 影片上限 {height}p · 保留原格式",
    "en": "Original-size images / video limit: {height}p · Original format"
  },
  "ui.invalid_video_quality_setting": {
    "zh-Hant": "影片畫質設定不正確",
    "en": "Invalid video quality setting"
  },
  "ui.no_video_meets_the_selected_quality_limit": {
    "zh-Hant": "平台未提供符合畫質上限的影片，或沒有回報解析度；請改選最高畫質。",
    "en": "No video meets the selected quality limit, or its resolution was not reported. Choose Best quality."
  },
  "ui.x_account_media_currently_uses_the_best": {
    "zh-Hant": "X 帳號媒體目前使用最高畫質。",
    "en": "X account media currently uses the best quality."
  },
  "ui.resolution_not_reported_original_encoding": {
    "zh-Hant": "解析度未回報 · 保留影音編碼",
    "en": "Resolution not reported · Original encoding"
  },
  "ui.multiple_resolutions_original_encoding": {
    "zh-Hant": "多個解析度 · 保留影音編碼",
    "en": "Multiple resolutions · Original encoding"
  },
  "ui.resolution_original_encoding": {
    "zh-Hant": "{resolution} · 保留影音編碼",
    "en": "{resolution} · Original encoding"
  },
  "ui.best_version_available_from_the_platform_original": {
    "zh-Hant": "平台提供的最高可用版本 · 保留原格式",
    "en": "Best version available from the platform · Original format"
  },
  "ui.x_images_orig_videos_highest_bitrate_original": {
    "zh-Hant": "X 圖片 orig / 影片最高位元率 · 保留原格式",
    "en": "X images: orig / videos: highest bitrate · Original format"
  },
  "ui.using_public_x_embed_data_only_media": {
    "zh-Hant": "使用 X 公開嵌入資料；僅能保存此端點提供的媒體，登入後可能有更多內容。",
    "en": "Using public X embed data. Only media exposed by this endpoint can be saved; signing in may provide more content."
  },
  "ui.download_failed_please_retry": {
    "zh-Hant": "下載失敗，請重試。",
    "en": "Download failed. Please retry."
  },
  "ui.the_engine_does_not_support_this_url": {
    "zh-Hant": "下載引擎不支援此網址；可按重新下載嘗試通用網頁解析。",
    "en": "The engine does not support this URL. Retry to try generic webpage discovery."
  },
  "ui.no_downloadable_source_was_found_the_page": {
    "zh-Hant": "通用解析未找到可下載的媒體來源；頁面可能需要動態播放或登入。",
    "en": "No downloadable source was found. The page may require dynamic playback or sign-in."
  },
  "ui.media_sources_were_found_but_could_not": {
    "zh-Hant": "已找到媒體來源，但目前無法下載。請查看詳細原因。",
    "en": "Media sources were found but could not be downloaded. See the failure details."
  },
  "ui.the_media_source_url_is_invalid_or": {
    "zh-Hant": "網頁媒體來源網址無效或不是公開網址。",
    "en": "The media source URL is invalid or is not public."
  },
  "ui.the_page_exceeds_the_discovery_size_limit": {
    "zh-Hant": "網頁內容過大，通用解析已停止；請改貼播放器或媒體網址。",
    "en": "The page exceeds the discovery size limit. Paste the player or media URL."
  },
  "ui.webpage_discovery_timed_out_paste_the_player": {
    "zh-Hant": "通用網頁解析已逾時；請改貼播放器或媒體網址。",
    "en": "Webpage discovery timed out. Paste the player or media URL."
  },
  "ui.the_player_data_returned_by_the_page": {
    "zh-Hant": "網頁回傳的播放器資料無法解析。",
    "en": "The player data returned by the page could not be parsed."
  },
  "ui.x_guest_authentication_did_not_return_guest": {
    "zh-Hant": "X 訪客驗證未回傳 guest_token。請按「連接 Chrome 登入」，完成登入後重試。",
    "en": "X guest authentication did not return guest_token. Connect your Chrome X session and retry."
  },
  "ui.the_platform_has_rate_limited_requests_the": {
    "zh-Hant": "平台限制請求次數，安全佇列已進入冷卻；請稍後再按重新下載。",
    "en": "The platform has rate-limited requests. The queue is cooling down; retry later."
  },
  "ui.sign_in_is_required_or_the_session": {
    "zh-Hant": "平台要求登入或登入已失效；X 連結可按「連接 Chrome 登入」後重試。",
    "en": "Sign-in is required or the session has expired. For X, connect Chrome and retry."
  },
  "ui.the_platform_denied_access_check_your_access": {
    "zh-Hant": "平台拒絕存取。請確認內容權限；X 連結可按「連接 Chrome 登入」後重試。",
    "en": "The platform denied access. Check your access permissions; for X, connect Chrome and retry."
  },
  "ui.content_was_not_found_check_the_url": {
    "zh-Hant": "平台找不到這則內容。請確認網址與貼文是否仍存在。",
    "en": "Content was not found. Check the URL and whether the post still exists."
  },
  "ui.connection_failed_or_timed_out_check_your": {
    "zh-Hant": "網路連線失敗或逾時，請確認連線後重試。",
    "en": "Connection failed or timed out. Check your network and retry."
  },
  "ui.no_downloadable_media_was_provided_sign_in": {
    "zh-Hant": "平台無法提供可下載媒體；可能需要登入或內容已失效。",
    "en": "No downloadable media was provided. Sign-in may be required or the content may be unavailable."
  },
  "ui.the_x_cookie_file_is_missing_or": {
    "zh-Hant": "X Cookie 檔案不存在或過大。請選擇 Netscape 格式的 cookies.txt。",
    "en": "The X cookie file is missing or too large. Choose a Netscape-format cookies.txt file."
  },
  "ui.cannot_read_x_cookies_use_a_netscape": {
    "zh-Hant": "無法讀取 X Cookie；請使用 Netscape 格式的 cookies.txt。",
    "en": "Cannot read X cookies. Use a Netscape-format cookies.txt file."
  },
  "ui.the_cookie_file_has_no_valid_x": {
    "zh-Hant": "Cookie 檔案沒有有效的 X 登入 auth_token。請登入 X 後重新匯出。",
    "en": "The cookie file has no valid X auth_token. Sign in to X and export it again."
  },
  "ui.saved_x_session_loaded": {
    "zh-Hant": "已載入本機保存的 X 登入狀態",
    "en": "Saved X session loaded"
  },
  "ui.the_saved_x_session_is_unavailable_please": {
    "zh-Hant": "保存的 X 登入狀態無法使用，請重新連接。",
    "en": "The saved X session is unavailable. Please reconnect."
  },
  "ui.chrome_connection_timed_out_press_connect_again": {
    "zh-Hant": "Chrome 連接已逾時，請再次按連接按鈕。",
    "en": "Chrome connection timed out. Press Connect again."
  },
  "ui.your_x_session_expired_please_reconnect": {
    "zh-Hant": "X 登入已到期，請重新連接。",
    "en": "Your X session expired. Please reconnect."
  },
  "ui.connecting_your_x_session_from_chrome": {
    "zh-Hant": "正在連接 Chrome 的 X 登入狀態…",
    "en": "Connecting your X session from Chrome…"
  },
  "ui.use_the_x_connector_in_regular_chrome": {
    "zh-Hant": "請在一般 Chrome 中使用 X 連接器，連接已登入的 X。首次需載入連接器，設定頁有安裝步驟。",
    "en": "Use the X connector in regular Chrome to connect your signed-in session. First-time setup instructions are available in Settings."
  },
  "ui.x_session_connected_from_chrome_failed_x": {
    "zh-Hant": "Chrome 的 X 登入狀態已連接；失敗的 X 項目將自動重試。",
    "en": "X session connected from Chrome. Failed X jobs will be retried automatically."
  },
  "ui.cannot_connect_chrome_use_the_chrome_connector": {
    "zh-Hant": "無法連接 Chrome，請使用 Chrome 連接器或進階 Cookie 檔案設定。",
    "en": "Cannot connect Chrome. Use the Chrome connector or the advanced cookie file option."
  },
  "ui.origin_not_allowed": {
    "zh-Hant": "不允許的來源",
    "en": "Origin not allowed"
  },
  "ui.file_path_not_allowed": {
    "zh-Hant": "不允許的檔案路徑",
    "en": "File path not allowed"
  },
  "ui.page_not_found": {
    "zh-Hant": "找不到頁面",
    "en": "Page not found"
  },
  "ui.file_not_found": {
    "zh-Hant": "找不到檔案",
    "en": "File not found"
  },
  "ui.only_local_requests_are_allowed": {
    "zh-Hant": "僅允許本機操作",
    "en": "Only local requests are allowed"
  },
  "ui.use_the_chrome_connector_for_this_action": {
    "zh-Hant": "請透過 Chrome 連接器操作",
    "en": "Use the Chrome connector for this action"
  },
  "ui.x_connected_failed_x_jobs_will_be_2": {
    "zh-Hant": "X 登入已連接，失敗項目將自動重試。",
    "en": "X connected. Failed X jobs will be retried automatically."
  },
  "ui.paste_at_least_one_url_first": {
    "zh-Hant": "請先貼上至少一個網址",
    "en": "Paste at least one URL first"
  },
  "ui.maximum_urls_per_batch_count": {
    "zh-Hant": "一次最多加入 {count} 個網址",
    "en": "Maximum URLs per batch: {count}"
  },
  "ui.invalid_url_format": {
    "zh-Hant": "網址格式不正確",
    "en": "Invalid URL format"
  },
  "ui.the_queue_holds_up_to_count_jobs": {
    "zh-Hant": "佇列最多保留 {count} 個項目，請先清除已完成項目",
    "en": "The queue holds up to {count} jobs. Clear completed jobs first."
  },
  "ui.opening_folders_is_supported_on_windows_only": {
    "zh-Hant": "目前僅支援在 Windows 開啟資料夾",
    "en": "Opening folders is supported on Windows only"
  },
  "ui.cannot_open_the_download_folder_detail": {
    "zh-Hant": "無法開啟下載資料夾：{detail}",
    "en": "Cannot open the download folder: {detail}"
  },
  "ui.enter_a_valid_download_folder_path": {
    "zh-Hant": "請輸入有效的下載資料夾路徑",
    "en": "Enter a valid download folder path"
  },
  "ui.enter_a_whole_number_from_1_to": {
    "zh-Hant": "每小時工作上限請輸入 1～1000 的整數",
    "en": "Enter a whole number from 1 to 1000 for the hourly limit"
  },
  "ui.invalid_x_cookie_file_path": {
    "zh-Hant": "X Cookie 路徑格式不正確",
    "en": "Invalid X cookie file path"
  },
  "ui.cannot_use_this_folder_detail": {
    "zh-Hant": "無法使用此資料夾：{detail}",
    "en": "Cannot use this folder: {detail}"
  },
  "ui.container_download_folder_boundary": {
    "zh-Hant": "下載位置必須位於容器的 /downloads 持久化資料夾內。",
    "en": "The download location must be inside the container's persistent /downloads folder."
  },
  "ui.download_job_not_found": {
    "zh-Hant": "找不到這個下載項目",
    "en": "Download job not found"
  },
  "ui.no_saved_file_is_available_or_the": {
    "zh-Hant": "此項目尚無檔案，或選擇的檔案已更新",
    "en": "No saved file is available, or the selected file has changed"
  },
  "ui.the_file_list_changed_select_the_file": {
    "zh-Hant": "檔案清單已更新，請重新選擇要開啟的檔案",
    "en": "The file list changed. Select the file again."
  },
  "ui.the_file_is_outside_this_job_s": {
    "zh-Hant": "檔案路徑不在此項目的下載資料夾內",
    "en": "The file is outside this job’s download folder"
  },
  "ui.file_not_found_it_may_have_been": {
    "zh-Hant": "找不到檔案，可能已被移動或刪除",
    "en": "File not found. It may have been moved or deleted."
  },
  "ui.opening_files_and_folders_is_supported_on": {
    "zh-Hant": "目前僅支援在 Windows 開啟檔案與資料夾",
    "en": "Opening files and folders is supported on Windows only"
  },
  "ui.this_image_video_or_audio_format_is": {
    "zh-Hant": "此檔案不是支援的圖片、影片或音訊格式",
    "en": "This image, video or audio format is not supported"
  },
  "ui.cannot_open_the_file_or_folder_check": {
    "zh-Hant": "無法開啟檔案或資料夾，請確認檔案存在且已設定預設開啟程式",
    "en": "Cannot open the file or folder. Check that it exists and has a default app."
  },
  "ui.job_not_found": {
    "zh-Hant": "找不到這個項目",
    "en": "Job not found"
  },
  "ui.this_job_is_already_queued_or_downloading": {
    "zh-Hant": "此項目已在佇列或下載中，請等處理完成",
    "en": "This job is already queued or downloading. Wait for it to finish."
  },
  "ui.download_in_progress_wait_for_it_to": {
    "zh-Hant": "下載進行中，完成後才能移除此項目",
    "en": "Download in progress. Wait for it to finish before removing it."
  },
  "ui.api_endpoint_not_found": {
    "zh-Hant": "找不到 API",
    "en": "API endpoint not found"
  },
  "ui.the_url_is_too_long": {
    "zh-Hant": "網址過長",
    "en": "The URL is too long"
  },
  "ui.enter_a_url_beginning_with_http_or": {
    "zh-Hant": "請輸入以 http:// 或 https:// 開頭的網址",
    "en": "Enter a URL beginning with http:// or https://"
  },
  "ui.urls_must_not_contain_a_username_or": {
    "zh-Hant": "網址不可包含帳號或密碼",
    "en": "URLs must not contain a username or password"
  },
  "ui.local_urls_are_not_accepted": {
    "zh-Hant": "不接受本機網址",
    "en": "Local URLs are not accepted"
  },
  "ui.private_or_non_public_ip_addresses_are": {
    "zh-Hant": "不接受內部或非公開 IP 位址",
    "en": "Private or non-public IP addresses are not accepted"
  },
  "ui.invalid_request_body_size": {
    "zh-Hant": "請求內容大小不正確",
    "en": "Invalid request body size"
  },
  "ui.invalid_request_format": {
    "zh-Hant": "請求格式不正確",
    "en": "Invalid request format"
  },
  "ui.the_specified_path_is_not_a_folder": {
    "zh-Hant": "指定路徑不是資料夾",
    "en": "The specified path is not a folder"
  },
  "ui.chrome_x_connection_smart_social_downloader": {
    "zh-Hant": "Chrome X 登入連接 · Smart Social Downloader",
    "en": "Chrome X Connection · Smart Social Downloader"
  },
  "ui.connect_your_x_session_from_chrome_2": {
    "zh-Hant": "連接 Chrome 中的 X 登入",
    "en": "Connect your X session from Chrome"
  },
  "ui.sign_in_to_x_in_your_regular": {
    "zh-Hant": "在平常使用的 Chrome 登入 X，再將登入狀態連接到本機下載工具。Google 或 Apple 登入也請在一般 Chrome 完成。",
    "en": "Sign in to X in your regular Chrome profile, then connect the session to this local downloader. Complete Google or Apple sign-in in regular Chrome as well."
  },
  "ui.detecting_the_chrome_connector": {
    "zh-Hant": "正在偵測 Chrome 連接器…",
    "en": "Detecting the Chrome connector…"
  },
  "ui.already_signed_in_to_x_connect_now": {
    "zh-Hant": "已登入 X？直接連接",
    "en": "Already signed in to X? Connect now"
  },
  "ui.only_x_session_cookies_from_this_chrome": {
    "zh-Hant": "只讀取這個 Chrome 個人檔案的 X 登入 Cookie；連接成功後會自動重試失敗的 X 項目。",
    "en": "Only X session cookies from this Chrome profile are read. Failed X jobs are retried automatically after connection."
  },
  "ui.connect_signed_in_x_session": {
    "zh-Hant": "連接已登入的 X",
    "en": "Connect signed-in X session"
  },
  "ui.open_x_in_regular_chrome_2": {
    "zh-Hant": "在一般 Chrome 開啟 X ↗",
    "en": "Open X in regular Chrome ↗"
  },
  "ui.session_data_is_sent_only_to_the": {
    "zh-Hant": "登入狀態僅傳送至這台電腦的下載工具並以 Windows 加密保存；不讀取帳號密碼，也不讀取 Google 或 Apple 的 Cookie。",
    "en": "Session data is sent only to the downloader on this computer and saved using Windows encryption. Passwords and Google or Apple cookies are not read."
  },
  "ui.first_time_setup_only_once": {
    "zh-Hant": "首次設定 · 只需一次",
    "en": "First-time setup · Only once"
  },
  "ui.load_the_local_chrome_connector": {
    "zh-Hant": "載入 Chrome 本機連接器",
    "en": "Load the local Chrome connector"
  },
  "ui.open_the_extensions_page": {
    "zh-Hant": "開啟擴充功能管理頁",
    "en": "Open the extensions page"
  },
  "ui.use_the_chrome_profile_where_you_normally": {
    "zh-Hant": "請使用你平常登入 X 的 Chrome 個人檔案。",
    "en": "Use the Chrome profile where you normally sign in to X."
  },
  "ui.open_chrome_extensions": {
    "zh-Hant": "開啟 Chrome 擴充功能頁",
    "en": "Open Chrome extensions"
  },
  "ui.enable_developer_mode_in_the_top_right": {
    "zh-Hant": "開啟右上角「開發人員模式」",
    "en": "Enable “Developer mode” in the top-right corner"
  },
  "ui.click_load_unpacked_and_select_this_folder": {
    "zh-Hant": "按「載入未封裝項目」，選擇這個資料夾",
    "en": "Click “Load unpacked” and select this folder"
  },
  "ui.chrome_connector_folder_path": {
    "zh-Hant": "Chrome 連接器資料夾路徑",
    "en": "Chrome connector folder path"
  },
  "ui.copy_path": {
    "zh-Hant": "複製路徑",
    "en": "Copy path"
  },
  "ui.select_the_entire_folder_containing_manifest_json": {
    "zh-Hant": "選擇包含 manifest.json 的整個資料夾。連接器名稱為「Smart Social Downloader · X 連接器」。",
    "en": "Select the entire folder containing manifest.json. The connector is named “Smart Social Downloader · X 連接器”."
  },
  "ui.return_to_this_page_and_refresh": {
    "zh-Hant": "回到此頁並重新整理",
    "en": "Return to this page and refresh"
  },
  "ui.if_you_are_signed_in_to_x": {
    "zh-Hant": "已登入 X 時會自動連接；也可以按上方「連接已登入的 X」。",
    "en": "If you are signed in to X, it connects automatically. You can also click “Connect signed-in X session” above."
  },
  "ui.loaded_refresh_page": {
    "zh-Hant": "已載入，重新整理",
    "en": "Loaded — refresh page"
  },
  "ui.this_is_chrome_s_supported_method_for": {
    "zh-Hant": "這是 Chrome 官方支援的本機擴充功能載入方式。",
    "en": "This is Chrome’s supported method for loading local extensions."
  },
  "ui.view_official_instructions": {
    "zh-Hant": "查看官方步驟 ↗",
    "en": "View official instructions ↗"
  },
  "ui.if_x_temporarily_restricts_sign_in": {
    "zh-Hant": "X 顯示「暫時限制登入」時",
    "en": "If X temporarily restricts sign-in"
  },
  "ui.stop_repeated_sign_in_attempts_x_says": {
    "zh-Hant": "先停止反覆登入。X 官方說明，多次登入失敗造成的暫時鎖定通常約一小時後解除；請先確認能在一般 Chrome 正常登入，再使用連接器。此工具不能解除帳號限制。",
    "en": "Stop repeated sign-in attempts. X says temporary lockouts after repeated failures usually end after about an hour. Confirm you can sign in using regular Chrome before connecting. This tool cannot remove account restrictions."
  },
  "ui.x_troubleshooting_instructions": {
    "zh-Hant": "X 官方處理說明 ↗",
    "en": "X troubleshooting instructions ↗"
  },
  "ui.chrome_connector_ready": {
    "zh-Hant": "Chrome 連接器已就緒",
    "en": "Chrome connector ready"
  },
  "ui.sync_x_session_again": {
    "zh-Hant": "重新同步 X 登入",
    "en": "Sync X session again"
  },
  "ui.enter_chrome_extensions_in_chrome_s_address": {
    "zh-Hant": "請在 Chrome 網址列輸入 chrome://extensions。",
    "en": "Enter chrome://extensions in Chrome’s address bar."
  },
  "ui.path_copied_paste_it_into_the_folder": {
    "zh-Hant": "路徑已複製，請貼到選擇資料夾視窗。",
    "en": "Path copied. Paste it into the folder picker."
  },
  "ui.press_ctrl_c_to_copy_the_selected": {
    "zh-Hant": "請按 Ctrl+C 複製已選取的路徑。",
    "en": "Press Ctrl+C to copy the selected path."
  },
  "ui.cannot_connect_to_the_local_tool_make": {
    "zh-Hant": "無法連線到本機工具，請確認 start.bat 已啟動。",
    "en": "Cannot connect to the local tool. Make sure start.bat is running."
  },
  "ui.first_time_setup_load_the_chrome_connector": {
    "zh-Hant": "首次使用：請先載入下方的 Chrome 連接器",
    "en": "First-time setup: load the Chrome connector below"
  },
  "ui.connecting_the_x_session_from_this_chrome": {
    "zh-Hant": "正在連接這個 Chrome 個人檔案的 X 登入狀態…",
    "en": "Connecting the X session from this Chrome profile…"
  },
  "ui.the_chrome_connector_was_updated_refresh_this": {
    "zh-Hant": "Chrome 連接器已更新，請重新整理這個頁面。",
    "en": "The Chrome connector was updated. Refresh this page."
  },
  "ui.waiting_for_the_safe_request_interval": {
    "zh-Hant": "安全請求間隔等待中",
    "en": "Waiting for the safe request interval"
  },
  "ui.rate_limit_cooldown_wait_seconds_s": {
    "zh-Hant": "限流冷卻，等待 {seconds} 秒",
    "en": "Rate-limit cooldown: wait {seconds}s"
  },
  "ui.this_url_did_not_return_an_image": {
    "zh-Hant": "此網址未回傳圖片檔，請貼上圖片或貼文的完整網址。",
    "en": "This URL did not return an image. Paste the full image or post URL."
  },
  "ui.the_image_download_is_incomplete_please_retry": {
    "zh-Hant": "圖片下載不完整，請重試。",
    "en": "The image download is incomplete. Please retry."
  },
  "ui.ffmpeg_is_required_to_save_the_best": {
    "zh-Hant": "需要安裝 FFmpeg 才能保存最高畫質影音。請重新執行 start.bat 更新下載引擎。",
    "en": "FFmpeg is required to save the best-quality video and audio. Run start.bat again to update the engines."
  },
  "ui.the_video_download_engine_is_not_installed": {
    "zh-Hant": "尚未安裝影片下載引擎，請執行 start.bat。",
    "en": "The video download engine is not installed. Run start.bat."
  },
  "ui.no_video_file_was_saved": {
    "zh-Hant": "沒有取得可保存的影片檔案。",
    "en": "No video file was saved."
  },
  "ui.no_media_is_available_in_this_post": {
    "zh-Hant": "貼文內沒有可取得的媒體檔案，或平台要求登入。",
    "en": "No media is available in this post, or sign-in is required."
  },
  "ui.x_did_not_expose_this_post_to": {
    "zh-Hant": "X 未向訪客提供這則貼文。可能需要登入，或內容已失效；可按「連接 Chrome 登入」後重試。",
    "en": "X did not expose this post to guests. Sign-in may be required or the content may be unavailable. Connect Chrome and retry."
  },
  "ui.x_returned_a_different_post_id_please": {
    "zh-Hant": "X 回傳的貼文編號不符，請重試。",
    "en": "X returned a different post ID. Please retry."
  },
  "ui.public_x_data_has_no_media_connect": {
    "zh-Hant": "X 公開資料未提供媒體。請按「連接 Chrome 登入」後重試。",
    "en": "Public X data has no media. Connect Chrome and retry."
  },
  "ui.x_did_not_provide_an_original_size": {
    "zh-Hant": "X 未提供原尺寸圖片網址。",
    "en": "X did not provide an original-size image URL."
  },
  "ui.x_did_not_provide_a_downloadable_video": {
    "zh-Hant": "X 未提供可保存的影片來源版本。請按「連接 Chrome 登入」後重試。",
    "en": "X did not provide a downloadable video source. Connect Chrome and retry."
  },
  "ui.the_x_video_source_domain_is_invalid": {
    "zh-Hant": "X 影片來源網域不符。",
    "en": "The X video source domain is invalid."
  },
  "ui.x_returned_an_unsupported_media_type_connect": {
    "zh-Hant": "X 回傳了尚未支援的媒體類型，請連接 Chrome 登入後重試。",
    "en": "X returned an unsupported media type. Connect Chrome and retry."
  },
  "ui.run_start_bat_again_to_install_the": {
    "zh-Hant": "請重新執行 start.bat 安裝 X 下載引擎。",
    "en": "Run start.bat again to install the X download engine."
  },
  "ui.the_public_x_endpoint_returned_http_status": {
    "zh-Hant": "X 公開資料端點回傳 HTTP {status}，請稍後重試或設定登入 Cookie。",
    "en": "The public X endpoint returned HTTP {status}. Retry later or connect an X session."
  },
  "ui.x_returned_invalid_public_data_retry_later": {
    "zh-Hant": "X 回傳的公開資料格式不正確，請稍後重試。",
    "en": "X returned invalid public data. Retry later."
  },
  "ui.x_returned_invalid_public_data": {
    "zh-Hant": "X 回傳的公開資料格式不正確。",
    "en": "X returned invalid public data."
  },
  "ui.some_x_media_could_not_be_saved": {
    "zh-Hant": "部分 X 媒體未能儲存，請重試。",
    "en": "Some X media could not be saved. Please retry."
  },
  "ui.x_profile_pages_and_other_non_post": {
    "zh-Hant": "X 帳號頁或非貼文連結需要登入；請按「連接 Chrome 登入」，或改貼單篇貼文網址。",
    "en": "X profile pages and other non-post links require sign-in. Connect Chrome or paste a single post URL."
  },
  "ui.x_post_media_requires_the_image_download": {
    "zh-Hant": "X 貼文的圖片與影片需要圖片下載引擎，請重新執行 start.bat。",
    "en": "X post media requires the image download engine. Run start.bat again."
  },
  "ui.automatic_chrome_session_connection_is_supported_on": {
    "zh-Hant": "Chrome 自動登入目前支援 Windows。",
    "en": "Automatic Chrome session connection is supported on Windows only."
  },
  "ui.windows_could_not_save_or_read_the": {
    "zh-Hant": "Windows 無法保存或讀取登入狀態，請重新連接。",
    "en": "Windows could not save or read the session. Please reconnect."
  },
  "ui.windows_session_encryption_is_unavailable_error_code": {
    "zh-Hant": "Windows 無法使用登入資料加密（錯誤 {code}）。請關閉目前服務，從一般 Windows 桌面執行 start.bat，再重新連接 X。",
    "en": "Windows session encryption is unavailable (error {code}). Close the current service, run start.bat from your normal Windows desktop, then reconnect X."
  },
  "ui.could_not_save_the_x_session_make": {
    "zh-Hant": "無法保存 X 登入狀態，請確認 data 資料夾可寫入，再重新連接。",
    "en": "Could not save the X session. Make sure the data folder is writable, then reconnect."
  },
  "ui.google_chrome_was_not_found_install_chrome": {
    "zh-Hant": "找不到 Google Chrome，請先安裝 Chrome，或使用進階 Cookie 檔案設定。",
    "en": "Google Chrome was not found. Install Chrome or use the advanced cookie file option."
  },
  "ui.the_saved_session_could_not_be_removed": {
    "zh-Hant": "無法移除保存的登入狀態，請稍後重試。",
    "en": "The saved session could not be removed. Retry later."
  },
  "ui.google_chrome_was_not_found_install_chrome_2": {
    "zh-Hant": "找不到 Google Chrome，請先安裝 Chrome。",
    "en": "Google Chrome was not found. Install Chrome first."
  },
  "ui.connection_cancelled": {
    "zh-Hant": "連接已取消。",
    "en": "Connection cancelled."
  },
  "ui.this_connection_ticket_expired_or_was_already": {
    "zh-Hant": "此連接已到期或已使用，請在工具頁重新按「連接 Chrome 登入」。",
    "en": "This connection ticket expired or was already used. Press Connect Chrome again in the downloader."
  },
  "ui.invalid_x_session_data": {
    "zh-Hant": "X 登入資料格式不正確。",
    "en": "Invalid X session data."
  },
  "ui.this_chrome_profile_is_not_signed_in": {
    "zh-Hant": "此 Chrome 尚未登入 X。請在一般 Chrome 確認 X 已登入，再連接。",
    "en": "This Chrome profile is not signed in to X. Sign in using regular Chrome, then connect."
  },
  "ui.connection_cancelled_please_reconnect": {
    "zh-Hant": "連接已取消，請重新連接。",
    "en": "Connection cancelled. Please reconnect."
  },
  "ui.the_local_tool_rejected_the_connection_press": {
    "zh-Hant": "本機工具拒絕連接，請重新按連接按鈕。",
    "en": "The local tool rejected the connection. Press Connect again."
  },
  "ui.this_chrome_profile_is_not_signed_in_2": {
    "zh-Hant": "這個 Chrome 個人檔案尚未登入 X。請先在一般 Chrome 登入；若 X 顯示暫時限制，先停止登入嘗試並等待解除。",
    "en": "This Chrome profile is not signed in to X. Sign in using regular Chrome first. If X temporarily restricts sign-in, stop repeated attempts and wait."
  },
  "ui.this_connection_expired_press_connect_chrome_again": {
    "zh-Hant": "此連接已到期，請從下載工具重新按連接 Chrome。",
    "en": "This connection expired. Press Connect Chrome again in the downloader."
  },
  "ui.cannot_reach_the_local_tool_start_smart": {
    "zh-Hant": "無法連線到本機工具，請先啟動 Smart Social Downloader。",
    "en": "Cannot reach the local tool. Start Smart Social Downloader first."
  },
  "ui.cannot_connect_the_x_session_please_reconnect": {
    "zh-Hant": "無法連接 X 登入狀態，請重新連接。",
    "en": "Cannot connect the X session. Please reconnect."
  },
  "ui.the_local_service_returned_a_non_json": {
    "zh-Hant": "本機服務回傳了非 JSON 回應，請更新狀態或重新啟動服務。",
    "en": "The local service returned a non-JSON response. Refresh status or restart the service."
  },
  "ui.the_local_service_returned_invalid_json_the": {
    "zh-Hant": "本機服務回傳的 JSON 無法解析，已保留上次成功資料。",
    "en": "The local service returned invalid JSON. The last successful data has been retained."
  },
  "ui.the_local_service_returned_an_unexpected_format": {
    "zh-Hant": "本機服務回應格式不正確，已保留上次成功資料。",
    "en": "The local service returned an unexpected format. The last successful data has been retained."
  },
  "ui.the_local_service_timed_out_check_that": {
    "zh-Hant": "本機服務回應逾時，請確認服務仍在執行。",
    "en": "The local service timed out. Check that it is still running."
  },
  "ui.request_cancelled": {
    "zh-Hant": "請求已取消。",
    "en": "Request cancelled."
  },
  "ui.cannot_reach_the_local_service_make_sure": {
    "zh-Hant": "無法連線到本機服務，請確認 start.bat 已啟動。",
    "en": "Cannot reach the local service. Make sure start.bat is running."
  },
  "ui.the_result_is_unconfirmed_refresh_status_before": {
    "zh-Hant": "操作結果尚未確認，請先更新狀態，避免重複操作。",
    "en": "The result is unconfirmed. Refresh status before repeating the action."
  },
  "ui.detail_the_result_is_unconfirmed_refresh_status": {
    "zh-Hant": "{detail} 操作結果尚未確認，請先更新狀態，避免重複操作。",
    "en": "{detail} The result is unconfirmed. Refresh status before repeating the action."
  },
  "ui.status_update_failed": {
    "zh-Hant": "狀態更新失敗",
    "en": "Status update failed"
  },
  "ui.last_successful_data_time_retained_status_updates": {
    "zh-Hant": "已保留上次成功資料（{time}），將自動重試更新。",
    "en": "Last successful data ({time}) retained. Status updates will retry automatically."
  },
  "ui.no_valid_status_has_been_received_yet": {
    "zh-Hant": "尚未取得有效狀態，將自動重試更新。",
    "en": "No valid status has been received yet. Status updates will retry automatically."
  },
  "ui.engines_need_repair": {
    "zh-Hant": "引擎待修復",
    "en": "Engines need repair"
  },
  "ui.environment_needs_attention": {
    "zh-Hant": "環境需要注意",
    "en": "Environment needs attention"
  },
  "ui.open_environment_diagnostics_in_settings_for_repair": {
    "zh-Hant": "請開啟設定中的環境診斷查看處理建議。",
    "en": "Open Environment diagnostics in Settings for repair guidance."
  },
  "ui.environment_diagnostics": {
    "zh-Hant": "環境診斷",
    "en": "Environment diagnostics"
  },
  "ui.recheck": {
    "zh-Hant": "重新檢查",
    "en": "Recheck"
  },
  "ui.checking": {
    "zh-Hant": "檢查中…",
    "en": "Checking…"
  },
  "ui.loading_environment_diagnostics": {
    "zh-Hant": "正在取得環境診斷…",
    "en": "Loading environment diagnostics…"
  },
  "ui.checking_the_local_environment": {
    "zh-Hant": "正在檢查本機環境…",
    "en": "Checking the local environment…"
  },
  "ui.environment_diagnostics_have_not_run_yet": {
    "zh-Hant": "尚未執行環境診斷。",
    "en": "Environment diagnostics have not run yet."
  },
  "ui.environment_ready": {
    "zh-Hant": "環境已就緒。",
    "en": "Environment ready."
  },
  "ui.environment_errors_checks_need_repair_warnings_need": {
    "zh-Hant": "環境診斷：{errors} 項需修復、{warnings} 項需要注意。",
    "en": "Environment: {errors} checks need repair, {warnings} need attention."
  },
  "ui.ok": {
    "zh-Hant": "正常",
    "en": "OK"
  },
  "ui.attention": {
    "zh-Hant": "注意",
    "en": "Attention"
  },
  "ui.needs_repair": {
    "zh-Hant": "需修復",
    "en": "Needs repair"
  },
  "ui.javascript_runtime": {
    "zh-Hant": "JavaScript 執行環境",
    "en": "JavaScript runtime"
  },
  "ui.package_dependencies": {
    "zh-Hant": "套件相依性",
    "en": "Package dependencies"
  },
  "ui.project_virtual_environment": {
    "zh-Hant": "專案虛擬環境",
    "en": "Project virtual environment"
  },
  "ui.x_session_encryption": {
    "zh-Hant": "X 登入加密保存",
    "en": "X session encryption"
  },
  "ui.local_port": {
    "zh-Hant": "本機連接埠",
    "en": "Local port"
  },
  "ui.python_3_10_or_newer_is_required": {
    "zh-Hant": "需要 Python 3.12 或更新版本。",
    "en": "Python 3.12 or newer is required."
  },
  "ui.installed": {
    "zh-Hant": "已安裝。",
    "en": "Installed."
  },
  "ui.not_installed_or_could_not_be_loaded": {
    "zh-Hant": "未安裝或無法載入。",
    "en": "Not installed or could not be loaded."
  },
  "ui.executable_supports_video_merging_and_thumbnails": {
    "zh-Hant": "可執行，支援影片合併與縮圖。",
    "en": "Executable; supports video merging and thumbnails."
  },
  "ui.no_working_ffmpeg_executable_was_found": {
    "zh-Hant": "找不到可執行的 FFmpeg。",
    "en": "No working FFmpeg executable was found."
  },
  "ui.node_js_and_deno_were_not_found": {
    "zh-Hant": "未找到 Node.js 或 Deno。",
    "en": "Node.js and Deno were not found."
  },
  "ui.package_dependencies_are_consistent": {
    "zh-Hant": "套件相依性一致。",
    "en": "Package dependencies are consistent."
  },
  "ui.the_dependency_check_failed_or_timed_out": {
    "zh-Hant": "相依性檢查失敗或逾時。",
    "en": "The dependency check failed or timed out."
  },
  "ui.using_the_project_venv": {
    "zh-Hant": "使用專案 .venv。",
    "en": "Using the project .venv."
  },
  "ui.the_project_venv_is_not_being_used": {
    "zh-Hant": "目前未使用專案 .venv。",
    "en": "The project .venv is not being used."
  },
  "ui.chrome_was_found_load_the_connector_in": {
    "zh-Hant": "已找到 Chrome；連接器需在已登入 X 的個人檔案載入。",
    "en": "Chrome was found. Load the connector in the profile signed into X."
  },
  "ui.google_chrome_was_not_found": {
    "zh-Hant": "未找到 Google Chrome。",
    "en": "Google Chrome was not found."
  },
  "ui.windows_encryption_and_decryption_are_available": {
    "zh-Hant": "Windows 加密與解密可用。",
    "en": "Windows encryption and decryption are available."
  },
  "ui.windows_session_encryption_is_unavailable_in_this": {
    "zh-Hant": "目前環境無法使用 Windows 登入資料加密。",
    "en": "Windows session encryption is unavailable in this environment."
  },
  "ui.invalid_ssdl_port_setting": {
    "zh-Hant": "SSDL_PORT 設定無效。",
    "en": "Invalid SSDL_PORT setting."
  },
  "ui.ssdl_port_must_be_a_whole_number": {
    "zh-Hant": "SSDL_PORT 必須是 1～65535 的整數。",
    "en": "SSDL_PORT must be a whole number from 1 to 65535."
  },
  "ui.set_the_same_port_in_the_chrome": {
    "zh-Hant": "Chrome 連接器須設定相同連接埠；預設為 8765。",
    "en": "Set the same port in the Chrome connector; the default is 8765."
  },
  "ui.could_not_complete_environment_diagnostics": {
    "zh-Hant": "無法完成環境診斷。",
    "en": "Could not complete environment diagnostics."
  },
  "ui.run_setup_bat_to_install_the_baseline": {
    "zh-Hant": "執行 setup.bat 安裝基準套件，或停止服務後執行 update.bat。",
    "en": "Run setup.bat to install the baseline, or stop the service before running update.bat."
  },
  "ui.run_setup_bat_if_path_points_to": {
    "zh-Hant": "執行 setup.bat；若 PATH 中已有失效的 FFmpeg，請修正後重新啟動服務。",
    "en": "Run setup.bat. If PATH points to a broken FFmpeg, fix it and restart the service."
  },
  "ui.youtube_requires_node_js_22_or_deno": {
    "zh-Hant": "YouTube 需要 Node.js 22+ 或 Deno 2.3+；安裝並加入 PATH 後，重新啟動服務。",
    "en": "YouTube requires Node.js 22+ or Deno 2.3+. Install it, add it to PATH, and restart the service."
  },
  "ui.run_setup_bat_to_restore_baseline_packages": {
    "zh-Hant": "執行 setup.bat 恢復基準套件；更新引擎前請先停止服務。",
    "en": "Run setup.bat to restore baseline packages. Stop the service before updating engines."
  },
  "ui.use_setup_bat_and_start_bat_to": {
    "zh-Hant": "請使用 setup.bat 與 start.bat，避免使用其他 Python 環境。",
    "en": "Use setup.bat and start.bat to run the project environment."
  },
  "ui.install_regular_chrome_or_use_the_advanced": {
    "zh-Hant": "安裝一般 Chrome，或使用進階 X Cookie 檔案設定。",
    "en": "Install regular Chrome, or use the advanced X cookie file setting."
  },
  "ui.run_start_bat_from_your_normal_windows": {
    "zh-Hant": "從一般 Windows 桌面執行 start.bat，再重新連接 X。",
    "en": "Run start.bat from your normal Windows desktop, then reconnect X."
  },
  "ui.recheck_or_restart_start_bat_from_your": {
    "zh-Hant": "請重新檢查，或從一般 Windows 桌面重新啟動 start.bat。",
    "en": "Recheck, or restart start.bat from your normal Windows desktop."
  },
  "ui.run_setup_bat_to_repair_packages_stop": {
    "zh-Hant": "修復套件請執行 setup.bat；更新引擎請先停止服務，再執行 update.bat。安裝 Node.js 或 Deno 後請重新啟動服務。",
    "en": "Run setup.bat to repair packages. Stop the service before running update.bat. Restart after installing Node.js or Deno."
  },
  "ui.official_node_js_download": {
    "zh-Hant": "Node.js 官方下載",
    "en": "Official Node.js download"
  },
  "ui.official_deno_installation_guide": {
    "zh-Hant": "Deno 官方安裝說明",
    "en": "Official Deno installation guide"
  },
  "ui.local_service_origin_use_the_same_port": {
    "zh-Hant": "本機服務：{origin}。Chrome 連接器須使用相同連接埠。",
    "en": "Local service: {origin}. Use the same port in the Chrome connector."
  },
  "ui.this_page_uses_port_port_but_the": {
    "zh-Hant": "此頁使用連接埠 {port}，連接器目前使用 {configured}。請在 Chrome 連接器的「本機連接設定」輸入相同連接埠，再連接。",
    "en": "This page uses port {port}, but the connector uses {configured}. Set the same port in the Chrome connector’s Local connection settings, then connect."
  },
  "ui.the_local_tool_returned_an_unexpected_format": {
    "zh-Hant": "本機工具回應格式不正確，請確認連接埠及服務版本。",
    "en": "The local tool returned an unexpected format. Check the port and service version."
  },
  "ui.the_local_tool_did_not_confirm_the": {
    "zh-Hant": "本機工具未確認連接成功，請更新下載工具的登入狀態。",
    "en": "The local tool did not confirm the connection. Refresh its login status."
  },
  "ui.the_local_port_must_be_a_whole": {
    "zh-Hant": "本機連接埠必須是 1～65535 的整數。",
    "en": "The local port must be a whole number from 1 to 65535."
  },
  "ui.the_connector_has_an_update_reload_it": {
    "zh-Hant": "連接器有更新，請在 chrome://extensions 重新載入連接器，再重新整理此頁。",
    "en": "The connector has an update. Reload it at chrome://extensions, then refresh this page."
  },
  "ui.no_progress_timeout": {
    "zh-Hant": "無進度期限",
    "en": "No-progress timeout"
  },
  "ui.seconds": {
    "zh-Hant": "秒",
    "en": "seconds"
  },
  "ui.default_300_seconds_adjustable_from_30_to": {
    "zh-Hant": "預設 300 秒，可設定 30～3600。長時間沒有傳輸或處理進度時停止該工作；安全佇列等待不計入，持續有進度的長影片不受總耗時限制。下個工作生效。",
    "en": "Default 300 seconds, adjustable from 30 to 3600. Stop a job with no transfer or processing progress. Queue waits are excluded; progressing long videos have no total-duration limit. Applies to the next job."
  },
  "ui.no_progress_timeout_must_be_a_whole": {
    "zh-Hant": "無進度期限必須是 30～3600 秒的整數。",
    "en": "No-progress timeout must be a whole number from 30 to 3600 seconds."
  },
  "ui.local_data_and_download_worker": {
    "zh-Hant": "本機資料與下載排程",
    "en": "Local data and download worker"
  },
  "ui.retry_saving": {
    "zh-Hant": "重新嘗試保存",
    "en": "Retry saving"
  },
  "ui.export_diagnostics": {
    "zh-Hant": "匯出診斷",
    "en": "Export diagnostics"
  },
  "ui.diagnostics_omit_source_urls_file_lists_and": {
    "zh-Hant": "診斷不包含來源網址、檔案清單或 Cookie；錯誤文字會遮蔽憑證與本機路徑，分享前仍可自行查看內容。",
    "en": "Diagnostics omit source URLs, file lists, and cookies. Credentials and local paths in errors are redacted. Review the export before sharing."
  },
  "ui.stop_download_keep_saved_files": {
    "zh-Hant": "停止下載：保留已保存檔案",
    "en": "Stop download: keep saved files"
  },
  "ui.download_stopped_saved_files_are_retained_you": {
    "zh-Hant": "下載已停止；已保存檔案保留，可重新下載。",
    "en": "Download stopped. Saved files are retained; you can retry."
  },
  "ui.no_progress_for_too_long_this_job": {
    "zh-Hant": "下載長時間沒有進度，已停止此工作；可重試，後續佇列會繼續。",
    "en": "No progress for too long. This job was stopped; you can retry. The queue continues."
  },
  "ui.the_download_process_exited_the_queue_continues": {
    "zh-Hant": "下載程序已中斷，後續佇列會繼續；可重新下載。",
    "en": "The download process exited. The queue continues; you can retry."
  },
  "ui.local_history_needs_attention": {
    "zh-Hant": "本機紀錄需要注意",
    "en": "Local history needs attention"
  },
  "ui.download_worker_unavailable": {
    "zh-Hant": "下載排程未運作",
    "en": "Download worker unavailable"
  },
  "ui.restart_the_service_or_export_diagnostics_for": {
    "zh-Hant": "請重新啟動服務，或匯出診斷查看原因。",
    "en": "Restart the service or export diagnostics for details."
  },
  "ui.history_is_being_saved_normally": {
    "zh-Hant": "紀錄保存正常。",
    "en": "History is being saved normally."
  },
  "ui.worker_ready_waiting_for_new_jobs": {
    "zh-Hant": "下載排程正常，等待新任務。",
    "en": "Worker ready, waiting for new jobs."
  },
  "ui.the_download_is_waiting_for_queue_limits": {
    "zh-Hant": "下載工作等待安全佇列。",
    "en": "The download is waiting for queue limits."
  },
  "ui.worker_running_seconds_seconds_since_the_last": {
    "zh-Hant": "下載排程運作中；目前無進度 {seconds} 秒。",
    "en": "Worker running; {seconds} seconds since the last progress."
  },
  "ui.history_belongs_to_a_newer_version_use": {
    "zh-Hant": "紀錄來自較新版本，請使用相容版本；目前不覆寫原紀錄。",
    "en": "History belongs to a newer version. Use a compatible version; the original file is preserved."
  },
  "ui.history_cannot_be_read_and_no_valid": {
    "zh-Hant": "下載紀錄無法讀取，且沒有有效備份；原檔保留，請查看排錯說明。",
    "en": "History cannot be read and no valid backup is available. The original is preserved; see troubleshooting."
  },
  "ui.restored_the_last_valid_backup_the_damaged": {
    "zh-Hant": "已從最後有效備份恢復；損壞紀錄會另行保留。",
    "en": "Restored the last valid backup. The damaged history is preserved separately."
  },
  "ui.history_could_not_be_saved_changes_are": {
    "zh-Hant": "本機紀錄保存失敗，變更目前只在記憶體中；請檢查磁碟權限與空間後重新嘗試保存。",
    "en": "History could not be saved. Changes are currently in memory only; check disk permissions and space, then retry saving."
  },
  "ui.could_not_read_the_media_manifest_the": {
    "zh-Hant": "無法讀取媒體保存紀錄，本次會重新檢查來源。",
    "en": "Could not read the media manifest. The source will be checked again."
  },
  "ui.the_download_did_not_produce_complete_valid": {
    "zh-Hant": "下載結果沒有完整且有效的媒體檔案，請重新下載。",
    "en": "The download did not produce complete, valid media files. Please retry."
  },
  "ui.files_were_saved_but_their_manifest_could": {
    "zh-Hant": "檔案已保存，但媒體紀錄保存失敗；下次可能重新下載。",
    "en": "Files were saved, but their manifest could not be saved. A later run may download them again."
  },
  "ui.media_must_use_public_http_https_urls": {
    "zh-Hant": "媒體來源必須是公開 HTTP／HTTPS 網址；已拒絕非公開目標。",
    "en": "Media must use public HTTP/HTTPS URLs. Non-public targets were rejected."
  },
  "ui.source_dns_includes_a_non_public_address": {
    "zh-Hant": "來源 DNS 包含非公開位址；已拒絕連線。",
    "en": "Source DNS includes a non-public address. The connection was rejected."
  },
  "ui.this_source_needs_an_external_network_downloader": {
    "zh-Hant": "此來源需要外部網路下載器；目前僅允許受檢查的 HTTP／HLS／DASH 傳輸。",
    "en": "This source needs an external network downloader. Only checked HTTP/HLS/DASH transfers are supported."
  },
  "ui.enable_dynamic_capture": {
    "zh-Hant": "啟用動態媒體捕捉（選配）",
    "en": "Enable dynamic media capture (optional)"
  },
  "ui.dynamic_capture_help": {
    "zh-Hant": "一般解析找不到來源時，使用隔離暫時 Chrome 執行頁面腳本。預設關閉；不讀取日常 Chrome 登入，不自動登入或點擊頁面按鈕。最多 45 秒、40 個請求。",
    "en": "When ordinary discovery finds no usable source, run page scripts in an isolated temporary Chrome session. Off by default; no regular Chrome login, automatic sign-in or button clicks. Up to 45 seconds / 40 requests."
  },
  "ui.dynamic_capture_install": {
    "zh-Hant": "安裝選配套件：",
    "en": "Install optional dependencies:"
  },
  "ui.dynamic_capture_ready": {
    "zh-Hant": "選配套件與 Chrome 已就緒。",
    "en": "Optional dependencies and Chrome are available."
  },
  "ui.dynamic_capture_missing": {
    "zh-Hant": "尚未安裝選配套件或 Chrome；不影響一般下載。",
    "en": "Optional dependencies or Chrome are missing; ordinary downloads are unaffected."
  },
  "ui.dynamic_capture_name": {
    "zh-Hant": "動態媒體捕捉（選配）",
    "en": "Dynamic media capture (optional)"
  },
  "ui.dynamic_capture_configuration": {
    "zh-Hant": "動態媒體捕捉設定不正確。",
    "en": "Invalid dynamic media capture setting."
  },
  "ui.dynamic_capture_unavailable": {
    "zh-Hant": "動態捕捉需要選配 Playwright 與一般 Chrome；請執行 python tools/manage.py browser-setup。",
    "en": "Dynamic capture needs optional Playwright and regular Chrome. Run python tools/manage.py browser-setup."
  },
  "ui.dynamic_capture_running": {
    "zh-Hant": "正在使用隔離 Chrome 捕捉動態媒體",
    "en": "Capturing dynamic media in isolated Chrome"
  },
  "ui.dynamic_capture_timeout": {
    "zh-Hant": "動態媒體捕捉已逾時。",
    "en": "Dynamic media capture timed out."
  },
  "ui.dynamic_capture_budget": {
    "zh-Hant": "動態網頁資源超過解析上限。",
    "en": "Dynamic page resources exceeded the discovery budget."
  },
  "ui.dynamic_capture_not_found": {
    "zh-Hant": "動態捕捉沒有找到可下載的影音來源；頁面可能需要登入、操作或使用不支援的傳輸。",
    "en": "Dynamic capture found no downloadable audio/video source. The page may need sign-in, interaction or an unsupported transport."
  },
  "ui.dynamic_capture_failed": {
    "zh-Hant": "隔離 Chrome 無法完成動態捕捉；請重新安裝選配套件或查看診斷。",
    "en": "Isolated Chrome could not finish capture. Reinstall optional dependencies or inspect diagnostics."
  },
  "ui.dynamic_capture_setup_hint": {
    "zh-Hant": "啟用前執行 python tools/manage.py browser-setup；需一般 Chrome，使用隔離暫時工作階段。",
    "en": "Run python tools/manage.py browser-setup before enabling. Requires regular Chrome and uses an isolated temporary session."
  },
  "ui.dynamic_capture_stopped_timeout": {
    "zh-Hant": "動態媒體捕捉已逾時；已停止隔離瀏覽器，後續佇列會繼續。",
    "en": "Dynamic capture timed out; its isolated browser was stopped. Other queued jobs can continue."
  }
};
