# -*- coding: utf-8 -*-
import time
import sys
import os
import threading
import tempfile
import wave
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from threading import Event
from datetime import datetime
import subprocess
import re
import ctypes
import json
import logging
import locale
import queue
import webbrowser
from logging.handlers import RotatingFileHandler

try:
    import soundfile as sf
except ImportError:
    sf = None

try:
    import winreg
except ImportError:
    winreg = None

try:
    import pystray
    from PIL import Image, ImageDraw
except ImportError:
    pystray = None
    Image = None
    ImageDraw = None

import keyboard
import pyaudio
import pyperclip
from groq import Groq
import opencc
from pynput import mouse as pynput_mouse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else SCRIPT_DIR
APP_DATA_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA", tempfile.gettempdir()),
    "AZA-STT",
)
os.makedirs(APP_DATA_DIR, exist_ok=True)
LOG_FILE_PATH = os.path.join(APP_DATA_DIR, "aza-stt.log")
USER_KEY_FILE_PATH = os.path.join(APP_DATA_DIR, "dictate_settings.conf")
USER_SETTINGS_FILE_PATH = os.path.join(APP_DATA_DIR, "settings.json")
GROQ_KEYS_URL = "https://console.groq.com/keys"
_LOGGER = None

TECH_TERMS = (
    "Groq", "Gemini", "ChatGPT", "OpenAI", "Claude", "Claude Code",
    "Anthropic", "NVIDIA", "CUDA", "Google", "DeepMind", "Microsoft",
    "GitHub", "GitHub Copilot", "Copilot", "Meta", "Llama", "xAI", "Grok",
    "Mistral", "Perplexity", "Hugging Face", "Cursor", "Codex", "Python",
    "JavaScript", "TypeScript", "React", "Next.js", "Node.js", "VS Code",
    "Docker", "Kubernetes", "API", "quota", "GPU", "AI", "AGI", "LLM",
)

LANGUAGE_TRADITIONAL = "zh-TW"
LANGUAGE_SIMPLIFIED = "zh-CN"
LANGUAGE_MODES = (LANGUAGE_TRADITIONAL, LANGUAGE_SIMPLIFIED)
_UI_CONVERTERS = {}
SIMPLIFIED_UI_PHRASES = (
    ("滑鼠", "鼠标"),
    ("剪贴簿", "剪贴板"),
    ("通知区", "系统托盘"),
    ("辨识", "识别"),
    ("游标", "光标"),
    ("连按两下", "连续按两次"),
    ("按一下", "按一次"),
    ("目前", "当前"),
    ("资料夹", "文件夹"),
    ("原始码", "源代码"),
    ("逐字稿", "转录稿"),
    ("设定", "设置"),
    ("程式", "程序"),
    ("图示", "图标"),
    ("档案", "文件"),
    ("装置", "设备"),
    ("讯息", "信息"),
    ("连线", "连接"),
)


def normalize_language_mode(mode):
    normalized = str(mode or "").strip()
    return normalized if normalized in LANGUAGE_MODES else None


def detect_default_language_mode():
    try:
        locale_name = locale.getlocale()[0] or ""
    except (ValueError, TypeError):
        locale_name = ""
    normalized = locale_name.replace("_", "-").lower()
    if normalized.startswith(("zh-cn", "zh-sg", "zh-hans")):
        return LANGUAGE_SIMPLIFIED
    return LANGUAGE_TRADITIONAL


def ui_text(text, language_mode=LANGUAGE_TRADITIONAL):
    value = str(text)
    if normalize_language_mode(language_mode) != LANGUAGE_SIMPLIFIED:
        return value
    converter = _UI_CONVERTERS.get(LANGUAGE_SIMPLIFIED)
    if converter is None:
        converter = opencc.OpenCC("t2s")
        _UI_CONVERTERS[LANGUAGE_SIMPLIFIED] = converter
    value = converter.convert(value)
    for source, replacement in SIMPLIFIED_UI_PHRASES:
        value = value.replace(source, replacement)
    return value


def display_language_mode(mode):
    return (
        "简体中文"
        if normalize_language_mode(mode) == LANGUAGE_SIMPLIFIED
        else "繁體中文"
    )


def transcription_prompt(language_mode):
    if normalize_language_mode(language_mode) == LANGUAGE_SIMPLIFIED:
        description = "简体中文 AI 与软件开发讨论转录稿。常用拼写: "
        instruction = ". 使用半角标点,标点后保留一个空格,并按语义自然分句。"
    else:
        description = "繁體中文 AI 與軟體開發討論逐字稿。常用拼字: "
        instruction = ". 使用半形標點,標點後保留一個空格,並依語意自然分句。"
    return description + ", ".join(TECH_TERMS) + instruction


PROMPT_LEAKAGE_SUFFIXES = (
    r"(?:使用半形標點[,，。.\s]*)?標點後保留一個空格[,，\s]*並依語意自然分句[。.]?",
    r"(?:使用半角标点[,，。.\s]*)?标点后保留一个空格[,，\s]*并按语义自然分句[。.]?",
)


def remove_transcription_prompt_leakage(text):
    """Remove known prompt instructions that Whisper may echo after quiet audio."""
    cleaned = str(text or "").strip()
    for suffix in PROMPT_LEAKAGE_SUFFIXES:
        cleaned = re.sub(
            rf"(?:[\s\"'「」『』]*{suffix}[\s\"'「」『』]*)$",
            "",
            cleaned,
            flags=re.IGNORECASE,
        ).rstrip()
    return cleaned


# Longer or more specific names must run before their shorter forms.
TECH_TERM_CORRECTIONS = (
    (r"(?<![A-Za-z0-9])claude[\s-]*code(?![A-Za-z0-9])", "Claude Code"),
    (r"克[勞洛]德\s*(?:Code|程式碼|代码)", "Claude Code"),
    (r"(?<![A-Za-z0-9])chat[\s-]*gpt(?![A-Za-z0-9])", "ChatGPT"),
    (r"(?<![A-Za-z0-9])open[\s-]*ai(?![A-Za-z0-9])", "OpenAI"),
    (r"(?<![A-Za-z0-9])git[\s-]*hub[\s-]*copilot(?![A-Za-z0-9])", "GitHub Copilot"),
    (r"(?<![A-Za-z0-9])git[\s-]*hub(?![A-Za-z0-9])", "GitHub"),
    (r"(?<![A-Za-z0-9])hugging[\s-]*face(?![A-Za-z0-9])", "Hugging Face"),
    (r"(?<![A-Za-z0-9])deep[\s-]*mind(?![A-Za-z0-9])", "DeepMind"),
    (r"(?<![A-Za-z0-9])visual\s*studio\s*code(?![A-Za-z0-9])", "VS Code"),
    (r"(?<![A-Za-z0-9])vs[\s-]*code(?![A-Za-z0-9])", "VS Code"),
    (r"(?<![A-Za-z0-9])java[\s-]*script(?![A-Za-z0-9])", "JavaScript"),
    (r"(?<![A-Za-z0-9])type[\s-]*script(?![A-Za-z0-9])", "TypeScript"),
    (r"(?<![A-Za-z0-9])next[\s.-]*js(?![A-Za-z0-9])", "Next.js"),
    (r"(?<![A-Za-z0-9])node[\s.-]*js(?![A-Za-z0-9])", "Node.js"),
    (r"(?<![A-Za-z0-9])nvidia(?![A-Za-z0-9])", "NVIDIA"),
    (r"(?<![A-Za-z0-9])x[\s-]*ai(?![A-Za-z0-9])", "xAI"),
    (r"(?<![A-Za-z0-9])groq(?![A-Za-z0-9])", "Groq"),
    (r"(?<![A-Za-z0-9])grok(?![A-Za-z0-9])", "Grok"),
    (r"(?<![A-Za-z0-9])gemini(?![A-Za-z0-9])", "Gemini"),
    (r"(?<![A-Za-z0-9])claude(?![A-Za-z0-9])", "Claude"),
    (r"(?<![A-Za-z0-9])anthropic(?![A-Za-z0-9])", "Anthropic"),
    (r"(?<![A-Za-z0-9])google(?![A-Za-z0-9])", "Google"),
    (r"(?<![A-Za-z0-9])microsoft(?![A-Za-z0-9])", "Microsoft"),
    (r"(?<![A-Za-z0-9])copilot(?![A-Za-z0-9])", "Copilot"),
    (r"(?<![A-Za-z0-9])meta(?![A-Za-z0-9])", "Meta"),
    (r"(?<![A-Za-z0-9])llama(?![A-Za-z0-9])", "Llama"),
    (r"(?<![A-Za-z0-9])mistral(?![A-Za-z0-9])", "Mistral"),
    (r"(?<![A-Za-z0-9])perplexity(?![A-Za-z0-9])", "Perplexity"),
    (r"(?<![A-Za-z0-9])javascript(?![A-Za-z0-9])", "JavaScript"),
    (r"(?<![A-Za-z0-9])typescript(?![A-Za-z0-9])", "TypeScript"),
    (r"(?<![A-Za-z0-9])python(?![A-Za-z0-9])", "Python"),
    (r"(?<![A-Za-z0-9])react(?![A-Za-z0-9])", "React"),
    (r"(?<![A-Za-z0-9])docker(?![A-Za-z0-9])", "Docker"),
    (r"(?<![A-Za-z0-9])kubernetes(?![A-Za-z0-9])", "Kubernetes"),
    (r"(?<![A-Za-z0-9])codex(?![A-Za-z0-9])", "Codex"),
    (r"(?<![A-Za-z0-9])cursor(?![A-Za-z0-9])", "Cursor"),
    (r"(?<![A-Za-z0-9])cuda(?![A-Za-z0-9])", "CUDA"),
    (r"(?<![A-Za-z0-9])quota(?![A-Za-z0-9])", " quota "),
    (r"扣打|扣達|扣达|闊塔|阔塔|庫塔|库塔", " quota "),
    (r"(?<![A-Za-z0-9])api(?![A-Za-z0-9])", "API"),
    (r"(?<![A-Za-z0-9])gpu(?![A-Za-z0-9])", "GPU"),
    (r"(?<![A-Za-z0-9])agi(?![A-Za-z0-9])", "AGI"),
    (r"(?<![A-Za-z0-9])llm(?![A-Za-z0-9])", "LLM"),
    (r"(?<![A-Za-z0-9])ai(?![A-Za-z0-9])", "AI"),
    (r"聊天\s*GPT", "ChatGPT"),
    (r"傑米奈|杰米奈", "Gemini"),
    (r"克[勞洛]德", "Claude"),
    (r"格[羅洛]克|葛洛克", "Groq"),
    (r"輝達|英偉達|英伟达", "NVIDIA"),
)

