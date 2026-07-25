import unittest
import os
import tempfile
import wave
from unittest.mock import Mock, patch

from groq_dictate import (
    FLAC_THRESHOLD_BYTES,
    GROQ_KEYS_URL,
    GroqDictateApp,
    MAX_SENTENCE_CHARACTERS,
    compress_to_flac,
    create_tray_image,
    display_activation_mode,
    display_record_key,
    load_user_input_settings,
    load_user_record_key,
    normalize_transcription,
    normalize_activation_mode,
    normalize_record_key,
    open_groq_keys_page,
    parse_api_keys,
    prompt_for_api_keys,
    punctuate_from_timestamps,
    run_flac_self_test,
    save_user_input_settings,
    save_user_record_key,
    sf,
    valid_api_keys,
)


class NormalizeTranscriptionTests(unittest.TestCase):
    def test_does_not_change_intentionally_spoken_command_code(self):
        self.assertEqual(normalize_transcription("腳本和指令碼是兩個詞"), "腳本和指令碼是兩個詞.")

    def test_converts_chinese_punctuation_to_half_width(self):
        self.assertEqual(
            normalize_transcription("這是腳本，請執行。真的可以嗎？可以！"),
            "這是腳本, 請執行. 真的可以嗎? 可以!",
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
            "Groq, Gemini, ChatGPT, Claude Code, NVIDIA GPU, "
            "GitHub Copilot, Node.js, TypeScript.",
        )

    def test_keeps_groq_and_grok_distinct(self):
        self.assertEqual(normalize_transcription("groq 和 grok"), "Groq 和 Grok.")

    def test_promotes_a_comma_after_an_excessively_long_sentence(self):
        source = ("字" * MAX_SENTENCE_CHARACTERS) + ",下一句"
        self.assertEqual(
            normalize_transcription(source),
            ("字" * MAX_SENTENCE_CHARACTERS) + ". 下一句.",
        )

    def test_adds_a_paragraph_break_after_five_sentences(self):
        self.assertEqual(
            normalize_transcription("一.二.三.四.五.六."),
            "一. 二. 三. 四. 五.\n\n六.",
        )

    def test_preserves_urls_versions_decimals_and_thousands(self):
        self.assertEqual(
            normalize_transcription(
                "Next.js 版本 1.2 網址 https://example.com，數字 1,000 正常嗎？"
            ),
            "Next.js 版本 1.2 網址 https://example.com, "
            "數字 1,000 正常嗎?",
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


class AudioCompressionTests(unittest.TestCase):
    def test_flac_threshold_is_about_four_minutes_of_recorded_audio(self):
        pcm_bytes_per_second = 16000 * 1 * 2
        self.assertEqual(FLAC_THRESHOLD_BYTES, 8 * 1024 * 1024)
        self.assertGreater(FLAC_THRESHOLD_BYTES / pcm_bytes_per_second, 240)
        self.assertLess(FLAC_THRESHOLD_BYTES / pcm_bytes_per_second, 270)

    @unittest.skipIf(sf is None, "soundfile is not installed")
    def test_compresses_wav_to_flac_without_external_ffmpeg(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            wav_path = os.path.join(temp_dir, "sample.wav")
            flac_path = os.path.join(temp_dir, "sample.flac")
            with wave.open(wav_path, "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(16000)
                wav_file.writeframes(b"\x00\x00" * 16000)

            self.assertTrue(compress_to_flac(wav_path, flac_path))
            with open(flac_path, "rb") as flac_file:
                self.assertEqual(flac_file.read(4), b"fLaC")
            self.assertLess(os.path.getsize(flac_path), os.path.getsize(wav_path))

    @unittest.skipIf(sf is None, "soundfile is not installed")
    def test_packaged_flac_self_test_path(self):
        self.assertTrue(run_flac_self_test())


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


class TrayIconTests(unittest.TestCase):
    def test_creates_a_valid_rgba_icon_for_each_status(self):
        for status in ("idle", "recording", "processing", "success", "error"):
            with self.subTest(status=status):
                image = create_tray_image(status=status, size=64)
                self.assertIsNotNone(image)
                self.assertEqual(image.mode, "RGBA")
                self.assertEqual(image.size, (64, 64))
                self.assertIsNotNone(image.getbbox())


class RecordingKeySettingsTests(unittest.TestCase):
    def test_normalizes_supported_key_names_and_aliases(self):
        self.assertEqual(normalize_record_key("F8"), "f8")
        self.assertEqual(normalize_record_key("apps"), "menu")
        self.assertEqual(normalize_record_key("PageUp"), "page up")
        self.assertEqual(normalize_record_key("space"), "space")
        self.assertEqual(normalize_record_key("ctrl"), "ctrl")
        self.assertEqual(normalize_record_key("mouse:x"), "mouse:x1")
        self.assertEqual(display_record_key("f8"), "F8")
        self.assertEqual(display_record_key("mouse:x2"), "滑鼠側鍵 2 (下一頁)")

    def test_saves_and_loads_recording_key(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings_path = os.path.join(temp_dir, "settings.json")
            self.assertEqual(save_user_record_key("F9", settings_path), "f9")
            self.assertEqual(load_user_record_key(settings_path), "f9")

    def test_saves_and_loads_activation_mode(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings_path = os.path.join(temp_dir, "settings.json")
            self.assertEqual(
                save_user_input_settings("mouse:x2", "hold", settings_path),
                ("mouse:x2", "hold"),
            )
            self.assertEqual(
                load_user_input_settings(settings_path),
                ("mouse:x2", "hold"),
            )
            self.assertEqual(display_activation_mode("hold"), "按住時錄音,放開停止")

    def test_invalid_or_missing_settings_use_menu_key(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            missing_path = os.path.join(temp_dir, "missing.json")
            self.assertEqual(
                load_user_input_settings(missing_path),
                ("menu", "double_press"),
            )

            invalid_path = os.path.join(temp_dir, "invalid.json")
            with open(invalid_path, "w", encoding="utf-8") as file:
                file.write(
                    '{"record_key": "definitely-not-a-real-key", '
                    '"activation_mode": "unknown"}'
                )
            self.assertEqual(
                load_user_input_settings(invalid_path),
                ("menu", "double_press"),
            )
            self.assertEqual(normalize_activation_mode("unknown"), "double_press")


class RecordingActivationModeTests(unittest.TestCase):
    @staticmethod
    def make_app(mode):
        app = GroqDictateApp.__new__(GroqDictateApp)
        app.activation_mode = mode
        app.is_processing_ui = False
        app.is_key_held = False
        app.is_recording = False
        app.last_press_time = 0
        app.double_press_threshold = 0.4

        def start_recording():
            app.is_recording = True

        def stop_recording():
            app.is_recording = False

        app.start_recording_process = Mock(side_effect=start_recording)
        app.stop_recording_process = Mock(side_effect=stop_recording)
        return app

    def test_single_press_toggles_recording(self):
        app = self.make_app("single_press")
        app.on_key_down()
        app.start_recording_process.assert_called_once()
        app.on_key_up()
        app.on_key_down()
        app.stop_recording_process.assert_called_once()

    def test_hold_records_only_while_pressed(self):
        app = self.make_app("hold")
        app.on_key_down()
        app.start_recording_process.assert_called_once()
        app.on_key_up()
        app.stop_recording_process.assert_called_once()

    def test_mouse_filter_suppresses_only_selected_side_button(self):
        app = GroqDictateApp.__new__(GroqDictateApp)
        app.record_key = "mouse:x1"
        app.mouse_listener = Mock()
        x1_data = Mock(mouseData=(1 << 16))
        x2_data = Mock(mouseData=(2 << 16))

        app.mouse_event_filter(
            0x20B,
            x1_data,
        )
        app.mouse_listener.suppress_event.assert_called_once()

        app.mouse_event_filter(
            0x20B,
            x2_data,
        )
        app.mouse_listener.suppress_event.assert_called_once()

    def test_double_press_mode_requires_two_presses(self):
        app = self.make_app("double_press")
        with (
            patch("groq_dictate.time.time", side_effect=(10.0, 10.2)),
            patch("groq_dictate.log_info"),
        ):
            app.on_key_down()
            app.start_recording_process.assert_not_called()
            app.on_key_up()
            app.on_key_down()
        app.start_recording_process.assert_called_once()


if __name__ == "__main__":
    unittest.main()
