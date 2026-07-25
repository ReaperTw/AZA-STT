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
- 短錄音直接上傳 WAV；大檔案才使用無損 FLAC

## 使用 Release 版

1. 從 GitHub Releases 下載並解壓縮。
2. 將 `dictate_settings.example.conf` 複製為 `dictate_settings.conf`。
3. 把範例內容換成自己的 Groq API key，一行一組。
4. 執行 `AZA-STT.exe`。
5. 雙擊 Menu 鍵開始錄音，再按一次停止。

也可以設定 `GROQ_API_KEYS` 環境變數，並以逗號、分號或換行分隔多組 key。

若要開機自動啟動，請在 PowerShell 執行：

```powershell
powershell -ExecutionPolicy Bypass -File .\Install-Startup.ps1
```

移除自動啟動：

```powershell
powershell -ExecutionPolicy Bypass -File .\Uninstall-Startup.ps1
```

## 從原始碼執行

需要 Windows、Python 3.10、麥克風，以及 Groq API key。

```powershell
python -m pip install -r requirements.txt
Copy-Item .\dictate_settings.example.conf .\dictate_settings.conf
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
- 錄音只在停止後送往 Groq 語音 API。
- 轉寫文字會暫時寫入 Windows 剪貼簿，以便送出 `Ctrl+V`。
- 執行紀錄位於 `%LOCALAPPDATA%\AZA-STT\aza-stt.log`，不記錄完整逐字稿或 API key。

## 驗證

```powershell
python -m unittest -v test_groq_dictate.py
python -m py_compile groq_dictate.py
```

## 授權

MIT