PUNCTUATION_TRANSLATION = str.maketrans({
    "，": ",",
    "。": ".",
    "、": ",",
    "；": ";",
    "：": ":",
    "！": "!",
    "？": "?",
    "（": "(",
    "）": ")",
})

PHRASE_PAUSE_SECONDS = 0.35
SENTENCE_PAUSE_SECONDS = 0.80
MAX_SENTENCE_CHARACTERS = 90
MAX_SENTENCES_PER_PARAGRAPH = 5


def canonicalize_tech_terms(text):
    for pattern, replacement in TECH_TERM_CORRECTIONS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


def _is_cjk(char):
    return bool(char and "\u3400" <= char <= "\u9fff")


def _field(item, name, default=None):
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def _join_words(left, right):
    right = right.strip()
    if not right:
        return left
    if not left:
        return right
    if right[0] in ",.;:!?)]}":
        return left + right
    if left[-1] in "([{":
        return left + right
    if left[-1] in ",.;:!?" and _is_cjk(right[0]):
        return left + right
    if _is_cjk(left[-1]) and _is_cjk(right[0]):
        return left + right
    return left + " " + right


def _comparable_characters(text):
    return [(char.casefold(), index) for index, char in enumerate(text) if char.isalnum()]


def _punctuate_raw_text_from_words(raw_text, words):
    """Insert pause punctuation into raw text without rebuilding its words."""
    raw_characters = _comparable_characters(raw_text)
    usable_words = []
    word_characters = []

    for word in words or []:
        value = str(_field(word, "word", ""))
        characters = [char.casefold() for char in value if char.isalnum()]
        if not characters:
            continue
        if _field(word, "start") is None or _field(word, "end") is None:
            continue
        usable_words.append((word, characters))
        word_characters.extend(characters)

    if not raw_characters or not usable_words:
        return None
    if [char for char, _ in raw_characters] != word_characters:
        return None

    replacements = {}
    insertions = {}
    consumed_characters = 0
    for index, (word, characters) in enumerate(usable_words[:-1]):
        consumed_characters += len(characters)
        next_word = usable_words[index + 1][0]
        gap = max(0.0, float(_field(next_word, "start")) - float(_field(word, "end")))
        if gap < PHRASE_PAUSE_SECONDS:
            continue

        boundary = raw_characters[consumed_characters - 1][1] + 1
        existing = raw_text[boundary] if boundary < len(raw_text) else ""
        if existing in ",，;；:：":
            if gap >= SENTENCE_PAUSE_SECONDS:
                replacements[boundary] = "."
            continue
        if existing in ".。!?！？":
            continue

        insertions[boundary] = "." if gap >= SENTENCE_PAUSE_SECONDS else ","

    output = raw_text
    for position, replacement in sorted(replacements.items(), reverse=True):
        output = output[:position] + replacement + output[position + 1:]
    for position, punctuation in sorted(insertions.items(), reverse=True):
        output = output[:position] + punctuation + output[position:]
    return output


def punctuate_from_timestamps(raw_text, words=None, segments=None):
    """Add punctuation at measured pauses without rewriting recognized words."""
    word_punctuated_text = _punctuate_raw_text_from_words(raw_text, words)
    if word_punctuated_text is not None:
        return word_punctuated_text

    usable_segments = [
        segment for segment in (segments or [])
        if _field(segment, "text") and _field(segment, "start") is not None and _field(segment, "end") is not None
    ]
    if not usable_segments:
        return raw_text

    rebuilt = ""
    previous_end = None
    for segment in usable_segments:
        piece = str(_field(segment, "text")).strip()
        if previous_end is not None:
            gap = max(0.0, float(_field(segment, "start")) - float(previous_end))
            if gap >= SENTENCE_PAUSE_SECONDS and not rebuilt.endswith((".", "!", "?")):
                rebuilt = rebuilt.rstrip(",;:") + "."
            elif gap >= PHRASE_PAUSE_SECONDS and not rebuilt.endswith((",", ".", ";", ":", "!", "?")):
                rebuilt += ","
        rebuilt = _join_words(rebuilt, piece)
        previous_end = _field(segment, "end")

    raw_characters = [char for char, _ in _comparable_characters(raw_text)]
    rebuilt_characters = [char for char, _ in _comparable_characters(rebuilt)]
    return rebuilt if raw_characters == rebuilt_characters else raw_text


def _limit_sentence_length(text):
    output = []
    count = 0
    for char in text:
        if char in ".!?":
            count = 0
        elif not char.isspace():
            count += 1

        if char == "," and count >= MAX_SENTENCE_CHARACTERS:
            output.append(".")
            count = 0
        else:
            output.append(char)
    return "".join(output)


def _add_paragraph_breaks(text):
    output = []
    sentence_count = 0
    for index, char in enumerate(text):
        output.append(char)
        next_char = text[index + 1] if index + 1 < len(text) else ""
        is_terminal = char in "!?" or (
            char == "." and not (next_char and (next_char.islower() or next_char.isdigit()))
        )
        if not is_terminal:
            continue

        sentence_count += 1
        if sentence_count >= MAX_SENTENCES_PER_PARAGRAPH and next_char:
            output.append("\n\n")
            sentence_count = 0
    return "".join(output)


def _format_half_width_punctuation_spacing(text):
    """Add one readable space after half-width punctuation without damaging tokens."""
    text = re.sub(r"[ \t]+([,.;:!?])", r"\1", text)
    text = re.sub(r"[ \t]+", " ", text)

    output = []
    length = len(text)
    for index, char in enumerate(text):
        output.append(char)
        if char not in ",.;:!?":
            continue

        previous_char = text[index - 1] if index > 0 else ""
        next_char = text[index + 1] if index + 1 < length else ""
        if not next_char or next_char.isspace() or next_char in ",.;:!?)]}":
            continue

        # Preserve numbers, versions, domains, technical names and URL schemes.
        if char == "," and previous_char.isdigit() and next_char.isdigit():
            continue
        if (
            char == "."
            and previous_char.isascii()
            and previous_char.isalnum()
            and next_char.isascii()
            and next_char.isalnum()
        ):
            continue
        if char == ":" and (
            (previous_char.isdigit() and next_char.isdigit()) or next_char == "/"
        ):
            continue

        output.append(" ")

    formatted = "".join(output)
    formatted = re.sub(r"[ \t]*\n[ \t]*", "\n", formatted)
    return formatted.strip()


def normalize_transcription(text):
    """Keep vocabulary intact and use spaced half-width punctuation consistently."""
    if not text:
        return text

    normalized = text.translate(PUNCTUATION_TRANSLATION)
    normalized = canonicalize_tech_terms(normalized)

    # Remove invalid spaces before punctuation first. Consistent spacing after
    # punctuation is applied after sentence and paragraph processing.
    normalized = re.sub(r"\s+([,.;:!?])", r"\1", normalized)
    normalized = re.sub(r"[ \t]+", " ", normalized).strip()
    normalized = _limit_sentence_length(normalized)

    normalized = _add_paragraph_breaks(normalized)
    return _format_half_width_punctuation_spacing(normalized)


def log_info(msg):
    global _LOGGER
    if _LOGGER is None:
        _LOGGER = logging.getLogger("aza_stt")
        _LOGGER.setLevel(logging.INFO)
        _LOGGER.propagate = False
        if not _LOGGER.handlers:
            handler = RotatingFileHandler(
                LOG_FILE_PATH,
                maxBytes=1024 * 1024,
                backupCount=2,
                encoding="utf-8",
            )
            handler.setFormatter(logging.Formatter("%(asctime)s.%(msecs)03d %(message)s", "%Y-%m-%d %H:%M:%S"))
            _LOGGER.addHandler(handler)
    _LOGGER.info(msg)
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}] {msg}", flush=True)

def refresh_windows_path():
    """Read PATH from Windows Registry and update current process PATH."""
    if sys.platform != 'win32' or not winreg:
        return

    paths = []
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as key:
            user_path, _ = winreg.QueryValueEx(key, "Path")
            paths.extend(user_path.split(';'))
    except:
        pass

    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment") as key:
            sys_path, _ = winreg.QueryValueEx(key, "Path")
            paths.extend(sys_path.split(';'))
    except:
        pass

    seen = set()
    cleaned_paths = []
    for p in paths:
        p = os.path.expandvars(p.strip())
        if p and p not in seen:
            seen.add(p)
            cleaned_paths.append(p)

    current_paths = os.environ.get("PATH", "").split(';')
    for p in current_paths:
        p = p.strip()
        if p and p not in seen:
            seen.add(p)
            cleaned_paths.append(p)

    os.environ["PATH"] = ';'.join(cleaned_paths)

def check_ffmpeg_available():
    try:
        refresh_windows_path()
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, startupinfo=startupinfo, check=True)
        return True
    except:
        return False

