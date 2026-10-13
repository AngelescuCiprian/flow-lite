"""Flow-lite: hold a key, speak (Romanian first), release, and the text appears in the focused app.

Everything runs locally and for free: faster-whisper (open Whisper models) on your GPU or CPU,
no accounts, no API keys, no audio leaves the machine.

Pipeline (modelled on Wispr Flow's Windows client):
  16 kHz mono microphone audio -> Whisper speech-to-text -> small text fixes ->
  clipboard + simulated Ctrl+V -> the previous clipboard text is restored.

Settings (environment variables, see start.bat):
  FLOW_LANGS   allowed languages, first is preferred (default "ro"); "ro,en" picks between them
  FLOW_MODEL   faster-whisper model (default "large-v3-turbo"; "large-v3" is more accurate,
               "medium" or "small" are faster on CPU-only machines)
  FLOW_DEVICE  "auto" (default: NVIDIA GPU if it works, otherwise CPU), "cuda" or "cpu"
  FLOW_KEY     key to hold while speaking (default "ctrl_r" = Right Ctrl; e.g. "alt_r", "f9")
  FLOW_INSERT  "paste" (default) or "type" for apps that block Ctrl+V
  FLOW_WORDS   comma list of names/jargon to bias recognition, e.g. "Ciprian,GitHub,Ghidra"

Run `python flow_lite.py --check` to test the model, microphone and clipboard without dictating.
"""

import os
import queue
import re
import sys
import threading
import time
import wave
from pathlib import Path


def _use_pip_cuda_libraries() -> None:
    """Let CTranslate2 find cuBLAS/cuDNN installed from requirements-gpu.txt (nvidia-* wheels)."""
    import importlib.util

    spec = importlib.util.find_spec("nvidia")
    if spec is None or not spec.submodule_search_locations:
        return
    for base in spec.submodule_search_locations:
        for bin_dir in Path(base).glob("*/bin"):
            os.add_dll_directory(str(bin_dir))
            os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ.get("PATH", "")


_use_pip_cuda_libraries()
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("HF_HUB_VERBOSITY", "error")

import numpy as np  # noqa: E402
import sounddevice as sd  # noqa: E402
import win32clipboard  # noqa: E402
from faster_whisper import WhisperModel  # noqa: E402
from faster_whisper.utils import download_model  # noqa: E402
from pynput import keyboard  # noqa: E402

SAMPLE_RATE = 16_000  # Wispr Flow also records 16 kHz mono
LANGS = [code.strip() for code in os.getenv("FLOW_LANGS", "ro").split(",") if code.strip()]
WORDS = [w.strip() for w in os.getenv("FLOW_WORDS", "").split(",") if w.strip()]
MODEL_NAME = os.getenv("FLOW_MODEL", "large-v3-turbo")
DEVICE = os.getenv("FLOW_DEVICE", "auto")
INSERT_MODE = os.getenv("FLOW_INSERT", "paste")
HOLD_KEY_NAME = os.getenv("FLOW_KEY", "ctrl_r")

# Whisper sometimes emits the legacy cedilla letters; standard Romanian uses comma-below.
_CEDILLA_TO_COMMA = str.maketrans({"ş": "ș", "ţ": "ț", "Ş": "Ș", "Ţ": "Ț"})
# Standalone hesitation sounds Whisper occasionally writes out.
_FILLERS = re.compile(r"(?<!\w)(?:ă+m*|î+m*|e+h*m+|h?m{2,}|uh+|um+)[,.]?(?!\w)\s*", re.IGNORECASE)

# A prompt in the target language nudges Whisper towards diacritics and punctuation.
_PROMPTS = {
    "ro": "Bună ziua. Aceasta este o dictare în limba română, cu diacritice: ă, â, î, ș, ț.",
    "en": "Hello. This is an English dictation with proper punctuation.",
}


def tidy(text: str, language: str) -> str:
    cleaned = re.sub(r"\s{2,}", " ", _FILLERS.sub("", text)).strip()
    if cleaned and text[:1].isupper():  # a removed leading filler took the capital letter with it
        cleaned = cleaned[0].upper() + cleaned[1:]
    if language == "ro":
        cleaned = cleaned.translate(_CEDILLA_TO_COMMA)
    return cleaned


