# -*- coding: utf-8 -*-
import time
import sys
import os
import threading
import tempfile
import wave
import tkinter as tk
from tkinter import messagebox, simpledialog
from threading import Event
from datetime import datetime
import subprocess
import re
import ctypes
import logging
import webbrowser
from logging.handlers import RotatingFileHandler

try:
    import winreg
except ImportError:
    winreg = None

import keyboard
import pyaudio
import pyperclip
from groq import Groq
import opencc

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else SCRIPT_DIR
APP_DATA_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA", tempfile.gettempdir()),
    "AZA-STT",
)
os.makedirs(APP_DATA_DIR, exist_ok=True)
LOG_FILE_PATH = os.path.join(APP_DATA_DIR, "aza-stt.log")
USER_KEY_FILE_PATH = os.path.join(APP_DATA_DIR, "dictate_settings.conf")
GROQ_KEYS_URL = "https://console.groq.com/keys"
_LOGGER = None

TECH_TERMS = (
    "Groq", "Gemini", "ChatGPT", "OpenAI", "Claude", "Claude Code",
    "Anthropic", "NVIDIA", "CUDA", "Google", "DeepMind", "Microsoft",
    "GitHub", "GitHub Copilot", "Copilot", "Meta", "Llama", "xAI", "Grok",
    "Mistral", "Perplexity", "Hugging Face", "Cursor", "Codex", "Python",
    "JavaScript", "TypeScript", "React", "Next.js", "Node.js", "VS Code",
    "Docker", "Kubernetes", "API", "GPU", "AI", "AGI", "LLM",
)

TRANSCRIPTION_PROMPT = (
    "繁體中文 AI 與軟體開發討論逐字稿。常用拼字: "
    + ", ".join(TECH_TERMS)
    + ". 使用半形逗號與句點,依語意自然分句。"
)

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


def normalize_transcription(text):
    """Keep vocabulary intact and consistently use half-width punctuation."""
    if not text:
        return text

    normalized = text.translate(PUNCTUATION_TRANSLATION)
    normalized = canonicalize_tech_terms(normalized)

    # A space before punctuation is wrong in both Chinese and English. A space
    # after punctuation is removed only before CJK, preserving "Hello, world".
    normalized = re.sub(r"\s+([,.;:!?])", r"\1", normalized)
    normalized = re.sub(r"([,.;:!?])\s+(?=[\u3400-\u9fff])", r"\1", normalized)
    normalized = re.sub(r"[ \t]+", " ", normalized).strip()
    normalized = _limit_sentence_length(normalized)

    if normalized and normalized[-1] not in ".!?":
        normalized += "."

    return _add_paragraph_breaks(normalized)


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
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        subprocess.run([
            "ffmpeg", "-y", "-i", wav_path,
            "-ar", str(RATE), "-ac", str(CHANNELS), "-c:a", "flac",
            flac_path
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, startupinfo=startupinfo, check=True)
        return True
    except Exception as e:
        log_info(f"FFmpeg compression failed: {e}")
        return False

# Settings
KEY_FILE_PATH = os.path.join(APP_DIR, "dictate_settings.conf")

FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1024
RECORD_KEY = 'menu'
API_TIMEOUT_SECONDS = 30.0
FLAC_THRESHOLD_BYTES = 20 * 1024 * 1024
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
    def body(self, master):
        self.title("AZA-STT 設定")
        tk.Label(
            master,
            text="請貼上 Groq API key",
            font=("Segoe UI", 11, "bold"),
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))
        tk.Label(
            master,
            text=(
                "多組 key 可使用逗號、分號或空格分隔。\n"
                "如果還沒有 key，請點下方按鈕前往 Groq 申請。"
            ),
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(0, 8))
        self.key_entry = tk.Entry(master, width=58, show="*")
        self.key_entry.grid(row=2, column=0, sticky="ew", pady=(0, 6))
        tk.Label(
            master,
            text=f"只會儲存在這台電腦：\n{USER_KEY_FILE_PATH}",
            justify="left",
            fg="#555555",
        ).grid(row=3, column=0, sticky="w")
        master.grid_columnconfigure(0, weight=1)
        return self.key_entry

    def buttonbox(self):
        box = tk.Frame(self)
        tk.Button(
            box,
            text="開啟 Groq API Keys",
            command=self.open_keys_page,
        ).pack(side="left", padx=(0, 18))
        tk.Button(
            box,
            text="儲存",
            width=10,
            command=self.ok,
            default=tk.ACTIVE,
        ).pack(side="left", padx=5)
        tk.Button(
            box,
            text="取消",
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
                f"無法開啟 Groq 網頁：\n{error}\n\n{GROQ_KEYS_URL}",
                parent=self,
            )

    def validate(self):
        keys = parse_api_keys(self.key_entry.get())
        if not valid_api_keys(keys):
            messagebox.showerror(
                "AZA-STT",
                "API key 格式不正確。Groq API key 應以 gsk_ 開頭。",
                parent=self,
            )
            return False
        self.validated_keys = keys
        return True

    def apply(self):
        self.result = self.validated_keys


