import unittest
import os
import tempfile
import wave
from unittest.mock import Mock, patch

import opencc

from groq_dictate import (
    FLAC_THRESHOLD_BYTES,
    GROQ_KEYS_URL,
    GroqDictateApp,
    LANGUAGE_SIMPLIFIED,
    LANGUAGE_TRADITIONAL,
    compress_to_flac,
    create_tray_image,
    detect_default_language_mode,
    display_activation_mode,
    display_language_mode,
    display_microphone_name,
    display_record_key,
    log_info,
    load_user_input_settings,
    load_user_language_mode,
    load_user_microphone_selection,
    load_user_record_key,
    microphone_device_candidates,
    normalize_activation_mode,
    normalize_record_key,
    open_microphone_stream,
    open_groq_keys_page,
    parse_api_keys,
    prompt_for_api_keys,
    repair_microphone_name,
    run_flac_self_test,
    run_language_self_test,
    save_user_input_settings,
    save_user_language_mode,
    save_user_microphone_selection,
    save_user_record_key,
    sf,
    ui_text,
    valid_api_keys,
)
from transcription_interpreter import (
    MAX_SENTENCE_CHARACTERS,
    TranscriptionInterpreter,
    normalize_transcription,
    punctuate_from_timestamps,
    remove_transcription_prompt_leakage,
    transcription_prompt,
)


class LoggingTests(unittest.TestCase):
    @patch("builtins.print", side_effect=OSError(22, "Invalid argument"))
    def test_log_info_does_not_crash_when_packaged_app_has_no_console(self, _print):
        log_info("packaged logging regression test")

    @patch("builtins.print", side_effect=OSError(22, "Invalid argument"))
    def test_error_ui_finishes_when_packaged_app_has_no_console(self, _print):
        app = GroqDictateApp.__new__(GroqDictateApp)
        app.cancel_hide_timer = Mock()
        app.canvas = Mock()
        app.sphere = "sphere"
        app.root = Mock()
        app.root.after.return_value = "timer-id"
        app.set_tray_status = Mock()
        app.set_ui_idle = Mock()

        app.set_ui_error("test failure")

        app.set_tray_status.assert_called_once_with("error")
        self.assertEqual(app.hide_timer_id, "timer-id")


