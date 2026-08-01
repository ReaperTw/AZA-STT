# AZA-STT 轉錄詞彙清單

這份文件維護「使用者常講、但 Whisper 可能因口音、連音或大小寫而辨識不穩定」的名詞。它和模型價格、排名、可用性分開；那些資訊會變動，不應寫死在轉錄詞彙表中。

最後檢視：2026-08-02

## 維護原則

- **Canonical** 是最後希望貼出的寫法。
- **常見辨識變體** 是提示詞或後處理值得照顧的拼法，不代表每個變體都能安全自動改寫。
- 兩個詞如果發音接近但意義不同，保留兩者並記錄歧義，不要用無條件替換把它們合併。
- 新增詞彙時，依用途更新 `transcription_interpreter.py` 的 `PROMPT_TERMS` 或 `TECH_TERM_CORRECTIONS`，並同步更新 `test_transcription_interpreter.py`；文件是可讀的索引，不是執行期設定檔。
- 只加入實際常講或確實容易辨識錯誤的詞，避免把所有歷史模型名稱塞進 Whisper prompt。

## 目前優先詞彙

| Canonical | 常見語音／辨識變體 | 處理方式 |
| --- | --- | --- |
| Grok | Gork、GROK | `Gork` 可安全修正為 `Grok`。 |
| Groq | GROQ、Groq | 保留為 `Groq`；不要和 `Grok` 無條件合併。 |
| GPT-5.6 Sol | GPT 5.6 Sol、GPT-5 6 Sol | 統一為 `GPT-5.6 Sol`。 |
| GPT-5.6 Terra | GPT 5.6 Terra、GPT-5 6 Terra | 統一為 `GPT-5.6 Terra`。 |
| GPT-5.6 Luna | GPT 5.6 Luna、GPT-5 6 Luna | 統一為 `GPT-5.6 Luna`。 |
| GPT-5.6 Sol Pro | GPT 5.6 Sol Pro、Sol Pro | 只有完整模型名才自動統一；`Pro` 單獨出現不自動改寫。 |
| xhigh | x high、x-high | 可作為 reasoning effort 名稱保留；不要把一般句子中的 `high` 改掉。 |
| Extra High | Extra-High、extra high | 保留為 ChatGPT 介面常見的顯示名稱。 |
| Skill / Skills | 可能被聽成 Scale 或其他近音 | `Skill/Skills` 是較常使用的意圖，但不能把所有 `Scale` 盲改成 `Skill`；先保留上下文。 |
| Scale | 可能和 Skill 混淆 | 使用者較少提到；只有有明確上下文時才保留為 `Scale`。 |

## GPT-5.6 名稱備註

目前文件只記錄使用者近期會談到的 GPT-5.6 家族：Sol、Terra、Luna，以及 Sol Pro。價格、性價比和可用性不放在這裡，因為它們可能隨時間改變。

Reasoning 名稱可以分成兩套來看：

- API 技術值：`none`、`low`、`medium`、`high`、`xhigh`、`max`。
- ChatGPT 介面顯示：`Instant`、`Medium`、`High`、`Extra High`、`Pro`。

`Max` 和 `Extra High` 不應在文件中視為同一個字串：前者是 API effort 名稱，後者是 ChatGPT 介面名稱。`ultra` 是目前部分 Codex 工作階段可能暴露的介面詞，但不是這份公開 GPT-5.6 API 清單的標準值；若使用者開始常講，再另外記錄其實際出現的產品介面。

## 已納入一般提示詞的相關名詞

目前 `transcription_interpreter.py` 的 `transcription_prompt()` 會先說明 AI／軟體開發情境與 `Skill/Skills` 偏好；`PROMPT_TERMS` 只保留經常需要提示 Whisper 拼字的短專有名詞清單，例如 Groq、Grok、GPT-5.6 家族與常用開發工具。較廣的安全拼字修正放在同檔的 `TECH_TERM_CORRECTIONS`。完整執行期規則均以 `transcription_interpreter.py` 為準。

## 新增詞彙的格式

新增時請使用下列欄位：

```text
Canonical: 最終輸出寫法
Variants: 常見口音／ASR 變體
Context: 如何和相似詞區分
Action: prompt、後處理、僅文件，或需要實際錄音再決定
Date: YYYY-MM-DD
```

## 官方名稱參考

- [OpenAI API Models](https://developers.openai.com/api/docs/models)
- [OpenAI Model guidance](https://developers.openai.com/api/docs/guides/latest-model)
- [GPT-5.6 in ChatGPT](https://help.openai.com/en/articles/20001354-gpt-5-6-in-chatgpt)
