# AZA-STT

一個 Windows 常駐語音輸入工具。雙擊鍵盤的 Menu 鍵開始錄音，再按一次停止；程式會使用 Groq Whisper 轉寫，整理繁體中文、半形英文標點、AI／科技品牌拼法，然後貼到目前的輸入位置。

## 功能

- `whisper-large-v3` 優先，失敗時自動切換模型與備用 API key
- 繁體中文簡轉繁，但不強制替換兩岸詞彙
- 半形英文逗號與句點
- 依 word／segment 時間戳與語音停頓補充分句
- 長句適度切開，每五句自動換段
- Groq、Gemini、ChatGPT、Claude Code、NVIDIA、OpenAI、GitHub Copilot、Codex 等科技詞彙校正
- 單一執行個體、唯一暫存音檔、輪替執行紀錄
- 常駐 Windows 右下角通知區；圖示會顯示待命、錄音、辨識、完成或錯誤狀態
- 短錄音直接上傳 WAV；約四分鐘以上的大檔案使用內建的無損 FLAC 壓縮，不需另外安裝 FFmpeg

## 使用 Release 版

1. 從 [GitHub Releases](https://github.com/ReaperTw/AZA-STT/releases/latest) 下載最新版 ZIP 並解壓縮。
2. 雙擊 `AZA-STT.exe`。
3. 第一次啟動會自動跳出 API key 設定視窗。
4. 若還沒有 Groq API key，可直接按視窗裡的 **開啟 Groq API Keys**；申請完成後貼上 key，再按 **儲存**。設定視窗關閉後，AZA-STT 會縮到 Windows 右下角通知區繼續執行。
5. 將游標放在想輸入文字的位置，雙擊 Menu 鍵開始錄音，再按一次 Menu 鍵停止；辨識完成後會自動貼上文字。

通知區的 AZA-STT 圖示可隨時確認程式仍在執行。按兩下圖示可查看狀態；
按右鍵可重新輸入 Groq API key、開啟 Groq API Keys 網頁，或完整退出程式。
錄音圓球在工作完成後自動消失是正常行為，不代表 EXE 已關閉。

一般使用者不需要複製、改名或手動編輯任何設定檔。日後若要更換 API key，
可直接從通知區圖示的右鍵選單操作，不必重新啟動。也可以雙擊
`Configure-AZA-STT.cmd` 開啟相同的設定視窗；使用這個獨立設定工具時，
儲存後需重新啟動 AZA-STT。

<details>
<summary>進階 API key 設定</summary>

進階用戶也可以設定 `GROQ_API_KEYS` 環境變數，或在 EXE 旁放置
`dictate_settings.conf`。多組 key 可用逗號、分號、空格或換行分隔。

</details>

若要開機自動啟動，請在 PowerShell 執行：

```powershell
powershell -ExecutionPolicy Bypass -File .\Install-Startup.ps1
```

移除自動啟動：

```powershell
powershell -ExecutionPolicy Bypass -File .\Uninstall-Startup.ps1
```

## 從原始碼執行

需要 Windows、Python 3.10 及麥克風。第一次執行原始碼時，也會自動跳出
API key 設定視窗。

```powershell
python -m pip install -r requirements.txt
python .\groq_dictate.py
```

## 建置 EXE

```powershell
python -m pip install -r requirements-dev.txt
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

輸出位於 `dist\AZA-STT.exe`。

## 隱私與安全

- `dictate_settings.conf`、`key.txt`、`.env`、日誌、音訊暫存及建置輸出皆由 `.gitignore` 排除。
- API key 不會編譯進 EXE，也不應提交至 GitHub。
- 設定視窗會將 key 儲存在 `%LOCALAPPDATA%\AZA-STT\dictate_settings.conf`，並限制為目前 Windows 使用者存取。
- 錄音只在停止後送往 Groq 語音 API。
- Groq 語音 API 依音訊時長計費；FLAC 只用來降低大檔案的上傳量，不會減少計費時長。
- 轉寫文字會暫時寫入 Windows 剪貼簿，以便送出 `Ctrl+V`。
- 執行紀錄位於 `%LOCALAPPDATA%\AZA-STT\aza-stt.log`，不記錄完整逐字稿或 API key。

## 驗證

```powershell
python -m unittest -v test_groq_dictate.py
python -m py_compile groq_dictate.py
```

## 授權

MIT