class NormalizeTranscriptionTests(unittest.TestCase):
    def test_does_not_change_intentionally_spoken_command_code(self):
        self.assertEqual(normalize_transcription("腳本和指令碼是兩個詞"), "腳本和指令碼是兩個詞")

    def test_converts_chinese_punctuation_to_half_width(self):
        self.assertEqual(
            normalize_transcription("這是腳本，請執行。真的可以嗎？可以！"),
            "這是腳本, 請執行. 真的可以嗎? 可以!",
        )

    def test_does_not_add_a_final_period_when_missing(self):
        self.assertEqual(normalize_transcription("補字"), "補字")

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
                "gemini、chat gpt、claude code、nvidia gpu、"
                "git hub、node js、type script"
            ),
            "Gemini, ChatGPT, Claude Code, NVIDIA GPU, "
            "GitHub, Node.js, TypeScript",
        )

    def test_repairs_gork_without_canonicalizing_unused_groq(self):
        self.assertEqual(
            normalize_transcription("Gork 和 GROQ"),
            "Grok 和 GROQ",
        )

    def test_does_not_canonicalize_removed_terms(self):
        text = "groq copilot deep mind meta perplexity mistral kubernetes cuda"

        self.assertEqual(normalize_transcription(text), text)

    def test_canonicalizes_gpt_56_model_names(self):
        self.assertEqual(
            normalize_transcription(
                "gpt 5.6 sol、gpt-5.6 terra、gpt 5 6 luna"
            ),
            "GPT-5.6 Sol, GPT-5.6 Terra, GPT-5.6 Luna",
        )

    def test_does_not_canonicalize_removed_sol_pro(self):
        self.assertEqual(
            normalize_transcription("gpt 5.6 sol pro"),
            "gpt 5.6 sol pro",
        )

    def test_recognizes_spoken_quota_variants(self):
        self.assertEqual(
            normalize_transcription("我的扣打快要用完了"),
            "我的 quota 快要用完了",
        )
        self.assertEqual(
            normalize_transcription("quota 還很充足"),
            "quota 還很充足",
        )

    def test_promotes_a_comma_after_an_excessively_long_sentence(self):
        source = ("字" * MAX_SENTENCE_CHARACTERS) + ",下一句"
        self.assertEqual(
            normalize_transcription(source),
            ("字" * MAX_SENTENCE_CHARACTERS) + ". 下一句",
        )

    def test_does_not_add_or_preserve_line_breaks(self):
        self.assertEqual(
            normalize_transcription("一.二.三.四.五.\n\n六."),
            "一. 二. 三. 四. 五. 六.",
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


class PromptLeakageTests(unittest.TestCase):
    def test_removes_traditional_prompt_suffix_from_spoken_text(self):
        self.assertEqual(
            remove_transcription_prompt_leakage(
                '像是現在就發生了. "標點後保留一個空格, 並依語意自然分句."'
            ),
            "像是現在就發生了.",
        )

    def test_removes_entire_traditional_prompt_instruction(self):
        self.assertEqual(
            remove_transcription_prompt_leakage(
                "使用半形標點,標點後保留一個空格,並依語意自然分句。"
            ),
            "",
        )

    def test_removes_simplified_prompt_suffix(self):
        self.assertEqual(
            remove_transcription_prompt_leakage(
                "補字。标点后保留一个空格，并按语义自然分句。"
            ),
            "補字。",
        )

    def test_preserves_natural_mention_of_half_width_punctuation(self):
        self.assertEqual(
            remove_transcription_prompt_leakage("這裡使用半形標點"),
            "這裡使用半形標點",
        )


class TranscriptionWorkflowTests(unittest.TestCase):
    def make_app(self, response, language_mode=LANGUAGE_TRADITIONAL):
        app = GroqDictateApp.__new__(GroqDictateApp)
        app.frames = [b"recorded audio"]
        app.transcription_interpreter = TranscriptionInterpreter(language_mode)
        app.transcribe_audio = Mock(return_value=response)
        app.simulate_typing = Mock(return_value=True)
        app.set_ui_success = Mock()
        app.set_ui_error = Mock()
        app.root = Mock()
        app.root.after.side_effect = lambda _delay, callback: callback()

        descriptor, wav_path = tempfile.mkstemp(suffix=".wav")
        os.close(descriptor)
        app.save_wav_file = Mock(return_value=wav_path)
        return app, wav_path

    def test_interprets_provider_response_before_pasting(self):
        app, wav_path = self.make_app({"text": "groq 和 gork，完成"})

        app.process_audio_workflow()

        app.simulate_typing.assert_called_once_with("groq 和 Grok, 完成")
        app.set_ui_success.assert_called_once_with()
        app.set_ui_error.assert_not_called()
        self.assertEqual(app.frames, [])
        self.assertFalse(os.path.exists(wav_path))

    def test_rejected_provider_response_is_not_pasted(self):
        app, wav_path = self.make_app(
            {"text": "使用半形標點,標點後保留一個空格,並依語意自然分句。"}
        )

        app.process_audio_workflow()

        app.simulate_typing.assert_not_called()
        app.set_ui_success.assert_not_called()
        app.set_ui_error.assert_called_once_with("Groq returned no spoken content.")
        self.assertEqual(app.frames, [])
        self.assertFalse(os.path.exists(wav_path))


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


class LanguageSettingsTests(unittest.TestCase):
    def test_simplified_ui_uses_mainland_terms(self):
        self.assertEqual(
            ui_text(
                "程式會縮到通知區,可設定滑鼠與麥克風裝置。",
                LANGUAGE_SIMPLIFIED,
            ),
            "程序会缩到系统托盘,可设置鼠标与麦克风设备。",
        )
        self.assertEqual(
            ui_text("程式與滑鼠", LANGUAGE_TRADITIONAL),
            "程式與滑鼠",
        )
        self.assertEqual(display_language_mode(LANGUAGE_SIMPLIFIED), "简体中文")

    def test_prompts_request_the_selected_chinese_variant(self):
        self.assertIn("简体中文", transcription_prompt(LANGUAGE_SIMPLIFIED))
        self.assertIn("繁體中文", transcription_prompt(LANGUAGE_TRADITIONAL))
        self.assertIn("quota", transcription_prompt(LANGUAGE_SIMPLIFIED))
        self.assertIn("Sol, Terra, Luna", transcription_prompt(LANGUAGE_TRADITIONAL))
        self.assertIn("Skill", transcription_prompt(LANGUAGE_TRADITIONAL))
        self.assertNotIn("Scale", transcription_prompt(LANGUAGE_TRADITIONAL))

    def test_detects_mainland_and_taiwan_windows_locales(self):
        with patch("groq_dictate.locale.getlocale", return_value=("zh_CN", "UTF-8")):
            self.assertEqual(detect_default_language_mode(), LANGUAGE_SIMPLIFIED)
        with patch("groq_dictate.locale.getlocale", return_value=("zh_TW", "UTF-8")):
            self.assertEqual(detect_default_language_mode(), LANGUAGE_TRADITIONAL)

    def test_saves_language_without_losing_other_settings(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings_path = os.path.join(temp_dir, "settings.json")
            save_user_input_settings("f9", "hold", settings_path)
            save_user_microphone_selection("Mic A", settings_path)
            self.assertEqual(
                save_user_language_mode(LANGUAGE_SIMPLIFIED, settings_path),
                LANGUAGE_SIMPLIFIED,
            )
            self.assertEqual(
                load_user_language_mode(settings_path),
                LANGUAGE_SIMPLIFIED,
            )
            self.assertEqual(load_user_input_settings(settings_path), ("f9", "hold"))
            self.assertEqual(load_user_microphone_selection(settings_path), "Mic A")

    def test_language_self_test_path(self):
        self.assertTrue(run_language_self_test())

    def test_language_self_test_fails_when_traditional_conversion_is_unavailable(self):
        real_opencc = opencc.OpenCC

        def open_converter(config):
            if config == "s2tw":
                raise RuntimeError("missing s2tw data")
            return real_opencc(config)

        with patch("groq_dictate.opencc.OpenCC", side_effect=open_converter):
            self.assertFalse(run_language_self_test())


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


class MicrophoneSettingsTests(unittest.TestCase):
    class FakeAudio:
        def __init__(self, fail_indexes=()):
            self.fail_indexes = set(fail_indexes)

        def get_default_input_device_info(self):
            return {"index": 1}

        def get_device_count(self):
            return 3

        def get_device_info_by_index(self, index):
            return (
                {"name": "Mic A", "maxInputChannels": 1, "hostApi": 0},
                {"name": "Mic B", "maxInputChannels": 1, "hostApi": 0},
                {"name": "Speaker", "maxInputChannels": 0, "hostApi": 0},
            )[index]

        def get_host_api_info_by_index(self, index):
            return {"name": "MME", "type": 2}

        def open(self, **kwargs):
            index = kwargs["input_device_index"]
            if index in self.fail_indexes:
                raise OSError(f"device {index} failed")
            return f"stream-{index}"

    def test_repairs_big5_device_names(self):
        self.assertEqual(
            repair_microphone_name("³Á§J­· (Razer Seiren V2 X)"),
            "麥克風 (Razer Seiren V2 X)",
        )

    def test_saves_microphone_without_losing_recording_control(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings_path = os.path.join(temp_dir, "settings.json")
            save_user_input_settings("f9", "hold", settings_path)
            self.assertEqual(
                save_user_microphone_selection("Razer Seiren V2 X", settings_path),
                "Razer Seiren V2 X",
            )
            self.assertEqual(load_user_input_settings(settings_path), ("f9", "hold"))
            self.assertEqual(
                load_user_microphone_selection(settings_path),
                "Razer Seiren V2 X",
            )
            self.assertEqual(
                display_microphone_name(load_user_microphone_selection(settings_path)),
                "Razer Seiren V2 X",
            )

    def test_selected_microphone_is_tried_before_default(self):
        audio = self.FakeAudio()
        candidates = microphone_device_candidates(audio, "Mic A")
        self.assertEqual([device["index"] for device in candidates[:2]], [0, 1])

    def test_failed_selected_microphone_falls_back_to_default(self):
        audio = self.FakeAudio(fail_indexes=(0,))
        stream, device = open_microphone_stream(audio, "Mic A")
        self.assertEqual(stream, "stream-1")
        self.assertEqual(device["name"], "Mic B")


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
