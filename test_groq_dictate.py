import unittest
from unittest.mock import Mock, patch

from groq_dictate import (
    GROQ_KEYS_URL,
    MAX_SENTENCE_CHARACTERS,
    normalize_transcription,
    open_groq_keys_page,
    parse_api_keys,
    prompt_for_api_keys,
    punctuate_from_timestamps,
    valid_api_keys,
)


class NormalizeTranscriptionTests(unittest.TestCase):
    def test_does_not_change_intentionally_spoken_command_code(self):
        self.assertEqual(normalize_transcription("腳本和指令碼是兩個詞"), "腳本和指令碼是兩個詞.")

    def test_converts_chinese_punctuation_to_half_width(self):
        self.assertEqual(
            normalize_transcription("這是腳本，請執行。真的可以嗎？可以！"),
            "這是腳本,請執行.真的可以嗎?可以!",
        )

    def test_adds_a_final_period_when_missing(self):
        self.assertEqual(normalize_transcription("這是一段沒有句號的文字"), "這是一段沒有句號的文字.")

    def test_does_not_duplicate_existing_terminal_punctuation(self):
        self.assertEqual(normalize_transcription("已經完成."), "已經完成.")

    def test_preserves_english_spacing(self):
        self.assertEqual(
            normalize_transcription("Hello, world. This is a test."),
            "Hello, world. This is a test.",
        )

    def test_canonicalizes_ai_and_tech_names(self):
        self.assertEqual(
            normalize_transcription(
                "groq、gemini、chat gpt、claude code、nvidia gpu、"
                "git hub copilot、node js、type script"
            ),
            "Groq,Gemini,ChatGPT,Claude Code,NVIDIA GPU,"
            "GitHub Copilot,Node.js,TypeScript.",
        )

    def test_keeps_groq_and_grok_distinct(self):
        self.assertEqual(normalize_transcription("groq 和 grok"), "Groq 和 Grok.")

    def test_promotes_a_comma_after_an_excessively_long_sentence(self):
        source = ("字" * MAX_SENTENCE_CHARACTERS) + ",下一句"
        self.assertEqual(
            normalize_transcription(source),
            ("字" * MAX_SENTENCE_CHARACTERS) + ".下一句.",
        )

    def test_adds_a_paragraph_break_after_five_sentences(self):
        self.assertEqual(
            normalize_transcription("一.二.三.四.五.六."),
            "一.二.三.四.五.\n\n六.",
        )


class TimestampPunctuationTests(unittest.TestCase):
    def test_uses_word_pauses_without_rewriting_words(self):
        words = [
            {"word": "第一句", "start": 0.0, "end": 0.5},
            {"word": "第二句", "start": 0.9, "end": 1.3},
            {"word": "第三句", "start": 2.2, "end": 2.6},
        ]
        self.assertEqual(
            punctuate_from_timestamps("第一句第二句第三句", words=words),
            "第一句,第二句.第三句",
        )

    def test_falls_back_when_timestamp_words_do_not_match(self):
        words = [{"word": "完全不同", "start": 0.0, "end": 1.0}]
        self.assertEqual(
            punctuate_from_timestamps("原始文字", words=words),
            "原始文字",
        )

    def test_preserves_brand_spelling_when_word_timestamps_split_tokens(self):
        words = [
            {"word": "G", "start": 0.0, "end": 0.1},
            {"word": "ro", "start": 0.1, "end": 0.2},
            {"word": "q", "start": 0.2, "end": 0.3},
            {"word": "Gem", "start": 0.7, "end": 0.8},
            {"word": "ini", "start": 0.8, "end": 1.0},
        ]
        self.assertEqual(
            punctuate_from_timestamps("Groq Gemini", words=words),
            "Groq, Gemini",
        )


class ApiKeyConfigurationTests(unittest.TestCase):
    def test_parses_multiple_keys_and_ignores_comments(self):
        self.assertEqual(
            parse_api_keys("# comment\ngsk_" + ("a" * 30) + ", gsk_" + ("b" * 30)),
            ["gsk_" + ("a" * 30), "gsk_" + ("b" * 30)],
        )

    def test_rejects_invalid_key_format(self):
        self.assertFalse(valid_api_keys(["not-a-groq-key"]))

    def test_accepts_groq_key_format(self):
        self.assertTrue(valid_api_keys(["gsk_" + ("a" * 30)]))

    @patch("groq_dictate.messagebox.showinfo")
    @patch("groq_dictate.save_user_api_keys")
    @patch("groq_dictate.ApiKeySetupDialog")
    def test_configuration_dialog_saves_valid_key(self, dialog, save_keys, showinfo):
        expected = ["gsk_" + ("a" * 30)]
        dialog.return_value.result = expected

        self.assertEqual(prompt_for_api_keys(parent=Mock()), expected)
        save_keys.assert_called_once_with(expected)
        showinfo.assert_called_once()

    @patch("groq_dictate.ApiKeySetupDialog")
    def test_configuration_dialog_can_be_cancelled(self, dialog):
        dialog.return_value.result = None
        self.assertEqual(prompt_for_api_keys(parent=Mock()), [])

    @patch("groq_dictate.webbrowser.open_new_tab", return_value=True)
    def test_opens_official_groq_keys_page(self, open_new_tab):
        self.assertTrue(open_groq_keys_page())
        open_new_tab.assert_called_once_with(GROQ_KEYS_URL)


if __name__ == "__main__":
    unittest.main()