def compress_to_flac(wav_path, flac_path):
    started_at = time.perf_counter()
    source_size = os.path.getsize(wav_path)
    try:
        if sf is not None:
            with sf.SoundFile(wav_path, "r") as source:
                with sf.SoundFile(
                    flac_path,
                    "w",
                    samplerate=source.samplerate,
                    channels=source.channels,
                    format="FLAC",
                    subtype="PCM_16",
                ) as destination:
                    while True:
                        block = source.read(65536, dtype="int16", always_2d=True)
                        if len(block) == 0:
                            break
                        destination.write(block)
            encoder = "bundled libsndfile"
        elif check_ffmpeg_available():
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            subprocess.run([
                "ffmpeg", "-y", "-i", wav_path,
                "-ar", str(RATE), "-ac", str(CHANNELS), "-c:a", "flac",
                flac_path
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, startupinfo=startupinfo, check=True)
            encoder = "FFmpeg fallback"
        else:
            raise RuntimeError("No FLAC encoder is available.")

        compressed_size = os.path.getsize(flac_path)
        if compressed_size <= 0:
            raise RuntimeError("The FLAC encoder produced an empty file.")

        elapsed = time.perf_counter() - started_at
        reduction = 100.0 * (1.0 - (compressed_size / source_size))
        log_info(
            f"FLAC compression success via {encoder}: "
            f"{source_size} -> {compressed_size} bytes "
            f"({reduction:.1f}% smaller), elapsed: {elapsed:.2f}s"
        )
        return True
    except Exception as e:
        log_info(f"FLAC compression failed: {e}")
        if os.path.exists(flac_path):
            try:
                os.remove(flac_path)
            except OSError:
                pass
        return False


def run_flac_self_test():
    wav_path = None
    flac_path = None
    try:
        fd, wav_path = tempfile.mkstemp(prefix="aza_stt_self_test_", suffix=".wav")
        os.close(fd)
        flac_path = os.path.splitext(wav_path)[0] + ".flac"
        with wave.open(wav_path, "wb") as wav_file:
            wav_file.setnchannels(CHANNELS)
            wav_file.setsampwidth(2)
            wav_file.setframerate(RATE)
            wav_file.writeframes(b"\x00\x00" * RATE)

        if not compress_to_flac(wav_path, flac_path):
            return False
        with open(flac_path, "rb") as flac_file:
            return flac_file.read(4) == b"fLaC"
    except Exception as e:
        log_info(f"FLAC self-test failed: {e}")
        return False
    finally:
        for path in (wav_path, flac_path):
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass


# Settings
KEY_FILE_PATH = os.path.join(APP_DIR, "dictate_settings.conf")

FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1024
DEFAULT_RECORD_KEY = "menu"
DEFAULT_ACTIVATION_MODE = "double_press"
ACTIVATION_MODES = ("double_press", "single_press", "hold")
MOUSE_TRIGGER_PREFIX = "mouse:"
API_TIMEOUT_SECONDS = 30.0
# The recorder already captures Groq's preferred 16 kHz mono audio. Keeping
# short recordings as WAV avoids encoder startup latency; 8 MiB is about
# 4 minutes 22 seconds at 16-bit PCM and leaves ample room below the free-tier
# direct-upload limit before lossless compression is needed.
FLAC_THRESHOLD_BYTES = 8 * 1024 * 1024
MICROPHONE_START_TIMEOUT_SECONDS = 5.0


def parse_api_keys(content):
    uncommented = "\n".join(
        line.split("#", 1)[0]
        for line in (content or "").splitlines()
    )
    return [
        key.strip()
        for key in re.split(r"[\n\r,;\s]+", uncommented)
        if key.strip()
    ]


def valid_api_keys(keys):
    return bool(keys) and all(key.startswith("gsk_") and len(key) >= 20 for key in keys)


def normalize_record_key(key):
    normalized = str(key or "").strip().lower().replace("_", " ")
    aliases = {
        "apps": "menu",
        "application": "menu",
        "pgup": "page up",
        "pgdn": "page down",
        "pageup": "page up",
        "pagedown": "page down",
        "prtscn": "print screen",
        "mouse:x": "mouse:x1",
        "mouse:back": "mouse:x1",
        "mouse:forward": "mouse:x2",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized in ("mouse:x1", "mouse:x2"):
        return normalized
    if not normalized or normalized.startswith(MOUSE_TRIGGER_PREFIX):
        return None
    try:
        keyboard.key_to_scan_codes(normalized)
        return normalized
    except (ValueError, KeyError):
        return None


def normalize_activation_mode(mode):
    normalized = str(mode or "").strip().lower()
    return normalized if normalized in ACTIVATION_MODES else DEFAULT_ACTIVATION_MODE


def display_record_key(key, language_mode=LANGUAGE_TRADITIONAL):
    normalized = normalize_record_key(key) or DEFAULT_RECORD_KEY
    if normalized == "mouse:x1":
        return ui_text("滑鼠側鍵 1 (上一頁)", language_mode)
    if normalized == "mouse:x2":
        return ui_text("滑鼠側鍵 2 (下一頁)", language_mode)
    if normalized.startswith("f") and normalized[1:].isdigit():
        return normalized.upper()
    return {
        "menu": "Menu",
        "page up": "Page Up",
        "page down": "Page Down",
        "print screen": "Print Screen",
        "scroll lock": "Scroll Lock",
    }.get(normalized, normalized.title())


def display_activation_mode(mode, language_mode=LANGUAGE_TRADITIONAL):
    return ui_text({
        "double_press": "連按兩下開始,按一下停止",
        "single_press": "按一下開始,再按一下停止",
        "hold": "按住時錄音,放開停止",
    }[normalize_activation_mode(mode)], language_mode)


def repair_microphone_name(name):
    """Repair Traditional Chinese device names mangled by PortAudio's ANSI API."""
    raw_name = str(name or "").strip()
    if not raw_name:
        return "未命名麥克風"
    try:
        repaired = raw_name.encode("latin1").decode("cp950").strip()
    except (UnicodeEncodeError, UnicodeDecodeError):
        return raw_name
    return repaired or raw_name


def normalize_microphone_name(name):
    normalized = str(name or "").strip()
    return normalized or None


def display_microphone_name(name, language_mode=LANGUAGE_TRADITIONAL):
    return ui_text(normalize_microphone_name(name) or "系統預設", language_mode)


def _load_user_settings(path):
    defaults = {
        "record_key": DEFAULT_RECORD_KEY,
        "activation_mode": DEFAULT_ACTIVATION_MODE,
        "microphone_name": None,
        "language_mode": detect_default_language_mode(),
    }
    try:
        if not os.path.exists(path):
            return defaults
        with open(path, "r", encoding="utf-8") as file:
            settings = json.load(file)
        return {
            "record_key": (
                normalize_record_key(settings.get("record_key"))
                or DEFAULT_RECORD_KEY
            ),
            "activation_mode": normalize_activation_mode(
                settings.get("activation_mode")
            ),
            "microphone_name": normalize_microphone_name(
                settings.get("microphone_name")
            ),
            "language_mode": (
                normalize_language_mode(settings.get("language_mode"))
                or detect_default_language_mode()
            ),
        }
    except (OSError, ValueError, TypeError) as error:
        log_info(f"Failed to load user settings: {error}")
        return defaults


def load_user_input_settings(path=USER_SETTINGS_FILE_PATH):
    settings = _load_user_settings(path)
    return settings["record_key"], settings["activation_mode"]


def load_user_record_key(path=USER_SETTINGS_FILE_PATH):
    return load_user_input_settings(path)[0]


def load_user_microphone_selection(path=USER_SETTINGS_FILE_PATH):
    return _load_user_settings(path)["microphone_name"]


def load_user_language_mode(path=USER_SETTINGS_FILE_PATH):
    return _load_user_settings(path)["language_mode"]


def _save_user_settings(
    record_key,
    activation_mode,
    microphone_name,
    language_mode,
    path,
):
    normalized = normalize_record_key(record_key)
    if not normalized:
        raise ValueError("Unsupported recording key.")
    normalized_mode = normalize_activation_mode(activation_mode)
    normalized_microphone = normalize_microphone_name(microphone_name)
    normalized_language = (
        normalize_language_mode(language_mode)
        or detect_default_language_mode()
    )
    settings_dir = os.path.dirname(path)
    if settings_dir:
        os.makedirs(settings_dir, exist_ok=True)
    temp_path = path + ".tmp"
    with open(temp_path, "w", encoding="utf-8", newline="\n") as file:
        json.dump(
            {
                "record_key": normalized,
                "activation_mode": normalized_mode,
                "microphone_name": normalized_microphone,
                "language_mode": normalized_language,
            },
            file,
            ensure_ascii=False,
            indent=2,
        )
        file.write("\n")
    os.replace(temp_path, path)
    return (
        normalized,
        normalized_mode,
        normalized_microphone,
        normalized_language,
    )


def save_user_input_settings(
    record_key,
    activation_mode=DEFAULT_ACTIVATION_MODE,
    path=USER_SETTINGS_FILE_PATH,
):
    current = _load_user_settings(path)
    normalized, normalized_mode, _, _ = _save_user_settings(
        record_key,
        activation_mode,
        current["microphone_name"],
        current["language_mode"],
        path,
    )
    return normalized, normalized_mode


def save_user_record_key(record_key, path=USER_SETTINGS_FILE_PATH):
    return save_user_input_settings(record_key, DEFAULT_ACTIVATION_MODE, path)[0]


def save_user_microphone_selection(
    microphone_name,
    path=USER_SETTINGS_FILE_PATH,
):
    current = _load_user_settings(path)
    _, _, normalized_microphone, _ = _save_user_settings(
        current["record_key"],
        current["activation_mode"],
        microphone_name,
        current["language_mode"],
        path,
    )
    return normalized_microphone


def save_user_language_mode(
    language_mode,
    path=USER_SETTINGS_FILE_PATH,
):
    current = _load_user_settings(path)
    _, _, _, normalized_language = _save_user_settings(
        current["record_key"],
        current["activation_mode"],
        current["microphone_name"],
        language_mode,
        path,
    )
    return normalized_language


def enumerate_input_devices(audio):
    default_index = None
    try:
        default_index = int(audio.get_default_input_device_info()["index"])
    except (IOError, OSError, KeyError, TypeError, ValueError):
        pass

    devices = []
    for index in range(audio.get_device_count()):
        try:
            info = audio.get_device_info_by_index(index)
            if int(info.get("maxInputChannels", 0)) < 1:
                continue
            host_index = int(info.get("hostApi", -1))
            host_info = audio.get_host_api_info_by_index(host_index)
            devices.append(
                {
                    "index": index,
                    "name": repair_microphone_name(info.get("name")),
                    "raw_name": str(info.get("name") or ""),
                    "host_api": str(host_info.get("name") or ""),
                    "host_type": int(host_info.get("type", -1)),
                    "is_default": index == default_index,
                }
            )
        except (IOError, OSError, KeyError, TypeError, ValueError):
            continue
    return devices


def list_microphone_choices(audio=None):
    owns_audio = audio is None
    if owns_audio:
        audio = pyaudio.PyAudio()
    try:
        choices = []
        seen = set()
        for device in enumerate_input_devices(audio):
            name = device["name"]
            if name.casefold().startswith("microsoft sound mapper"):
                continue
            key = name.casefold()
            if key not in seen:
                choices.append(name)
                seen.add(key)
        return choices
    finally:
        if owns_audio:
            audio.terminate()


def microphone_device_candidates(audio, microphone_name=None):
    devices = enumerate_input_devices(audio)
    selected = normalize_microphone_name(microphone_name)
    host_priority = {
        getattr(pyaudio, "paMME", 2): 0,
        getattr(pyaudio, "paDirectSound", 1): 1,
        getattr(pyaudio, "paWASAPI", 13): 2,
        getattr(pyaudio, "paWDMKS", 11): 3,
    }

    def order(device):
        return (
            0 if device["is_default"] else 1,
            host_priority.get(device["host_type"], 9),
            device["index"],
        )

    selected_devices = []
    if selected:
        selected_devices = [
            device
            for device in devices
            if device["name"].casefold() == selected.casefold()
        ]
    default_devices = [device for device in devices if device["is_default"]]
    remaining = [
        device
        for device in devices
        if device not in selected_devices and device not in default_devices
    ]
    return (
        sorted(selected_devices, key=order)
        + sorted(default_devices, key=order)
        + sorted(remaining, key=order)
    )


def open_microphone_stream(audio, microphone_name=None):
    candidates = microphone_device_candidates(audio, microphone_name)
    if not candidates:
        raise RuntimeError("Windows 找不到任何可用的麥克風。")

    errors = []
    for device in candidates:
        try:
            stream = audio.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                input_device_index=device["index"],
                frames_per_buffer=CHUNK,
            )
            return stream, device
        except Exception as error:
            errors.append(f'{device["name"]}: {error}')
    raise RuntimeError(
        "無法開啟任何麥克風。"
        + (f" 最後錯誤: {errors[-1]}" if errors else "")
    )


def save_user_api_keys(keys):
    os.makedirs(APP_DATA_DIR, exist_ok=True)
    temp_path = USER_KEY_FILE_PATH + ".tmp"
    with open(temp_path, "w", encoding="utf-8", newline="\n") as file:
        file.write("\n".join(keys) + "\n")
    os.replace(temp_path, USER_KEY_FILE_PATH)

    if sys.platform == "win32":
        identity = f"{os.environ.get('USERDOMAIN', '.')}\\" f"{os.environ.get('USERNAME', '')}"
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            subprocess.run(
                [
                    "icacls",
                    USER_KEY_FILE_PATH,
                    "/inheritance:r",
                    "/grant:r",
                    f"{identity}:(F)",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                startupinfo=startupinfo,
                check=True,
            )
        except Exception as error:
            log_info(f"Could not restrict API key file permissions: {error}")


def open_groq_keys_page():
    return webbrowser.open_new_tab(GROQ_KEYS_URL)


class ApiKeySetupDialog(simpledialog.Dialog):
    def __init__(self, parent, language_mode=LANGUAGE_TRADITIONAL):
        self.language_mode = (
            normalize_language_mode(language_mode) or LANGUAGE_TRADITIONAL
        )
        super().__init__(parent, title=self.ui("AZA-STT 設定"))

    def ui(self, text):
        return ui_text(text, self.language_mode)

    def body(self, master):
        self.title(self.ui("AZA-STT 設定"))
        tk.Label(
            master,
            text=self.ui("請貼上 Groq API key"),
            font=("Segoe UI", 11, "bold"),
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))
        tk.Label(
            master,
            text=self.ui(
                "多組 key 可使用逗號、分號或空格分隔。\n"
                "如果還沒有 key，請點下方按鈕前往 Groq 申請。"
            ),
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(0, 8))
        self.key_entry = tk.Entry(master, width=58, show="*")
        self.key_entry.grid(row=2, column=0, sticky="ew", pady=(0, 6))
        tk.Label(
            master,
            text=self.ui(f"只會儲存在這台電腦：\n{USER_KEY_FILE_PATH}"),
            justify="left",
            fg="#555555",
        ).grid(row=3, column=0, sticky="w")
        master.grid_columnconfigure(0, weight=1)
        return self.key_entry

    def buttonbox(self):
        box = tk.Frame(self)
        tk.Button(
            box,
            text=self.ui("開啟 Groq API Keys"),
            command=self.open_keys_page,
        ).pack(side="left", padx=(0, 18))
        tk.Button(
            box,
            text=self.ui("儲存"),
            width=10,
            command=self.ok,
            default=tk.ACTIVE,
        ).pack(side="left", padx=5)
        tk.Button(
            box,
            text=self.ui("取消"),
            width=10,
            command=self.cancel,
        ).pack(side="left", padx=5)
        self.bind("<Return>", self.ok)
        self.bind("<Escape>", self.cancel)
        box.pack(pady=(8, 10))

    def open_keys_page(self):
        try:
            if not open_groq_keys_page():
                raise RuntimeError("Windows did not open the browser.")
        except Exception as error:
            messagebox.showerror(
                "AZA-STT",
                self.ui(f"無法開啟 Groq 網頁：\n{error}\n\n{GROQ_KEYS_URL}"),
                parent=self,
            )

    def validate(self):
        keys = parse_api_keys(self.key_entry.get())
        if not valid_api_keys(keys):
            messagebox.showerror(
                "AZA-STT",
                self.ui("API key 格式不正確。Groq API key 應以 gsk_ 開頭。"),
                parent=self,
            )
            return False
        self.validated_keys = keys
        return True

    def apply(self):
        self.result = self.validated_keys


class RecordKeySetupDialog(simpledialog.Dialog):
    def __init__(
        self,
        parent,
        current_key,
        current_mode,
        language_mode=LANGUAGE_TRADITIONAL,
    ):
        self.language_mode = (
            normalize_language_mode(language_mode) or LANGUAGE_TRADITIONAL
        )
        self.current_key = normalize_record_key(current_key) or DEFAULT_RECORD_KEY
        self.selected_key = self.current_key
        self.current_mode = normalize_activation_mode(current_mode)
        self.capture_keyboard_hook = None
        self.capture_mouse_listener = None
        self.capture_queue = queue.Queue()
        self.capture_poll_id = None
        super().__init__(parent, title=self.ui("AZA-STT 錄音控制"))

    def ui(self, text):
        return ui_text(text, self.language_mode)

    def body(self, master):
        tk.Label(
            master,
            text=self.ui("設定錄音控制"),
            font=("Segoe UI", 11, "bold"),
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))
        tk.Label(
            master,
            text=self.ui(
                "可以使用任何鍵盤按鍵,也可以使用滑鼠側鍵。\n"
                "選中的按鍵會由 AZA-STT 攔截,原本功能可能無法使用。"
            ),
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(0, 10))

        self.selected_var = tk.StringVar(
            value=self.ui(
                f"目前按鍵: "
                f"{display_record_key(self.selected_key, self.language_mode)}"
            )
        )
        tk.Label(
            master,
            textvariable=self.selected_var,
            font=("Segoe UI", 11),
            fg="#1D4ED8",
        ).grid(row=2, column=0, sticky="w", pady=(0, 8))

        self.capture_button = tk.Button(
            master,
            text=self.ui("按下新的鍵盤鍵或滑鼠側鍵"),
            width=28,
            command=self.begin_capture,
        )
        self.capture_button.grid(row=3, column=0, sticky="w")

        self.capture_status_var = tk.StringVar(value="")
        tk.Label(
            master,
            textvariable=self.capture_status_var,
            justify="left",
            fg="#555555",
        ).grid(row=4, column=0, sticky="w", pady=(6, 10))

        mode_box = tk.LabelFrame(
            master,
            text=self.ui("錄音方式"),
            padx=10,
            pady=6,
        )
        mode_box.grid(row=5, column=0, sticky="ew")
        self.mode_var = tk.StringVar(value=self.current_mode)
        for mode in ACTIVATION_MODES:
            tk.Radiobutton(
                mode_box,
                text=display_activation_mode(mode, self.language_mode),
                variable=self.mode_var,
                value=mode,
                anchor="w",
            ).pack(fill="x", anchor="w")

        master.grid_columnconfigure(0, weight=1)
        return self.capture_button

    def buttonbox(self):
        box = tk.Frame(self)
        tk.Button(
            box,
            text=self.ui("恢復預設"),
            command=self.select_default,
        ).pack(side="left", padx=(0, 18))
        tk.Button(
            box,
            text=self.ui("儲存"),
            width=10,
            command=self.ok,
            default=tk.ACTIVE,
        ).pack(side="left", padx=5)
        tk.Button(
            box,
            text=self.ui("取消"),
            width=10,
            command=self.cancel,
        ).pack(side="left", padx=5)
        self.bind("<Return>", self.ok)
        self.bind("<Escape>", self.cancel)
        box.pack(pady=(12, 10))

    def begin_capture(self):
        self.stop_capture()
        self.capture_status_var.set(self.ui("等待鍵盤按鍵或滑鼠側鍵中…"))
        self.capture_button.config(state=tk.DISABLED)
        try:
            self.capture_keyboard_hook = keyboard.hook(
                self.capture_keyboard_event,
                suppress=True,
            )
            self.capture_mouse_listener = pynput_mouse.Listener(
                on_click=self.capture_mouse_event,
                win32_event_filter=self.capture_mouse_filter,
            )
            self.capture_mouse_listener.start()
        except Exception as error:
            self.stop_capture()
            self.capture_status_var.set(
                self.ui(f"無法開始偵測輸入: {error}")
            )
            return
        self.capture_poll_id = self.after(50, self.poll_capture_queue)

    def capture_keyboard_event(self, event):
        if event.event_type == keyboard.KEY_DOWN and event.name:
            self.capture_queue.put(event.name)

    def capture_mouse_event(self, x, y, button, pressed, injected=False):
        if not pressed:
            return
        if button == pynput_mouse.Button.x1:
            self.capture_queue.put("mouse:x1")
        elif button == pynput_mouse.Button.x2:
            self.capture_queue.put("mouse:x2")

    def capture_mouse_filter(self, msg, data):
        if msg in (
            pynput_mouse.Listener.WM_XBUTTONDOWN,
            pynput_mouse.Listener.WM_XBUTTONUP,
        ):
            button_id = (int(data.mouseData) >> 16) & 0xFFFF
            if button_id in (
                pynput_mouse.Listener.XBUTTON1,
                pynput_mouse.Listener.XBUTTON2,
            ):
                self.capture_mouse_listener.suppress_event()
        return True

    def poll_capture_queue(self):
        self.capture_poll_id = None
        try:
            key = self.capture_queue.get_nowait()
        except queue.Empty:
            if (
                self.capture_keyboard_hook is not None
                or self.capture_mouse_listener is not None
            ):
                self.capture_poll_id = self.after(50, self.poll_capture_queue)
            return

        self.stop_capture()
        normalized = normalize_record_key(key)
        if not normalized:
            self.capture_status_var.set(
                self.ui(f"無法辨識「{key}」,請再試一次。")
            )
            return
        self.selected_key = normalized
        self.selected_var.set(
            self.ui(
                f"新按鍵: "
                f"{display_record_key(normalized, self.language_mode)}"
            )
        )
        self.capture_status_var.set(
            self.ui("按「儲存」後立即生效,不需要重新啟動。")
        )

    def select_default(self):
        self.stop_capture()
        self.selected_key = DEFAULT_RECORD_KEY
        self.mode_var.set(DEFAULT_ACTIVATION_MODE)
        self.selected_var.set(self.ui("新按鍵: Menu"))
        self.capture_status_var.set(
            self.ui("已恢復預設按鍵與錄音方式。")
        )

    def stop_capture(self):
        if self.capture_poll_id is not None:
            self.after_cancel(self.capture_poll_id)
            self.capture_poll_id = None
        if self.capture_keyboard_hook is not None:
            try:
                keyboard.unhook(self.capture_keyboard_hook)
            except (KeyError, ValueError):
                pass
            self.capture_keyboard_hook = None
        if self.capture_mouse_listener is not None:
            try:
                self.capture_mouse_listener.stop()
                self.capture_mouse_listener.join(timeout=1)
            except (RuntimeError, OSError):
                pass
            self.capture_mouse_listener = None
        if hasattr(self, "capture_button"):
            self.capture_button.config(state=tk.NORMAL)

    def apply(self):
        self.stop_capture()
        self.result = (
            self.selected_key,
            normalize_activation_mode(self.mode_var.get()),
        )

    def cancel(self, event=None):
        self.stop_capture()
        super().cancel(event)


