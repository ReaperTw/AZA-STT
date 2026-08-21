from types import SimpleNamespace
import unittest
from unittest.mock import patch

from transcription_interpreter import TranscriptionInterpreter


class TranscriptionInterpreterTests(unittest.TestCase):
    @patch(
        "transcription_interpreter.opencc.OpenCC",
        side_effect=RuntimeError("missing OpenCC data"),
    )
    def test_opencc_initialization_failure_is_logged(self, _opencc):
        with self.assertLogs("aza_stt.transcription_interpreter", level="WARNING"):
            TranscriptionInterpreter()

    def test_opencc_conversion_failure_is_logged_and_preserves_raw_text(self):
        class BrokenConverter:
            def convert(self, _text):
                raise RuntimeError("conversion failed")

        with patch(
            "transcription_interpreter.opencc.OpenCC",
            return_value=BrokenConverter(),
        ):
            interpreter = TranscriptionInterpreter()
            with self.assertLogs(
                "aza_stt.transcription_interpreter",
                level="WARNING",
            ):
                result = interpreter.interpret({"text": "保留原始文字"})

        self.assertEqual(result.text, "保留原始文字")

    def test_traditional_output_preserves_common_taiwanese_eating_word(self):
        result = TranscriptionInterpreter().interpret({"text": "我想吃飯"})

        self.assertEqual(result.text, "我想吃飯")

    def test_traditional_conversion_uses_the_public_interface(self):
        result = TranscriptionInterpreter().interpret({"text": "这是脚本"})

        self.assertEqual(result.text, "這是腳本")

    def test_empty_and_prompt_leakage_are_rejected(self):
        interpreter = TranscriptionInterpreter()

        self.assertFalse(interpreter.interpret({"text": ""}).accepted)

        result = interpreter.interpret(
            {"text": "使用半形標點,標點後保留一個空格,並依語意自然分句。"}
        )

        self.assertEqual(
            (result.accepted, result.text, result.rejection_reason),
            (False, "", "Groq returned no spoken content."),
        )

    def test_current_prompt_echo_is_rejected(self):
        interpreter = TranscriptionInterpreter()

        result = interpreter.interpret({"text": interpreter.prompt})

        self.assertFalse(result.accepted)
        self.assertEqual(result.text, "")

    def test_current_prompt_echo_is_removed_after_spoken_text(self):
        interpreter = TranscriptionInterpreter()

        result = interpreter.interpret({"text": "前句。 " + interpreter.prompt})

        self.assertEqual(result.text, "前句.")

    def test_traditional_punctuation_and_technical_terms(self):
        response = SimpleNamespace(
            text="我 用 groq 和 gork，寫 api",
            words=None,
            segments=None,
        )

        result = TranscriptionInterpreter().interpret(response)

        self.assertEqual(result.text, "我 用 groq 和 Grok, 寫 API")

    def test_removes_standalone_fillers_and_provider_line_breaks(self):
        result = TranscriptionInterpreter().interpret(
            {"text": "嗯，我覺得，呃... 這個可以。\n\n下一句"}
        )

        self.assertEqual(result.text, "我覺得, 這個可以. 下一句")

    def test_preserves_terminal_agreement_word(self):
        result = TranscriptionInterpreter().interpret({"text": "我回答：嗯。"})

        self.assertEqual(result.text, "我回答: 嗯.")

    def test_removes_filler_with_consecutive_punctuation(self):
        result = TranscriptionInterpreter().interpret(
            {"text": "我覺得，呃...，這個可以"}
        )

        self.assertEqual(result.text, "我覺得, 這個可以")

    def test_removes_pause_ellipses_and_standalone_interjections(self):
        result = TranscriptionInterpreter().interpret(
            {"text": "我需要想一下 ... 噢，哦，喔，哇！然後繼續…下一句"}
        )

        self.assertEqual(result.text, "我需要想一下然後繼續下一句")

    def test_rejects_ellipsis_only_transcription(self):
        result = TranscriptionInterpreter().interpret({"text": "..."})

        self.assertFalse(result.accepted)
        self.assertEqual(result.text, "")

    def test_preserves_urls_containing_ellipsis(self):
        result = TranscriptionInterpreter().interpret(
            {"text": "路徑 https://example.com/.../file ftp://example.com/.../file"}
        )

        self.assertEqual(result.text, "路徑 https://example.com/.../file ftp://example.com/.../file")

    def test_removes_ellipsis_immediately_after_url_and_chinese_punctuation(self):
        result = TranscriptionInterpreter().interpret(
            {"text": "網址 https://example.com，然後...繼續"}
        )

        self.assertEqual(result.text, "網址 https://example.com, 然後繼續")

    def test_public_interface_preserves_urls_versions_decimals_and_thousands(self):
        result = TranscriptionInterpreter().interpret(
            {
                "text": (
                    "Next.js 版本 1.2 網址 https://example.com，"
                    "數字 1,000 正常嗎？"
                )
            }
        )

        self.assertEqual(
            result.text,
            "Next.js 版本 1.2 網址 https://example.com, 數字 1,000 正常嗎?",
        )

    def test_simplified_conversion(self):
        result = TranscriptionInterpreter("zh-CN").interpret(
            {"text": "我使用滑鼠，開啟資料夾"}
        )

        self.assertEqual(result.text, "我使用滑鼠, 开启资料夹")

    def test_split_words_preserve_raw_groq_spelling_with_timestamp_punctuation(self):
        response = {
            "text": "Groq測試",
            "words": [
                {"word": "G", "start": 0, "end": 0.1},
                {"word": "ro", "start": 0.1, "end": 0.2},
                {"word": "q", "start": 0.2, "end": 0.3},
                {"word": "測試", "start": 1.2, "end": 1.3},
            ],
        }

        result = TranscriptionInterpreter().interpret(response)

        self.assertEqual(result.text, "Groq. 測試")

    def test_segment_fallback(self):
        response = {
            "text": "hello world",
            "segments": [
                {"text": "hello", "start": 0, "end": 0.1},
                {"text": "world", "start": 1, "end": 1.1},
            ],
        }

        result = TranscriptionInterpreter().interpret(response)

        self.assertEqual(result.text, "hello. world")

    def test_prompt_matches_frequently_spoken_terms(self):
        interpreter = TranscriptionInterpreter()

        self.assertIn("Skill/Skills", interpreter.prompt)
        self.assertIn("Sol, Terra, Luna", interpreter.prompt)
        self.assertIn("子代理, Subagent", interpreter.prompt)
        for unused_term in ("Groq", "Scale", "Sol Pro", "Extra High", "Copilot"):
            self.assertNotIn(unused_term, interpreter.prompt)
        self.assertIn("不要換行", interpreter.prompt)
        self.assertIn("繁體中文", interpreter.prompt)

    def test_simplified_prompt_language(self):
        self.assertIn("简体中文", TranscriptionInterpreter("zh-CN").prompt)


if __name__ == "__main__":
    unittest.main()
