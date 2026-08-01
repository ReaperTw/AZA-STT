"""Interpret Groq verbose transcription responses without UI dependencies."""

from dataclasses import dataclass
from typing import Optional
import logging
import re

import opencc


LOGGER = logging.getLogger("aza_stt.transcription_interpreter")


PROMPT_TERMS = (
    "Grok", "Groq", "Gemini", "ChatGPT", "OpenAI", "Claude Code",
    "GitHub", "GitHub Copilot", "Codex", "Python", "TypeScript", "API", "quota",
    "GPT-5.6", "GPT-5.6 Sol", "GPT-5.6 Terra", "GPT-5.6 Luna",
    "GPT-5.6 Sol Pro", "Extra High", "xhigh",
)

LANGUAGE_TRADITIONAL = "zh-TW"
LANGUAGE_SIMPLIFIED = "zh-CN"
LANGUAGE_MODES = (LANGUAGE_TRADITIONAL, LANGUAGE_SIMPLIFIED)


def normalize_language_mode(mode):
    normalized = str(mode or "").strip()
    return normalized if normalized in LANGUAGE_MODES else None


def transcription_prompt(language_mode):
    if normalize_language_mode(language_mode) == LANGUAGE_SIMPLIFIED:
        description = (
            "简体中文 AI 与软件开发忠实逐字稿。常见词: Skill/Skills。"
            "Scale 仅用于尺度、比例或规模。专有名词: "
        )
    else:
        description = (
            "繁體中文 AI 與軟體開發忠實逐字稿。常見詞: Skill/Skills。"
            "Scale 僅用於尺度、比例或規模。專有名詞: "
        )
    return description + ", ".join(PROMPT_TERMS) + "."


PROMPT_LEAKAGE_SUFFIXES = (
    r"(?:使用半形標點[,，。.\s]*)?標點後保留一個空格[,，\s]*並依語意自然分句[。.]?",
    r"(?:使用半角标点[,，。.\s]*)?标点后保留一个空格[,，\s]*并按语义自然分句[。.]?",
)


def remove_transcription_prompt_leakage(text):
    """Remove known prompt instructions Whisper may echo after quiet audio."""
    cleaned = str(text or "").strip()
    for mode in LANGUAGE_MODES:
        cleaned = re.sub(
            rf"(?:[\s\"'「」『』]*{re.escape(transcription_prompt(mode))}"
            rf"[\s\"'「」『』]*)$",
            "",
            cleaned,
            flags=re.IGNORECASE,
        ).rstrip()
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
    (r"(?<![A-Za-z0-9])gpt[\s.-]*5[\s.-]*6[\s-]*sol[\s-]*pro(?![A-Za-z0-9])", "GPT-5.6 Sol Pro"),
    (r"(?<![A-Za-z0-9])gpt[\s.-]*5[\s.-]*6[\s-]*sol(?![A-Za-z0-9])", "GPT-5.6 Sol"),
    (r"(?<![A-Za-z0-9])gpt[\s.-]*5[\s.-]*6[\s-]*terra(?![A-Za-z0-9])", "GPT-5.6 Terra"),
    (r"(?<![A-Za-z0-9])gpt[\s.-]*5[\s.-]*6[\s-]*luna(?![A-Za-z0-9])", "GPT-5.6 Luna"),
    (r"(?<![A-Za-z0-9])gpt[\s.-]*5[\s.-]*6(?![A-Za-z0-9])", "GPT-5.6"),
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
    (r"(?<![A-Za-z0-9])gork(?![A-Za-z0-9])", "Grok"),
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

PUNCTUATION_TRANSLATION = str.maketrans(
    {
        "，": ",",
        "。": ".",
        "、": ",",
        "；": ";",
        "：": ":",
        "！": "!",
        "？": "?",
        "（": "(",
        "）": ")",
    }
)

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
        gap = max(
            0.0,
            float(_field(next_word, "start")) - float(_field(word, "end")),
        )
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
        segment
        for segment in (segments or [])
        if _field(segment, "text")
        and _field(segment, "start") is not None
        and _field(segment, "end") is not None
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
            elif gap >= PHRASE_PAUSE_SECONDS and not rebuilt.endswith(
                (",", ".", ";", ":", "!", "?")
            ):
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
        if char == ":" and ((previous_char.isdigit() and next_char.isdigit()) or next_char == "/"):
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
    normalized = re.sub(r"\s+([,.;:!?])", r"\1", normalized)
    normalized = re.sub(r"[ \t]+", " ", normalized).strip()
    normalized = _limit_sentence_length(normalized)
    normalized = _add_paragraph_breaks(normalized)
    return _format_half_width_punctuation_spacing(normalized)


@dataclass(frozen=True)
class Interpretation:
    """A normalized transcription result or a reason it was rejected."""

    accepted: bool
    text: str
    rejection_reason: Optional[str] = None


class TranscriptionInterpreter:
    """Convert a Groq transcription response into a normalized accepted result."""

    def __init__(self, language_mode=LANGUAGE_TRADITIONAL):
        self.language_mode = normalize_language_mode(language_mode) or LANGUAGE_TRADITIONAL
        try:
            config = "t2s" if self.language_mode == LANGUAGE_SIMPLIFIED else "s2tw"
            self._converter = opencc.OpenCC(config)
        except Exception as error:
            LOGGER.warning("OpenCC initialization failed for %s: %s", config, error)
            self._converter = None

    @property
    def prompt(self):
        """Return the language-specific prompt for the transcription API."""
        return transcription_prompt(self.language_mode)

    def interpret(self, response):
        """Normalize an object or mapping response with text, words, and segments."""
        raw_text = remove_transcription_prompt_leakage(_field(response, "text", ""))
        if not raw_text:
            return Interpretation(False, "", "Groq returned no spoken content.")

        text = punctuate_from_timestamps(
            raw_text,
            _field(response, "words"),
            _field(response, "segments"),
        )
        if self._converter is not None:
            try:
                text = self._converter.convert(text)
            except Exception as error:
                LOGGER.warning("OpenCC conversion failed: %s", error)

        text = normalize_transcription(text)
        if text:
            return Interpretation(True, text)
        return Interpretation(False, "", "Groq returned no spoken content.")