class MicrophoneSetupDialog(simpledialog.Dialog):
    SYSTEM_DEFAULT_LABEL = "系統預設 (建議)"

    def __init__(
        self,
        parent,
        current_microphone,
        language_mode=LANGUAGE_TRADITIONAL,
    ):
        self.language_mode = (
            normalize_language_mode(language_mode) or LANGUAGE_TRADITIONAL
        )
        self.current_microphone = normalize_microphone_name(current_microphone)
        self.choice_map = {}
        super().__init__(parent, title=self.ui("AZA-STT 麥克風"))

    def ui(self, text):
        return ui_text(text, self.language_mode)

    def body(self, master):
        tk.Label(
            master,
            text=self.ui("選擇錄音麥克風"),
            font=("Segoe UI", 11, "bold"),
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        tk.Label(
            master,
            text=self.ui(
                "建議保留「系統預設」。如果指定的裝置拔除或失效,\n"
                "AZA-STT 會自動改用其他可用的麥克風。"
            ),
            justify="left",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 10))

        self.microphone_var = tk.StringVar()
        self.microphone_combo = ttk.Combobox(
            master,
            textvariable=self.microphone_var,
            state="readonly",
            width=48,
        )
        self.microphone_combo.grid(row=2, column=0, sticky="ew", padx=(0, 8))
        tk.Button(
            master,
            text=self.ui("重新掃描"),
            command=self.refresh_choices,
        ).grid(row=2, column=1, sticky="e")

        self.status_var = tk.StringVar(value="")
        tk.Label(
            master,
            textvariable=self.status_var,
            justify="left",
            fg="#555555",
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(6, 0))
        master.grid_columnconfigure(0, weight=1)
        self.refresh_choices()
        return self.microphone_combo

    def refresh_choices(self):
        self.status_var.set(self.ui("正在掃描麥克風…"))
        self.update_idletasks()
        try:
            microphones = list_microphone_choices()
        except Exception as error:
            microphones = []
            self.status_var.set(
                self.ui(f"無法讀取麥克風清單: {error}")
            )
        else:
            self.status_var.set(
                self.ui(f"找到 {len(microphones)} 個麥克風。")
            )

        system_default_label = self.ui(self.SYSTEM_DEFAULT_LABEL)
        self.choice_map = {system_default_label: None}
        for microphone in microphones:
            self.choice_map[self.ui(microphone)] = microphone

        selected_label = system_default_label
        if self.current_microphone:
            localized_current = self.ui(self.current_microphone)
            if localized_current not in self.choice_map:
                missing_label = self.ui(
                    f"{self.current_microphone} (目前找不到)"
                )
                self.choice_map[missing_label] = self.current_microphone
                selected_label = missing_label
            else:
                selected_label = localized_current

        values = list(self.choice_map)
        self.microphone_combo.configure(values=values)
        self.microphone_var.set(selected_label)

    def buttonbox(self):
        box = tk.Frame(self)
        tk.Button(
            box,
            text=self.ui("儲存"),
            width=10,
            command=self.ok,
            default=tk.ACTIVE,
        ).pack(side="left", padx=5)
        tk.Button(
            box,
            text=self.ui("取消"),
            width=10,
            command=self.cancel,
        ).pack(side="left", padx=5)
        self.bind("<Return>", self.ok)
        self.bind("<Escape>", self.cancel)
        box.pack(pady=(12, 10))

    def apply(self):
        self.result = (self.choice_map.get(self.microphone_var.get()),)