def prompt_for_api_keys(parent=None):
    owns_root = parent is None
    dialog_parent = parent
    if owns_root:
        dialog_parent = tk.Tk()
        dialog_parent.withdraw()
        dialog_parent.attributes("-topmost", True)

    try:
        dialog = ApiKeySetupDialog(dialog_parent)
        keys = dialog.result or []
        if not keys:
            return []

        try:
            save_user_api_keys(keys)
        except Exception as error:
            messagebox.showerror(
                "AZA-STT",
                f"無法儲存 API key：\n{error}",
                parent=dialog_parent,
            )
            return []

        messagebox.showinfo(
            "AZA-STT",
            "Groq API key 已儲存。\n"
            "若 AZA-STT 已在執行，請重新啟動後使用新 key。",
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

class GroqDictateApp:
    def __init__(self, instance_handle=None):
        self.instance_handle = instance_handle
        self.api_keys = self.load_api_keys()
        if not self.api_keys:
            log_info("No API keys found. Opening first-run setup.")
            self.api_keys = prompt_for_api_keys()
            if not self.api_keys:
                log_info("API key setup was cancelled.")
                sys.exit(1)

        self.current_key_index = 0
        self.models = ["whisper-large-v3", "whisper-large-v3-turbo"]
        self.current_model_index = 0
        self.client = Groq(api_key=self.api_keys[self.current_key_index], timeout=API_TIMEOUT_SECONDS)
        log_info(f"Groq API client initialized with key #{self.current_key_index + 1}")
        try:
            # Convert simplified characters only. Avoid s2twp because its
            # regional phrase conversion changes words such as 腳本/指令碼.
            self.converter = opencc.OpenCC('s2t')
        except Exception as e:
            print(f"OpenCC initialization failed: {e}")
            self.converter = None

        self.p = pyaudio.PyAudio()
        self.frames = []
        self.is_recording = False
        self.recording_started_event = Event()
        self.recording_error = None

        self.is_key_held = False
        self.last_press_time = 0
        self.double_press_threshold = 0.4  # Double click interval (seconds)

        self.setup_gui()

        self.stop_event = Event()
        self.listen_thread = threading.Thread(target=self.pynput_listen_loop, daemon=True)
        self.listen_thread.start()

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

    def pynput_listen_loop(self):
        keyboard.on_press_key(RECORD_KEY, self.on_key_down, suppress=True)
        keyboard.on_release_key(RECORD_KEY, self.on_key_up, suppress=True)

        self.stop_event.wait()
        keyboard.unhook_all()

    def on_key_down(self, e):
        if self.is_processing_ui: return

        if not self.is_key_held:
            self.is_key_held = True
            current_time = time.time()

            if not self.is_recording:
                if current_time - self.last_press_time <= self.double_press_threshold:
                    log_info("Double press detected, starting recording...")
                    self.start_recording_process()
                self.last_press_time = current_time
            else:
                log_info("Key pressed during recording, stopping recording...")
                self.is_key_held = False
                self.stop_recording_process()

    def on_key_up(self, e):
        if self.is_processing_ui: return
        self.is_key_held = False

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
        try:
            stream = self.p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
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
            raw_text = transcription.text
            if not raw_text:
                raise RuntimeError("Groq returned an empty transcription.")

            timestamped_text = punctuate_from_timestamps(
                raw_text,
                words=getattr(transcription, "words", None),
                segments=getattr(transcription, "segments", None),
            )
            final_text = self.prepare_transcription(timestamped_text)
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
                wf.setsampwidth(self.p.get_sample_size(FORMAT))
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

        if os.path.getsize(wav_path) >= FLAC_THRESHOLD_BYTES:
            candidate_path = os.path.splitext(wav_path)[0] + ".flac"
            if check_ffmpeg_available():
                log_info("Large WAV detected. Compressing losslessly to FLAC...")
                if compress_to_flac(wav_path, candidate_path):
                    upload_path = candidate_path
                    compressed_path = candidate_path
            else:
                log_info("FFmpeg not detected. Uploading raw WAV.")

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
                            prompt=TRANSCRIPTION_PROMPT,
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
        self.popup_menu.add_command(label="Exit", command=self.quit_app)
        self.canvas.bind("<Button-3>", self.show_popup_menu)

        self.root.withdraw()

        self.root.after(100, lambda: print("=== Program started and modules loaded successfully ==="))
        self.root.after(100, lambda: print(f"🚀 Groq voice ball started! (Double press {RECORD_KEY.upper()} to record)"))

    def cancel_hide_timer(self):
        if self.hide_timer_id is not None:
            self.root.after_cancel(self.hide_timer_id)
            self.hide_timer_id = None

    def set_ui_idle(self):
        self.cancel_hide_timer()
        self.is_processing_ui = False
        self.root.withdraw()

    def set_ui_recording(self):
        self.cancel_hide_timer()
        self.is_processing_ui = False
        self.root.deiconify()
        self.canvas.itemconfig(self.sphere, fill='#ff1a1a', outline='#4d0000', width=2)
        self.canvas.config(cursor="hand2")

    def set_ui_processing(self):
        self.cancel_hide_timer()
        self.is_processing_ui = True
        self.canvas.itemconfig(self.sphere, fill='#FF851B', outline='#B35900', width=2)
        self.canvas.config(cursor="watch")

    def set_ui_success(self):
        self.cancel_hide_timer()
        self.is_processing_ui = False
        self.canvas.itemconfig(self.sphere, fill='#2ECC40', outline='#145A32', width=2)
        self.hide_timer_id = self.root.after(1000, self.set_ui_idle)

    def set_ui_error(self, message):
        self.cancel_hide_timer()
        self.is_processing_ui = False
        self.canvas.itemconfig(self.sphere, fill='#666666', outline='#333333', width=2)
        self.canvas.config(cursor="x_cursor")
        print(f"❌ Error: {message}")
        self.hide_timer_id = self.root.after(3000, self.set_ui_idle)

    def show_popup_menu(self, event):
        if not self.is_processing_ui:
            self.popup_menu.post(event.x_root, event.y_root)

    def quit_app(self):
        self.stop_event.set()
        self.cancel_hide_timer()
        self.is_recording = False
        try:
            self.p.terminate()
        except Exception as e:
            log_info(f"PyAudio shutdown failed: {e}")
        if self.instance_handle:
            release_single_instance(self.instance_handle)
            self.instance_handle = None
        self.root.quit()
        self.root.destroy()
        sys.exit(0)

    def run(self):
        self.set_ui_idle()
        self.root.mainloop()

if __name__ == "__main__":
    if "--configure" in sys.argv:
        configured_keys = prompt_for_api_keys()
        sys.exit(0 if configured_keys else 1)

    instance_handle = acquire_single_instance()
    if not instance_handle:
        log_info("Another AZA-STT instance is already running.")
        sys.exit(0)
    app = GroqDictateApp(instance_handle=instance_handle)
    app.run()
