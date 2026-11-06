"""User-invoked native migration wizard, before either data scope is started."""
def _wizard(action):
    import clr
    clr.AddReference('System.Windows.Forms')
    from System.Windows.Forms import FolderBrowserDialog, MessageBox, MessageBoxButtons, DialogResult
    from ssdl.data_migration import migrate, rollback
    from ssdl.runtime_paths import paths
    home = paths().home
    title = '匯入舊版資料' if action == 'migrate' else '回復匯入前資料'
    with FolderBrowserDialog() as dialog:
        dialog.Description = '選擇舊版程式資料夾（內含 data）' if action == 'migrate' else '選擇 data-backups 下的一份備份資料夾'
        if action == 'rollback':
            dialog.SelectedPath = str(home / 'data-backups')
        if dialog.ShowDialog() != DialogResult.OK:
            return 0
        selected = dialog.SelectedPath
    message = ('請先關閉兩邊視窗及背景服務。\n將備份目前紀錄後匯入歷史與加密登入；媒體保留原位置。\n來源：' + selected + '\n目的：' + str(home)) if action == 'migrate' else '回復備份前的紀錄？較新的資料會另行保留。\n' + selected
    if MessageBox.Show(message, title, MessageBoxButtons.OKCancel) != DialogResult.OK:
        return 0
    from pathlib import Path
    try:
        if action == 'migrate':
            result = migrate(Path(selected), home)
        else:
            chosen = Path(selected).resolve()
            if chosen.parent != (home / 'data-backups').resolve():
                raise ValueError('請選擇此安裝版 data-backups 中的備份。')
            result = rollback(chosen.name, home)
        MessageBox.Show('已完成。備份：' + str(result.get('backup', result.get('restored'))), title)
        return 0
    except Exception as error:
        MessageBox.Show('未完成，原始資料保留。\n' + str(error), title)
        return 1


def run(action):
    # FolderBrowserDialog requires an STA thread, including the windowless EXE.
    import clr
    clr.AddReference('System.Windows.Forms')
    from System.Threading import Thread, ThreadStart, ApartmentState
    result = []
    def execute():
        try:
            result.append(_wizard(action))
        except Exception as error:
            from System.Windows.Forms import MessageBox
            MessageBox.Show('未完成，原始資料保留。\n' + str(error), 'Smart Social Downloader')
            result.append(1)
    thread = Thread(ThreadStart(execute))
    thread.SetApartmentState(ApartmentState.STA)
    thread.Start()
    thread.Join()
    return result[0]