class LanguageSetupDialog(simpledialog.Dialog):
    def __init__(self, parent, current_language):
        self.current_language = (
            normalize_language_mode(current_language)
            or LANGUAGE_TRADITIONAL
        )
        super().__init__(parent, title="AZA-STT 語言 / 语言")

    def ui(self, text):
        return ui_text(text, self.current_language)

    def body(self, master):
        tk.Label(
            master,
            text="語言與輸出 / 语言与输出",
            font=("Segoe UI", 11, "bold"),
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))
        tk.Label(
            master,
            text=self.ui(
                "切換後,設定介面、通知區選單與辨識結果會一起變更。"
            ),
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(0, 10))
        self.language_var = tk.StringVar(value=self.current_language)
        tk.Radiobutton(
            master,
            text="繁體中文",
            variable=self.language_var,
            value=LANGUAGE_TRADITIONAL,
            anchor="w",
        ).grid(row=2, column=0, sticky="w")
        tk.Radiobutton(
            master,
            text="简体中文",
            variable=self.language_var,
            value=LANGUAGE_SIMPLIFIED,
            anchor="w",
        ).grid(row=3, column=0, sticky="w")
        master.grid_columnconfigure(0, weight=1)
        return None

    def buttonbox(self):
        box = tk.Frame(self)
        tk.Button(
            box,
            text=self.ui("儲存"),
            width=10,
            command=self.ok,
            default=tk.ACTIVE,
        ).pack(side="left", padx=5)
        tk.Button(
            box,
            text=self.ui("取消"),
            width=10,
            command=self.cancel,
        ).pack(side="left", padx=5)
        self.bind("<Return>", self.ok)
        self.bind("<Escape>", self.cancel)
        box.pack(pady=(12, 10))

    def apply(self):
        self.result = normalize_language_mode(self.language_var.get())


def prompt_for_api_keys(parent=None, language_mode=None):
    language_mode = (
        normalize_language_mode(language_mode)
        or load_user_language_mode()
    )
    owns_root = parent is None
    dialog_parent = parent
    if owns_root:
        dialog_parent = tk.Tk()
        dialog_parent.withdraw()
        dialog_parent.attributes("-topmost", True)

    try:
        dialog = ApiKeySetupDialog(dialog_parent, language_mode=language_mode)
        keys = dialog.result or []
        if not keys:
            return []

        try:
            save_user_api_keys(keys)
        except Exception as error:
            messagebox.showerror(
                "AZA-STT",
                ui_text(f"無法儲存 API key：\n{error}", language_mode),
                parent=dialog_parent,
            )
            return []

        messagebox.showinfo(
            "AZA-STT",
            ui_text("Groq API key 已儲存。", language_mode),
            parent=dialog_parent,
        )
        return keys
    finally:
        if owns_root:
            dialog_parent.destroy()


def acquire_single_instance():
    """Return a Windows mutex handle, or None when another copy is running."""
    if sys.platform != "win32":
        return True
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = (ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p)
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
    kernel32.CloseHandle.restype = ctypes.c_bool

    handle = kernel32.CreateMutexW(None, False, "Local\\AZA_STT")
    if not handle:
        return None
    if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
        kernel32.CloseHandle(handle)
        return None
    return handle


def release_single_instance(handle):
    if sys.platform == "win32" and handle:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
        kernel32.CloseHandle.restype = ctypes.c_bool
        kernel32.CloseHandle(handle)