def parse_hold_key(name: str):
    if hasattr(keyboard.Key, name):
        return getattr(keyboard.Key, name)
    if len(name) == 1:
        return keyboard.KeyCode.from_char(name)
    raise SystemExit(f"Unknown FLOW_KEY {name!r}; use a pynput Key name such as ctrl_r, alt_r or f9")


class Transcriber:
    def __init__(self) -> None:
        self.model, self.device = self._load()

    @staticmethod
    def _model_path() -> str:
        if os.path.isdir(MODEL_NAME):
            return MODEL_NAME
        try:
            return download_model(MODEL_NAME, local_files_only=True)  # works offline after the first run
        except Exception:
            return download_model(MODEL_NAME)  # first run: free download from Hugging Face

    @classmethod
    def _load(cls) -> tuple[WhisperModel, str]:
        path = cls._model_path()
        if DEVICE in ("auto", "cuda"):
            try:
                model = WhisperModel(path, device="cuda", compute_type="auto")
                # A missing cuBLAS/cuDNN only fails on first use, so warm the model up here.
                segments, _ = model.transcribe(np.zeros(SAMPLE_RATE, dtype=np.float32), language=LANGS[0])
                list(segments)
                return model, "cuda"
            except Exception as exc:  # no NVIDIA GPU, unsupported GPU or missing CUDA libraries
                if DEVICE == "cuda":
                    raise
                print(f"GPU not usable ({str(exc).splitlines()[0]}); using CPU instead.")
        return WhisperModel(path, device="cpu", compute_type="int8"), "cpu"

    def _run(self, audio: np.ndarray, language: str | None):
        prompt = " ".join(filter(None, [_PROMPTS.get(language or LANGS[0], ""), ", ".join(WORDS)]))
        segments, info = self.model.transcribe(
            audio,
            language=language,
            initial_prompt=prompt or None,
            vad_filter=True,  # drops leading/trailing silence
            beam_size=5,
        )
        return " ".join(s.text.strip() for s in segments).strip(), info

    def transcribe(self, audio: np.ndarray) -> tuple[str, str]:
        if len(LANGS) == 1:
            text, _ = self._run(audio, LANGS[0])
            return text, LANGS[0]
        # Several allowed languages: let Whisper detect, but never leave the allowed set
        # (the same "select only the languages you speak" rule Wispr documents).
        text, info = self._run(audio, None)
        if info.language in LANGS:
            return text, info.language
        probs = dict(info.all_language_probs or [])
        best = max(LANGS, key=lambda code: probs.get(code, 0.0))
        text, _ = self._run(audio, best)
        return text, best


_EXCLUDE_FROM_HISTORY = win32clipboard.RegisterClipboardFormat("ExcludeClipboardContentFromMonitorProcessing")


def read_clipboard_text() -> str | None:
    win32clipboard.OpenClipboard()
    try:
        if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
            return win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
        return None
    finally:
        win32clipboard.CloseClipboard()


def write_clipboard_text(text: str, hide_from_history: bool) -> None:
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_UNICODETEXT, text)
        if hide_from_history:  # keeps dictations out of Win+V history, as Wispr's helper does
            win32clipboard.SetClipboardData(_EXCLUDE_FROM_HISTORY, b"\0")
    finally:
        win32clipboard.CloseClipboard()


def insert_text(text: str, kb: keyboard.Controller) -> None:
    if INSERT_MODE == "type":
        kb.type(text)  # Unicode key events; slower, but works where paste is blocked
        return
    previous = read_clipboard_text()  # only plain text is restored
    write_clipboard_text(text, hide_from_history=True)
    with kb.pressed(keyboard.Key.ctrl):
        kb.press("v")
        kb.release("v")
    time.sleep(0.3)  # let the target app read the clipboard before restoring it
    if previous is not None:
        write_clipboard_text(previous, hide_from_history=False)


