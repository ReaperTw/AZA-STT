# AZA-STT 轉錄詞彙清單

這份文件維護「使用者常講、但 Whisper 可能因口音、連音或大小寫而辨識不穩定」的名詞。它和模型價格、排名、可用性分開；那些資訊會變動，不應寫死在轉錄詞彙表中。

最後檢視：2026-08-16

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
| Sol | GPT-5.6 Sol | Prompt 優先提示獨立名稱；若完整說出 GPT-5.6，仍統一其格式。 |
| Terra | GPT-5.6 Terra | Prompt 優先提示獨立名稱；若完整說出 GPT-5.6，仍統一其格式。 |
| Luna | GPT-5.6 Luna | Prompt 優先提示獨立名稱；若完整說出 GPT-5.6，仍統一其格式。 |
| xhigh | x high、x-high | 可作為 reasoning effort 名稱保留；不要把一般句子中的 `high` 改掉。 |
| Skill / Skills | 可能被聽成其他近音 | 直接在 Prompt 提示常見拼字，不做猜測式自動改寫。 |
| 子代理 / Subagent | 子代理、Subagent | 直接在 Prompt 提示中英文寫法；沒有實際誤辨樣本前不做自動改寫。 |

## 模型名稱備註

使用者通常直接說 Sol、Terra、Luna，不一定先說 GPT-5.6，因此 Prompt 使用獨立名稱。價格、排名和可用性不放在這裡，因為它們可能隨時間改變。

Reasoning 名稱可以分成兩套來看：

- API 技術值：`none`、`low`、`medium`、`high`、`xhigh`、`max`。
- ChatGPT 介面顯示不是目前轉錄提示重點。

若使用者開始常講其他名稱，再依實際辨識錯誤補入，不預先擴張清單。

## 已納入一般提示詞的相關名詞

目前 `transcription_interpreter.py` 的 `transcription_prompt()` 會先說明 AI／軟體開發情境、略過口語停頓用的「呃／嗯」、不自動換行，以及 `Skill/Skills` 偏好；`PROMPT_TERMS` 只保留近期常講且需要提示 Whisper 拼字的短名詞。較廣的安全拼字修正放在同檔的 `TECH_TERM_CORRECTIONS`。完整執行期規則均以 `transcription_interpreter.py` 為準。

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