def create_tray_image(status="idle", size=64):
    """Create a compact AZA-STT microphone icon for the Windows notification area."""
    if Image is None or ImageDraw is None:
        return None

    colors = {
        "idle": "#2563EB",
        "recording": "#EF4444",
        "processing": "#F59E0B",
        "success": "#22C55E",
        "error": "#6B7280",
    }
    accent = colors.get(status, colors["idle"])
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    margin = max(2, size // 16)
    radius = max(6, size // 5)
    draw.rounded_rectangle(
        (margin, margin, size - margin - 1, size - margin - 1),
        radius=radius,
        fill="#111827",
        outline=accent,
        width=max(2, size // 16),
    )

    # A font-free microphone mark stays sharp even at 16x16 tray size.
    mic_left = int(size * 0.38)
    mic_top = int(size * 0.22)
    mic_right = int(size * 0.62)
    mic_bottom = int(size * 0.58)
    stroke = max(2, size // 16)
    draw.rounded_rectangle(
        (mic_left, mic_top, mic_right, mic_bottom),
        radius=max(3, size // 10),
        fill=accent,
    )
    draw.arc(
        (int(size * 0.29), int(size * 0.34), int(size * 0.71), int(size * 0.72)),
        start=0,
        end=180,
        fill="white",
        width=stroke,
    )
    draw.line(
        (size // 2, int(size * 0.70), size // 2, int(size * 0.80)),
        fill="white",
        width=stroke,
    )
    draw.line(
        (int(size * 0.39), int(size * 0.81), int(size * 0.61), int(size * 0.81)),
        fill="white",
        width=stroke,
    )
    return image


def run_tray_self_test(timeout_seconds=5):
    """Exercise the packaged Windows notification-area backend without starting the app."""
    if pystray is None:
        log_info("Tray self-test failed: pystray or Pillow is unavailable.")
        return False

    ready = Event()
    icon = pystray.Icon(
        "AZA-STT Self Test",
        create_tray_image(),
        "AZA-STT notification area self-test",
        pystray.Menu(pystray.MenuItem("測試中", lambda *_: None)),
    )

    def mark_ready(active_icon):
        active_icon.visible = True
        ready.set()

    tray_thread = threading.Thread(
        target=lambda: icon.run(setup=mark_ready),
        name="AZA-STT Tray Self Test",
        daemon=True,
    )
    tray_thread.start()
    if not ready.wait(timeout_seconds):
        icon.stop()
        log_info("Tray self-test failed: notification area icon did not become ready.")
        return False

    try:
        icon.icon = create_tray_image("recording")
        icon.update_menu()
    finally:
        icon.stop()
        tray_thread.join(timeout=timeout_seconds)

    passed = not tray_thread.is_alive()
    log_info(f"Tray self-test {'passed' if passed else 'failed'}.")
    return passed


def run_hotkey_self_test():
    """Confirm packaged keyboard and mouse backends can bind and stop cleanly."""
    hooks = []
    mouse_listener = None
    try:
        hooks = [
            keyboard.on_press_key("f12", lambda event: None, suppress=True),
            keyboard.on_release_key("f12", lambda event: None, suppress=True),
        ]
        mouse_listener = pynput_mouse.Listener(
            on_click=lambda x, y, button, pressed, injected=False: None,
        )
        mouse_listener.start()
        time.sleep(0.1)
        if not mouse_listener.running:
            raise RuntimeError("Mouse listener did not start.")
        log_info("Recording-control self-test passed.")
        return True
    except Exception as error:
        log_info(f"Recording-control self-test failed: {error}")
        return False
    finally:
        for hook in hooks:
            try:
                keyboard.unhook(hook)
            except (KeyError, ValueError):
                pass
        if mouse_listener is not None:
            try:
                mouse_listener.stop()
                mouse_listener.join(timeout=1)
            except (RuntimeError, OSError):
                pass


def run_microphone_self_test():
    """Open and read the selected microphone without saving or uploading audio."""
    audio = None
    stream = None
    try:
        audio = pyaudio.PyAudio()
        selected = load_user_microphone_selection()
        stream, device = open_microphone_stream(audio, selected)
        captured_bytes = sum(
            len(stream.read(CHUNK, exception_on_overflow=False))
            for _ in range(5)
        )
        log_info(
            f'Microphone self-test passed: "{device["name"]}", '
            f"{captured_bytes} bytes."
        )
        return captured_bytes > 0
    except Exception as error:
        log_info(f"Microphone self-test failed: {error}")
        return False
    finally:
        if stream is not None:
            try:
                stream.stop_stream()
                stream.close()
            except Exception:
                pass
        if audio is not None:
            audio.terminate()


def run_language_self_test():
    try:
        simplified_ui = ui_text(
            "程式會縮到通知區,可設定滑鼠與麥克風裝置。",
            LANGUAGE_SIMPLIFIED,
        )
        expected_terms = ("程序", "系统托盘", "鼠标", "麦克风", "设备")
        if not all(term in simplified_ui for term in expected_terms):
            raise RuntimeError(f"Simplified UI conversion mismatch: {simplified_ui}")

        simplified_converter = opencc.OpenCC("t2s")
        if simplified_converter.convert("這是腳本") != "这是脚本":
            raise RuntimeError("Simplified transcription conversion failed.")
        if "简体中文" not in transcription_prompt(LANGUAGE_SIMPLIFIED):
            raise RuntimeError("Simplified transcription prompt is missing.")
        if "繁體中文" not in transcription_prompt(LANGUAGE_TRADITIONAL):
            raise RuntimeError("Traditional transcription prompt is missing.")

        log_info("Language self-test passed.")
        return True
    except Exception as error:
        log_info(f"Language self-test failed: {error}")
        return False


class GroqDictateApp:
    def __init__(self, instance_handle=None):
        self.instance_handle = instance_handle
        self.language_mode = load_user_language_mode()
        self.record_key, self.activation_mode = load_user_input_settings()
        self.microphone_name = load_user_microphone_selection()
        self.active_microphone_name = None
        self.api_keys = self.load_api_keys()
        if not self.api_keys:
            log_info("No API keys found. Opening first-run setup.")
            self.api_keys = prompt_for_api_keys(
                language_mode=self.language_mode
            )
            if not self.api_keys:
                log_info("API key setup was cancelled.")
                sys.exit(1)

        self.current_key_index = 0
        self.models = ["whisper-large-v3", "whisper-large-v3-turbo"]
        self.current_model_index = 0
        self.client = Groq(api_key=self.api_keys[self.current_key_index], timeout=API_TIMEOUT_SECONDS)
        log_info(f"Groq API client initialized with key #{self.current_key_index + 1}")
        self.converter = None
        self.set_output_converter()

        self.frames = []
        self.is_recording = False
        self.recording_started_event = Event()
        self.recording_error = None

        self.is_key_held = False
        self.last_press_time = 0
        self.double_press_threshold = 0.4  # Double click interval (seconds)

        self.stop_event = Event()
        self.ui_actions = queue.Queue()
        self.tray_icon = None
        self.tray_thread = None
        self.is_quitting = False
        self.keyboard_hooks = []
        self.mouse_listener = None

        self.setup_gui()
        self.setup_tray_icon()
        self.bind_record_key()

    def ui(self, text):
        return ui_text(text, self.language_mode)

    def set_output_converter(self):
        try:
            # Character conversion only. Avoid regional phrase conversion so
            # vocabulary such as 腳本/指令碼 remains faithful to the speaker.
            config = (
                "t2s"
                if self.language_mode == LANGUAGE_SIMPLIFIED
                else "s2t"
            )
            self.converter = opencc.OpenCC(config)
        except Exception as error:
            log_info(f"OpenCC initialization failed: {error}")
            self.converter = None

    def load_api_keys(self):
        try:
            content = os.environ.get("GROQ_API_KEYS", "")
            for path in (USER_KEY_FILE_PATH, KEY_FILE_PATH):
                if not content and os.path.exists(path):
                    with open(path, "r", encoding="utf-8") as file:
                        content = file.read()
            keys = parse_api_keys(content)
            return keys if valid_api_keys(keys) else []
        except Exception as e:
            log_info(f"Failed to load API keys: {e}")
            return []

    def recording_instruction(self):
        key_name = display_record_key(
            self.record_key,
            self.language_mode,
        )
        return {
            "double_press": (
                self.ui(
                    f"連按兩下 {key_name} 開始錄音,"
                    "錄音中再按一下停止"
                )
            ),
            "single_press": (
                self.ui(
                    f"按一下 {key_name} 開始錄音,"
                    "再按一下停止"
                )
            ),
            "hold": (
                self.ui(f"按住 {key_name} 錄音,放開後停止")
            ),
        }[normalize_activation_mode(self.activation_mode)]

    def bind_record_key(self):
        self.unbind_record_key()
        self.is_key_held = False
        if self.record_key.startswith(MOUSE_TRIGGER_PREFIX):
            self.mouse_listener = pynput_mouse.Listener(
                on_click=self.on_mouse_click,
                win32_event_filter=self.mouse_event_filter,
            )
            self.mouse_listener.start()
        else:
            self.keyboard_hooks = [
                keyboard.on_press_key(self.record_key, self.on_key_down, suppress=True),
                keyboard.on_release_key(self.record_key, self.on_key_up, suppress=True),
            ]
        log_info(
            "Recording control bound: "
            f"{display_record_key(self.record_key)}, "
            f"{display_activation_mode(self.activation_mode)}"
        )

    def unbind_record_key(self):
        for hook in self.keyboard_hooks:
            try:
                keyboard.unhook(hook)
            except (KeyError, ValueError):
                pass
        self.keyboard_hooks = []
        if self.mouse_listener is not None:
            try:
                self.mouse_listener.stop()
                self.mouse_listener.join(timeout=1)
            except (RuntimeError, OSError):
                pass
            self.mouse_listener = None

    def selected_mouse_button(self):
        return {
            "mouse:x1": pynput_mouse.Button.x1,
            "mouse:x2": pynput_mouse.Button.x2,
        }.get(self.record_key)

    def mouse_event_filter(self, msg, data):
        selected_button = self.selected_mouse_button()
        if selected_button is None:
            return True
        if msg not in (
            pynput_mouse.Listener.WM_XBUTTONDOWN,
            pynput_mouse.Listener.WM_XBUTTONUP,
        ):
            return True

        button_id = (int(data.mouseData) >> 16) & 0xFFFF
        selected_id = (
            pynput_mouse.Listener.XBUTTON1
            if selected_button == pynput_mouse.Button.x1
            else pynput_mouse.Listener.XBUTTON2
        )
        if button_id == selected_id and self.mouse_listener is not None:
            self.mouse_listener.suppress_event()
        return True

    def on_mouse_click(self, x, y, button, pressed, injected=False):
        if button != self.selected_mouse_button():
            return
        if pressed:
            self.on_key_down()
        else:
            self.on_key_up()

    def on_key_down(self, event=None):
        if self.is_processing_ui or self.is_key_held:
            return

        self.is_key_held = True
        if self.activation_mode == "hold":
            if not self.is_recording:
                log_info("Hold control pressed, starting recording...")
                self.start_recording_process()
            return

        if self.activation_mode == "single_press":
            if self.is_recording:
                log_info("Single press detected, stopping recording...")
                self.stop_recording_process()
            else:
                log_info("Single press detected, starting recording...")
                self.start_recording_process()
            return

        current_time = time.time()
        if not self.is_recording:
            if current_time - self.last_press_time <= self.double_press_threshold:
                log_info("Double press detected, starting recording...")
                self.start_recording_process()
            self.last_press_time = current_time
        else:
            log_info("Key pressed during recording, stopping recording...")
            self.stop_recording_process()

    def on_key_up(self, event=None):
        was_held = self.is_key_held
        self.is_key_held = False
        if (
            was_held
            and self.activation_mode == "hold"
            and self.is_recording
        ):
            log_info("Hold control released, stopping recording...")
            self.stop_recording_process()

    def start_recording_process(self):
        if not self.is_recording:
            self.is_recording = True
            self.frames = []
            self.recording_error = None
            self.recording_started_event.clear()
            threading.Thread(target=self.record_thread, daemon=True).start()
            if not self.recording_started_event.wait(MICROPHONE_START_TIMEOUT_SECONDS):
                self.is_recording = False
                self.root.after(0, lambda: self.set_ui_error("Microphone start timed out."))
                return
            if self.recording_error:
                self.is_recording = False
                return
            self.root.after(0, self.set_ui_recording)

    def stop_recording_process(self):
        if self.is_recording:
            self.is_recording = False
            self.is_processing_ui = True
            self.root.after(0, self.set_ui_processing)
            threading.Thread(target=self.process_audio_workflow, daemon=True).start()

    def record_thread(self):
        stream = None
        audio = None
        try:
            # Refresh PortAudio for every recording. This avoids stale device
            # indexes after a USB or Bluetooth microphone is unplugged.
            audio = pyaudio.PyAudio()
            stream, device = open_microphone_stream(audio, self.microphone_name)
            self.active_microphone_name = device["name"]
            if (
                self.microphone_name
                and device["name"].casefold() != self.microphone_name.casefold()
            ):
                log_info(
                    f'Selected microphone "{self.microphone_name}" was unavailable. '
                    f'Using "{device["name"]}" instead.'
                )
            else:
                log_info(
                    f'Recording from microphone "{device["name"]}" '
                    f'({device["host_api"]}, device {device["index"]}).'
                )
            self.recording_started_event.set()

            while self.is_recording and not self.stop_event.is_set():
                data = stream.read(CHUNK, exception_on_overflow=False)
                self.frames.append(data)
        except Exception as e:
            self.recording_error = str(e)
            log_info(f"Recording thread error: {e}")
            self.root.after(0, lambda: self.set_ui_error(f"Recording failed: {e}"))
            self.is_recording = False
            self.recording_started_event.set()
        finally:
            if stream:
                try:
                    stream.stop_stream()
                    stream.close()
                except Exception as e:
                    log_info(f"Failed to close microphone stream: {e}")
            if audio is not None:
                try:
                    audio.terminate()
                except Exception as error:
                    log_info(f"Failed to terminate microphone session: {error}")

    def process_audio_workflow(self):
        start_time = time.time()
        wav_path = None
        log_info("=== Starting Audio Workflow ===")
        try:
            if not self.frames:
                raise RuntimeError("No audio frames were recorded.")

            wav_path = self.save_wav_file()
            if not wav_path:
                raise RuntimeError("The recording could not be saved.")

            transcription = self.transcribe_audio(wav_path)
            raw_text = remove_transcription_prompt_leakage(transcription.text)
            if not raw_text:
                raise RuntimeError("Groq returned no spoken content.")

            timestamped_text = punctuate_from_timestamps(
                raw_text,
                words=getattr(transcription, "words", None),
                segments=getattr(transcription, "segments", None),
            )
            final_text = self.prepare_transcription(timestamped_text)
            if not final_text:
                raise RuntimeError("Groq returned no spoken content.")
            log_info(f"Transcription success: {len(final_text)} characters")

            if not self.simulate_typing(final_text):
                raise RuntimeError("The transcription was copied, but automatic paste failed.")
            self.root.after(0, self.set_ui_success)
        except Exception as e:
            log_info(f"Audio workflow failed: {e}")
            self.root.after(0, lambda message=str(e): self.set_ui_error(message))
        finally:
            self.frames = []
            if wav_path and os.path.exists(wav_path):
                try:
                    os.remove(wav_path)
                    log_info("Cleaned temp WAV file.")
                except Exception as e:
                    log_info(f"Failed to clean temp WAV: {e}")

            elapsed = time.time() - start_time
            log_info(f"=== Audio Workflow Completed, Elapsed: {elapsed:.2f}s ===")

    def save_wav_file(self):
        wav_path = None
        try:
            fd, wav_path = tempfile.mkstemp(prefix="groq_dictate_", suffix=".wav")
            os.close(fd)
            log_info(f"Saving WAV to: {wav_path} ...")
            audio_data = b"".join(self.frames)
            with wave.open(wav_path, "wb") as wf:
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(pyaudio.get_sample_size(FORMAT))
                wf.setframerate(RATE)
                wf.writeframes(audio_data)
            log_info(f"WAV saved successfully, size: {len(audio_data)} bytes")
            return wav_path
        except Exception as e:
            log_info(f"Error saving WAV: {e}")
            if wav_path and os.path.exists(wav_path):
                try:
                    os.remove(wav_path)
                except OSError:
                    pass
            return None

    def transcribe_audio(self, wav_path):
        upload_path = wav_path
        compressed_path = None
        wav_size = os.path.getsize(wav_path)
        duration_seconds = max(
            0.0,
            (wav_size - 44) / (RATE * CHANNELS * pyaudio.get_sample_size(FORMAT)),
        )
        log_info(
            f"Audio prepared: duration: {duration_seconds:.2f}s, "
            f"WAV size: {wav_size} bytes"
        )

        if wav_size >= FLAC_THRESHOLD_BYTES:
            candidate_path = os.path.splitext(wav_path)[0] + ".flac"
            log_info("Large WAV detected. Compressing losslessly to FLAC...")
            if compress_to_flac(wav_path, candidate_path):
                upload_path = candidate_path
                compressed_path = candidate_path
            else:
                log_info("FLAC compression unavailable. Uploading raw WAV.")

        attempts = 0
        max_attempts = len(self.api_keys) * len(self.models)
        last_error = None

        try:
            while attempts < max_attempts:
                api_start = time.time()
                current_model = self.models[self.current_model_index]
                log_info(
                    f"Attempting transcription: key #{self.current_key_index + 1}, "
                    f"model \"{current_model}\" (attempt {attempts + 1}/{max_attempts})..."
                )

                try:
                    with open(upload_path, "rb") as file:
                        file_data = file.read()
                        log_info(f"Payload size: {len(file_data)} bytes")
                        transcription = self.client.audio.transcriptions.create(
                            file=(upload_path, file_data),
                            model=current_model,
                            response_format="verbose_json",
                            timestamp_granularities=["word", "segment"],
                            language="zh",
                            prompt=transcription_prompt(self.language_mode),
                            temperature=0.0,
                        )
                    api_elapsed = time.time() - api_start
                    log_info(f"Groq API call success, elapsed: {api_elapsed:.2f}s")
                    return transcription
                except Exception as e:
                    last_error = e
                    api_elapsed = time.time() - api_start
                    log_info(
                        f"Groq API call failed: key #{self.current_key_index + 1}, "
                        f"model \"{current_model}\", elapsed: {api_elapsed:.2f}s, error: {e}"
                    )

                    self.current_model_index = (self.current_model_index + 1) % len(self.models)
                    if self.current_model_index == 0:
                        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
                        next_key = self.api_keys[self.current_key_index]
                        log_info(f"Switching to key #{self.current_key_index + 1}...")
                        self.client = Groq(api_key=next_key, timeout=API_TIMEOUT_SECONDS)

                    attempts += 1
                    if attempts < max_attempts:
                        time.sleep(0.5)

            raise RuntimeError(f"All transcription attempts failed. Last error: {last_error}")
        finally:
            if compressed_path and os.path.exists(compressed_path):
                try:
                    os.remove(compressed_path)
                    log_info("Cleaned temp FLAC file.")
                except Exception as e:
                    log_info(f"Failed to clean temp FLAC: {e}")

    def prepare_transcription(self, text):
        if self.converter and text:
            try:
                text = self.converter.convert(text)
            except Exception as e:
                log_info(f"OpenCC conversion failed: {e}")
        return normalize_transcription(text)

    def simulate_typing(self, text):
        """Use clipboard and Ctrl+V to paste text instantly."""
        if not text:
            return False
        try:
            log_info("Copying text to clipboard and triggering Ctrl+V...")
            pyperclip.copy(text)
            time.sleep(0.05)
            keyboard.send('ctrl+v')
            log_info("Ctrl+V keystroke sent.")
            return True
        except Exception as e:
            log_info(f"Pasting failed: {e}")
            return False

    # ==========================================
    # GUI and Visuals
    # ==========================================
    def setup_gui(self):
        self.root = tk.Tk()
        self.root.attributes("-topmost", True)
        self.root.overrideredirect(True)
        self.root.attributes("-alpha", 0.85)
        self.root.config(bg='black')
        self.root.attributes("-transparentcolor", "black")

        self.ball_size = 50
        self.canvas = tk.Canvas(self.root, width=self.ball_size, height=self.ball_size, bg='black', highlightthickness=0)
        self.canvas.pack()

        self.sphere = self.canvas.create_oval(
            5, 5, self.ball_size-5, self.ball_size-5,
            outline='#4d0000', width=2, fill='#ff1a1a'
        )

        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x_c = screen_width - self.ball_size - 20
        y_c = screen_height - self.ball_size - 35
        self.root.geometry(f"{self.ball_size}x{self.ball_size}+{x_c}+{y_c}")

        self.is_processing_ui = False
        self.hide_timer_id = None

        self.popup_menu = tk.Menu(self.root, tearoff=0)
        self.popup_menu.add_command(
            label=self.ui("退出 AZA-STT"),
            command=self.quit_app,
        )
        self.canvas.bind("<Button-3>", self.show_popup_menu)

        self.root.withdraw()
        self.root.after(100, self.process_ui_actions)

        self.root.after(100, lambda: print("=== Program started and modules loaded successfully ==="))
        self.root.after(
            100,
            lambda: print(
                "🚀 Groq voice ball started! "
                f"({self.recording_instruction()})"
            ),
        )

    def setup_tray_icon(self):
        if pystray is None:
            log_info("pystray or Pillow is unavailable; notification area icon was not started.")
            return

        menu = pystray.Menu(
            pystray.MenuItem(
                lambda item: self.tray_status_text(),
                self.enqueue_status_dialog,
                default=True,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                lambda item: (
                    self.ui("設定錄音控制 ")
                    + self.ui(
                        f"(目前: "
                        f"{display_record_key(self.record_key, self.language_mode)})"
                    )
                ),
                self.enqueue_record_key_setup,
            ),
            pystray.MenuItem(
                lambda item: (
                    self.ui("選擇麥克風 ")
                    + self.ui(
                        f"(目前: "
                        f"{display_microphone_name(self.microphone_name, self.language_mode)})"
                    )
                ),
                self.enqueue_microphone_setup,
            ),
            pystray.MenuItem(
                lambda item: (
                    "語言 / 语言 "
                    f"({display_language_mode(self.language_mode)})"
                ),
                self.enqueue_language_setup,
            ),
            pystray.MenuItem(
                lambda item: self.ui("重新輸入 Groq API key"),
                self.enqueue_api_key_setup,
            ),
            pystray.MenuItem(
                lambda item: self.ui("開啟 Groq API Keys 網頁"),
                self.enqueue_open_keys_page,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                lambda item: self.ui("退出 AZA-STT"),
                self.enqueue_quit,
            ),
        )
        self.tray_icon = pystray.Icon(
            "AZA-STT",
            create_tray_image(),
            self.ui("AZA-STT - 背景執行中"),
            menu,
        )
        self.tray_thread = threading.Thread(
            target=self.run_tray_icon,
            name="AZA-STT Tray",
            daemon=True,
        )
        self.tray_thread.start()

    def run_tray_icon(self):
        try:
            self.tray_icon.run(setup=self.on_tray_ready)
        except Exception as error:
            log_info(f"Notification area icon failed: {error}")

    def on_tray_ready(self, icon):
        icon.visible = True
        try:
            icon.notify(
                self.ui("AZA-STT 已縮到 Windows 右下角通知區。\n")
                + f"{self.recording_instruction()}.",
                self.ui("AZA-STT 正在背景執行"),
            )
        except Exception as error:
            log_info(f"Startup tray notification failed: {error}")

    def tray_status_text(self):
        if self.is_recording:
            return self.ui("AZA-STT - 錄音中")
        if self.is_processing_ui:
            return self.ui("AZA-STT - 辨識中")
        return self.ui("AZA-STT - 背景執行中")

    def enqueue_ui_action(self, action):
        if not self.is_quitting:
            self.ui_actions.put(action)

    def enqueue_status_dialog(self, icon=None, item=None):
        self.enqueue_ui_action(self.show_status_dialog)

    def enqueue_api_key_setup(self, icon=None, item=None):
        self.enqueue_ui_action(self.configure_api_keys)

    def enqueue_record_key_setup(self, icon=None, item=None):
        self.enqueue_ui_action(self.configure_record_key)

    def enqueue_microphone_setup(self, icon=None, item=None):
        self.enqueue_ui_action(self.configure_microphone)

    def enqueue_language_setup(self, icon=None, item=None):
        self.enqueue_ui_action(self.configure_language)

    def enqueue_open_keys_page(self, icon=None, item=None):
        self.enqueue_ui_action(self.open_keys_page_from_tray)

    def enqueue_quit(self, icon=None, item=None):
        self.enqueue_ui_action(self.quit_app)

    def process_ui_actions(self):
        if self.is_quitting:
            return
        try:
            while True:
                action = self.ui_actions.get_nowait()
                action()
                if self.is_quitting:
                    return
        except queue.Empty:
            pass
        self.root.after(100, self.process_ui_actions)

    def show_status_dialog(self):
        status = self.tray_status_text()
        messagebox.showinfo(
            "AZA-STT",
            f"{status}\n\n"
            + self.ui(
                f"{self.recording_instruction()},完成後會轉成文字。\n"
                f"麥克風: "
                f"{display_microphone_name(self.microphone_name, self.language_mode)}\n"
                "程式關閉錄音提示後仍會留在 Windows 右下角通知區。\n\n"
                "若要完整關閉,請在 AZA-STT 圖示按右鍵,"
                "選擇「退出 AZA-STT」。"
            ),
            parent=self.root,
        )

    def configure_record_key(self):
        if self.is_recording or self.is_processing_ui:
            messagebox.showwarning(
                "AZA-STT",
                self.ui("請先完成目前的錄音或語音辨識,再更換錄音控制。"),
                parent=self.root,
            )
            return

        previous_key = self.record_key
        previous_mode = self.activation_mode
        self.unbind_record_key()
        try:
            dialog = RecordKeySetupDialog(
                self.root,
                previous_key,
                previous_mode,
                self.language_mode,
            )
            selected_settings = dialog.result
            if not selected_settings:
                return
            selected_key, selected_mode = selected_settings
            self.record_key, self.activation_mode = save_user_input_settings(
                selected_key,
                selected_mode,
            )
            log_info(
                "Recording control changed to "
                f"{display_record_key(self.record_key, self.language_mode)}, "
                f"{display_activation_mode(self.activation_mode, self.language_mode)}"
            )
            if self.tray_icon:
                self.tray_icon.update_menu()
            messagebox.showinfo(
                "AZA-STT",
                self.ui(
                    f"錄音控制已儲存。\n"
                    f"{self.recording_instruction()}。"
                ),
                parent=self.root,
            )
        except Exception as error:
            self.record_key = previous_key
            self.activation_mode = previous_mode
            log_info(f"Failed to change recording control: {error}")
            messagebox.showerror(
                "AZA-STT",
                self.ui(f"無法儲存錄音控制:\n{error}"),
                parent=self.root,
            )
        finally:
            self.bind_record_key()

    def configure_microphone(self):
        if self.is_recording or self.is_processing_ui:
            messagebox.showwarning(
                "AZA-STT",
                self.ui("請先完成目前的錄音或語音辨識,再更換麥克風。"),
                parent=self.root,
            )
            return

        try:
            dialog = MicrophoneSetupDialog(
                self.root,
                self.microphone_name,
                self.language_mode,
            )
            selected = dialog.result
            if not selected:
                return
            self.microphone_name = save_user_microphone_selection(selected[0])
            self.active_microphone_name = None
            log_info(
                "Microphone selection changed to "
                f'"{display_microphone_name(self.microphone_name, self.language_mode)}".'
            )
            if self.tray_icon:
                self.tray_icon.update_menu()
            messagebox.showinfo(
                "AZA-STT",
                self.ui(
                    "麥克風設定已儲存。\n"
                    f"目前: "
                    f"{display_microphone_name(self.microphone_name, self.language_mode)}"
                ),
                parent=self.root,
            )
        except Exception as error:
            log_info(f"Failed to change microphone: {error}")
            messagebox.showerror(
                "AZA-STT",
                self.ui(f"無法儲存麥克風設定:\n{error}"),
                parent=self.root,
            )

    def configure_language(self):
        if self.is_recording or self.is_processing_ui:
            messagebox.showwarning(
                "AZA-STT",
                self.ui("請先完成目前的錄音或語音辨識,再切換語言。"),
                parent=self.root,
            )
            return

        previous_language = self.language_mode
        try:
            dialog = LanguageSetupDialog(
                self.root,
                previous_language,
            )
            selected_language = dialog.result
            if not selected_language:
                return
            self.language_mode = save_user_language_mode(selected_language)
            self.set_output_converter()
            self.popup_menu.entryconfigure(
                0,
                label=self.ui("退出 AZA-STT"),
            )
            if self.tray_icon:
                self.tray_icon.title = self.tray_status_text()
                self.tray_icon.update_menu()
            log_info(
                "Language mode changed to "
                f'"{self.language_mode}".'
            )
            messagebox.showinfo(
                "AZA-STT",
                self.ui(
                    "語言設定已儲存。\n"
                    f"目前: {display_language_mode(self.language_mode)}"
                ),
                parent=self.root,
            )
        except Exception as error:
            self.language_mode = previous_language
            self.set_output_converter()
            log_info(f"Failed to change language mode: {error}")
            messagebox.showerror(
                "AZA-STT",
                self.ui(f"無法儲存語言設定:\n{error}"),
                parent=self.root,
            )

    def configure_api_keys(self):
        if self.is_recording or self.is_processing_ui:
            messagebox.showwarning(
                "AZA-STT",
                self.ui("請先完成目前的錄音或語音辨識,再更換 API key。"),
                parent=self.root,
            )
            return

        keys = prompt_for_api_keys(
            parent=self.root,
            language_mode=self.language_mode,
        )
        if not keys:
            return
        self.api_keys = keys
        self.current_key_index = 0
        self.current_model_index = 0
        self.client = Groq(api_key=keys[0], timeout=API_TIMEOUT_SECONDS)
        log_info("Groq API keys updated from the notification area menu.")

    def open_keys_page_from_tray(self):
        if not open_groq_keys_page():
            messagebox.showerror(
                "AZA-STT",
                self.ui(f"無法開啟瀏覽器。\n\n{GROQ_KEYS_URL}"),
                parent=self.root,
            )

    def set_tray_status(self, status):
        if not self.tray_icon:
            return
        try:
            self.tray_icon.icon = create_tray_image(status)
            self.tray_icon.title = self.tray_status_text()
            self.tray_icon.update_menu()
        except Exception as error:
            log_info(f"Failed to update notification area status: {error}")

    def cancel_hide_timer(self):
        if self.hide_timer_id is not None:
            self.root.after_cancel(self.hide_timer_id)
            self.hide_timer_id = None

    def set_ui_idle(self):
        self.cancel_hide_timer()
        self.is_processing_ui = False
        self.root.withdraw()
        self.set_tray_status("idle")

    def set_ui_recording(self):
        self.cancel_hide_timer()
        self.is_processing_ui = False
        self.root.deiconify()
        self.canvas.itemconfig(self.sphere, fill='#ff1a1a', outline='#4d0000', width=2)
        self.canvas.config(cursor="hand2")
        self.set_tray_status("recording")

    def set_ui_processing(self):
        self.cancel_hide_timer()
        self.is_processing_ui = True
        self.canvas.itemconfig(self.sphere, fill='#FF851B', outline='#B35900', width=2)
        self.canvas.config(cursor="watch")
        self.set_tray_status("processing")

    def set_ui_success(self):
        self.cancel_hide_timer()
        self.is_processing_ui = False
        self.canvas.itemconfig(self.sphere, fill='#2ECC40', outline='#145A32', width=2)
        self.set_tray_status("success")
        self.hide_timer_id = self.root.after(1000, self.set_ui_idle)

    def set_ui_error(self, message):
        self.cancel_hide_timer()
        self.is_processing_ui = False
        self.canvas.itemconfig(self.sphere, fill='#666666', outline='#333333', width=2)
        self.canvas.config(cursor="x_cursor")
        print(f"❌ Error: {message}")
        self.set_tray_status("error")
        self.hide_timer_id = self.root.after(3000, self.set_ui_idle)

    def show_popup_menu(self, event):
        if not self.is_processing_ui:
            self.popup_menu.post(event.x_root, event.y_root)

    def quit_app(self):
        if self.is_quitting:
            return
        self.is_quitting = True
        self.stop_event.set()
        self.cancel_hide_timer()
        self.is_recording = False
        self.unbind_record_key()
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception as e:
                log_info(f"Notification area shutdown failed: {e}")
        if self.instance_handle:
            release_single_instance(self.instance_handle)
            self.instance_handle = None
        self.root.quit()
        self.root.destroy()

    def run(self):
        self.set_ui_idle()
        self.root.mainloop()

if __name__ == "__main__":
    if "--self-test-hotkey" in sys.argv:
        sys.exit(0 if run_hotkey_self_test() else 1)

    if "--self-test-tray" in sys.argv:
        sys.exit(0 if run_tray_self_test() else 1)

    if "--self-test-flac" in sys.argv:
        sys.exit(0 if run_flac_self_test() else 1)

    if "--self-test-microphone" in sys.argv:
        sys.exit(0 if run_microphone_self_test() else 1)

    if "--self-test-language" in sys.argv:
        sys.exit(0 if run_language_self_test() else 1)

    if "--configure" in sys.argv:
        configured_keys = prompt_for_api_keys()
        sys.exit(0 if configured_keys else 1)

    instance_handle = acquire_single_instance()
    if not instance_handle:
        log_info("Another AZA-STT instance is already running.")
        if sys.platform == "win32":
            language_mode = load_user_language_mode()
            ctypes.windll.user32.MessageBoxW(
                0,
                ui_text(
                    "AZA-STT 已經在背景執行。\n\n"
                    "請在 Windows 右下角通知區尋找 AZA-STT 圖示。",
                    language_mode,
                ),
                "AZA-STT",
                0x40,
            )
        sys.exit(0)
    app = GroqDictateApp(instance_handle=instance_handle)
    app.run()