class Recorder:
    def __init__(self) -> None:
        self.chunks: list[np.ndarray] = []
        self.stream: sd.InputStream | None = None

    def start(self) -> None:
        self.chunks = []
        self.stream = sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype="float32",
            blocksize=640,  # 40 ms, the same chunk size as Wispr's recorder worklet
            callback=lambda data, frames, t, status: self.chunks.append(data[:, 0].copy()),
        )
        self.stream.start()

    def stop(self) -> np.ndarray:
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        return np.concatenate(self.chunks) if self.chunks else np.zeros(0, dtype=np.float32)


def load_wav(path: str) -> np.ndarray:
    """Read a 16-bit PCM WAV as 16 kHz mono float32 (faster-whisper's own decoder needs a PyAV
    version compatible with it; the live app never decodes files, so --check avoids PyAV)."""
    with wave.open(path, "rb") as wav:
        rate, channels, width = wav.getframerate(), wav.getnchannels(), wav.getsampwidth()
        frames = wav.readframes(wav.getnframes())
    if width != 2:
        raise SystemExit(f"{path}: --check expects 16-bit PCM WAV files")
    audio = np.frombuffer(frames, dtype=np.int16).reshape(-1, channels).mean(axis=1) / 32768.0
    if rate != SAMPLE_RATE:
        target = int(len(audio) * SAMPLE_RATE / rate)
        audio = np.interp(np.linspace(0, len(audio) - 1, target), np.arange(len(audio)), audio)
    return audio.astype(np.float32)


def check() -> None:
    """Self-test: model, microphone and clipboard, without dictating into any app."""
    started = time.perf_counter()
    transcriber = Transcriber()
    print(f"Model {MODEL_NAME} loaded on {transcriber.device} in {time.perf_counter() - started:.1f}s")
    device = sd.query_devices(kind="input")
    print(f"Microphone: {device['name']}")
    previous = read_clipboard_text()
    write_clipboard_text("flow-lite clipboard test ș ț", hide_from_history=True)
    ok = read_clipboard_text() == "flow-lite clipboard test ș ț"
    if previous is not None:
        write_clipboard_text(previous, hide_from_history=False)
    print(f"Clipboard: {'ok' if ok else 'FAILED'}")
    for path in sys.argv[2:]:  # optional 16-bit PCM WAV files to transcribe
        started = time.perf_counter()
        text, language = transcriber.transcribe(load_wav(path))
        print(f"[{language}] {time.perf_counter() - started:.1f}s  {tidy(text, language)}")


def main() -> None:
    hold_key = parse_hold_key(HOLD_KEY_NAME)
    print(f"Loading {MODEL_NAME} for languages {LANGS} (first run downloads the model) ...")
    transcriber = Transcriber()
    print(f"Running on {transcriber.device}.")
    recorder = Recorder()
    kb = keyboard.Controller()
    jobs: queue.Queue[np.ndarray] = queue.Queue()
    recording = threading.Event()

    def worker() -> None:
        while True:
            audio = jobs.get()
            if len(audio) < SAMPLE_RATE * 0.3:
                continue  # accidental tap
            try:
                started = time.perf_counter()
                text, language = transcriber.transcribe(audio)
                text = tidy(text, language)
                if text:
                    insert_text(text + " ", kb)
                print(f"[{language}] {time.perf_counter() - started:.1f}s  {text}")
            except Exception as exc:
                print(f"Dictation failed: {exc}")

    threading.Thread(target=worker, daemon=True).start()

    # Keyboard hook callbacks must return quickly (Windows drops slow low-level hooks),
    # so they only start/stop the recorder and hand the audio to the worker thread.
    def on_press(key) -> None:
        if key == hold_key and not recording.is_set():
            recording.set()
            recorder.start()

    def on_release(key) -> None:
        if key == hold_key and recording.is_set():
            recording.clear()
            jobs.put(recorder.stop())

    print(f"Hold {HOLD_KEY_NAME} and speak; release to insert the text. Close this window to quit.")
    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()


if __name__ == "__main__":
    check() if "--check" in sys.argv[1:2] else main()
