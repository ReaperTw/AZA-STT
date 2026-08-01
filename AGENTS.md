# AZA-STT agent guide

AZA-STT is a Windows desktop dictation tool. It records microphone audio, sends it to Groq Whisper, interprets the response, and pastes the final text into the active application.

## Source map

- `groq_dictate.py`: Windows integration, tray/UI, recording controls, microphone capture, settings, Groq requests/retries, and paste workflow.
- `transcription_interpreter.py`: the transcription boundary. It accepts a complete Groq response and returns final pasteable text or a rejection reason. Prompt text, prompt-leakage filtering, timestamp punctuation, OpenCC conversion, technology-name corrections, and final formatting belong here.
- `test_groq_dictate.py`: desktop workflow, settings, audio, controls, and packaging regressions.
- `test_transcription_interpreter.py`: public-interface transcription behavior. Prefer testing `TranscriptionInterpreter.interpret()` instead of private helpers.
- `TRANSCRIPTION_GLOSSARY.md`: human-readable vocabulary policy. Runtime truth remains in `transcription_interpreter.py`.
- `build.ps1` and `AZA-STT.spec`: PyInstaller packaging.

Do not treat `archive/`, `bin/`, `build/`, `dist/`, or `release/` as source code. Do not overwrite `bin/` or publish a release unless the user explicitly asks.

## Behavior that must remain stable

- Keep the provider's raw transcription as the source text. Timestamps may add punctuation; never rebuild wording from timestamp tokens because names such as `Groq` may arrive split.
- Keep `Groq` and `Grok` distinct.
- Preserve Latin spacing and protect URLs, versions, decimals, and thousands separators.
- Output uses readable half-width punctuation while preserving the speaker's intended wording.
- `zh-TW` intentionally uses OpenCC `s2tw`; `zh-CN` uses `t2s`. Test both through `TranscriptionInterpreter.interpret()` and the packaged language self-test.
- Reject empty results and known prompt echoes instead of pasting them.
- The packaged app is windowed and may have no usable stdout/stderr. Logging must never crash when console streams are absent.

## Change rules

1. For structural refactors, freeze behavior first. Add or preserve public-interface regression tests, then move code.
2. Do not combine a module move with Prompt, vocabulary, or output-policy changes. Make those separate, reviewable changes backed by real failure examples.
3. Add terms to `PROMPT_TERMS` only when Whisper genuinely needs priming. Add automatic corrections only when the replacement is context-safe.
4. When a real transcription error occurs, record the spoken intent, provider output, and expected final text as the smallest regression test that reproduces it.
5. Keep modules few and responsibility-based. Do not split helpers into files merely to reduce line counts.

## Verification

Use the project's Python 3.10 interpreter when plain `python` is unavailable:

```powershell
& 'C:\Users\user\AppData\Local\Programs\Python\Python310\python.exe' -m py_compile groq_dictate.py transcription_interpreter.py test_groq_dictate.py test_transcription_interpreter.py
& 'C:\Users\user\AppData\Local\Programs\Python\Python310\python.exe' -m unittest -q
```

For packaging-sensitive changes, build a fresh EXE and run the relevant packaged self-tests. At minimum, transcription or language changes must pass `--self-test-language`. The available checks also include FLAC, hotkey, tray, and microphone self-tests.

Before any release, scan source, archives, and binaries for configured Groq API keys. Never print, quote, commit, or upload credentials or local settings files.
