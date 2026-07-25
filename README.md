# AZA-STT

AZA-STT 是一個 Windows 語音輸入工具。把游標放在任何可以打字的位置,按下錄音鍵開始說話,程式就會把語音整理成文字並自動貼上。

它特別針對繁體中文口述內容做整理,包含自然分句、半形英文標點、段落切分,以及常見 AI 與科技名稱的拼字修正。程式平常會待在 Windows 右下角通知區,不會一直占用桌面空間。

## 主要功能

- 使用 Groq Whisper 進行語音辨識
- 自動整理成繁體中文,但不強制替換兩岸用詞
- 統一使用半形逗號、句點及其他英文標點
- 依照說話停頓自然分句,每五句自動換段
- 自動修正 Groq、Gemini、ChatGPT、Claude Code、NVIDIA、OpenAI、GitHub Copilot、Codex 等科技名稱
- 辨識完成後直接貼到目前的輸入位置
- 可自行更換錄音按鍵,儲存後立即生效
- 常駐 Windows 右下角通知區,可隨時查看狀態、修改設定或退出
- 短錄音直接上傳 WAV,較長的錄音會自動使用無損 FLAC 壓縮,不需另外安裝 FFmpeg
- 辨識失敗時會自動切換模型或備用 API key

## 如何使用

### 1. 下載並啟動

從 [GitHub Releases](https://github.com/ReaperTw/AZA-STT/releases/latest) 下載最新版本。

- 想直接使用:下載 `AZA-STT.exe`
- 想連同 README 與輔助工具一起保存:下載完整 ZIP 並解壓縮

下載後雙擊 `AZA-STT.exe` 即可啟動,不需要另外安裝。

### 2. 設定 Groq API key

第一次啟動時,AZA-STT 會自動開啟設定視窗。

1. 如果還沒有 API key,按下 **開啟 Groq API Keys** 前往 [Groq 官方申請頁面](https://console.groq.com/keys)。
2. 將取得的 key 貼進設定視窗。
3. 按下 **儲存**。

設定完成後,AZA-STT 會縮到 Windows 右下角通知區繼續執行。

### 3. 開始語音輸入

1. 把游標放在想輸入文字的位置。
2. 連按兩下預設的 **Menu 鍵** 開始錄音。
3. 說完後再按一次相同按鍵。
4. 等待辨識完成,文字會自動貼到游標位置。

錄音時會出現紅色圓球,辨識時會變成橘色,完成後顯示綠色並自動消失。圓球消失不代表程式已關閉,AZA-STT 仍會留在右下角通知區等待下一次使用。

### 4. 更換錄音按鍵

1. 在 Windows 右下角找到 AZA-STT 小圖示。
2. 按右鍵並選擇 **設定錄音按鍵**。
3. 按下 **按下新的錄音鍵**,再直接按一次想使用的鍵。
4. 按下 **儲存**。

支援 Menu、F1–F12、Pause、Scroll Lock、Insert、Home、End、Page Up、Page Down 與 Print Screen。為了避免影響正常打字,不接受英文字母、數字、空白鍵或 Ctrl、Shift、Alt 等常用按鍵。

### 5. 其他設定與退出

在右下角 AZA-STT 圖示按右鍵,還可以:

- 重新輸入 Groq API key
- 開啟 Groq API Keys 網頁
- 完整退出 AZA-STT

按兩下通知區圖示則可以查看目前狀態和正在使用的錄音按鍵。

## 常見問題

### 錄音圓球不見了,程式是不是關掉了?

不是。圓球只在錄音與辨識期間出現。平常請在 Windows 右下角通知區尋找 AZA-STT 小圖示。

### 雙擊 EXE 沒有出現新視窗?

AZA-STT 同一時間只會執行一份。它可能已經在右下角通知區運作,因此不會再開啟第二份。

### 鍵盤沒有 Menu 鍵怎麼辦?

從右下角 AZA-STT 圖示的右鍵選單更換錄音按鍵即可。

### 如何更換 Groq API key?

在右下角 AZA-STT 圖示按右鍵,選擇 **重新輸入 Groq API key**。儲存後立即生效。

## 隱私與安全

AZA-STT 本身在你的 Windows 電腦上執行,沒有自己的帳號系統或中繼伺服器。

- Groq API key 只會儲存在這台電腦的 `%LOCALAPPDATA%\AZA-STT\dictate_settings.conf`
- 錄音停止後,音訊會直接送往 Groq 語音 API 進行辨識
- 暫存的 WAV 或 FLAC 音訊會在處理完成後刪除
- 辨識結果會暫時放入 Windows 剪貼簿,以便自動貼上
- 本機執行紀錄不保存完整逐字稿或 API key
- 程式沒有另外加入廣告、使用者追蹤或遙測服務

完整原始碼公開在這個 Repository。如果對程式行為有疑慮,可以直接檢查 [`groq_dictate.py`](groq_dictate.py),交給熟悉 Python 的人查看,或使用 AI 程式碼工具協助檢查後再執行。

## 授權

AZA-STT 使用 [MIT License](LICENSE)。
