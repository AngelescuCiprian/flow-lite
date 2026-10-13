# Flow-lite

Free, local voice typing for Windows, Romanian first. Hold a key, speak, release, and the
text is typed into whatever app has the cursor: browser, Word, Slack, VS Code, chat apps.

- **Free and private**: speech recognition runs on your own PC with open
  [Whisper](https://github.com/SYSTRAN/faster-whisper) models. No account, no API key,
  no subscription; your audio never leaves the computer.
- **Romanian with correct diacritics** (ă, â, î, ș, ț), plus any other Whisper language.
- **Uses an NVIDIA GPU when available**, otherwise the CPU.

Inspired by Wispr Flow's Windows client (not affiliated).

## Install (once per computer)

1. Install **Python 3.13** from [python.org](https://www.python.org/downloads/) or the Microsoft Store.
2. Get this folder: **Code → Download ZIP** on GitHub (then unzip), or
   `git clone https://github.com/AngelescuCiprian/flow-lite.git`.
3. Double-click **`install.bat`**. It creates a private `.venv`, installs the dependencies
   (plus CUDA libraries if an NVIDIA GPU is present), downloads the speech model once
   (about 1.6 GB) and runs a self-test.

## Use

1. Double-click **`start.bat`** and wait for `GATA!` in the window.
2. Click into any text field, **hold the Right Ctrl key on its own** (not Ctrl+R), speak,
   **release**. The window shows `>> Înregistrez...` while recording and then the text.
3. The text is pasted at the cursor. Your previous clipboard text is restored, and
   dictations are kept out of the Win+V clipboard history.

To start it with Windows: press Win+R, type `shell:startup`, and put a shortcut to `start.bat` there.

## Settings

Edit the top of `start.bat`:

| Setting | Default | Meaning |
|---|---|---|
| `FLOW_LANGS` | `ro,en` | Allowed languages, first preferred. `ro` = Romanian only (most reliable). Each dictation is in one language. |
| `FLOW_MODEL` | `large-v3-turbo` | `large-v3` = most accurate (slower); `medium` / `small` = faster on CPU-only PCs. |
| `FLOW_KEY` | `ctrl_r` | Key to hold: `ctrl_r`, `alt_r`, `f9`, `scroll_lock`, ... |
| `FLOW_INSERT` | `paste` | `type` types the characters one by one, for apps that block pasting; `print` only shows the text in the window (test mode). |
| `FLOW_WORDS` | empty | Names and jargon to recognise better, e.g. `Ciprian,GitHub,Kubernetes`. |
| `FLOW_DEVICE` | `auto` | `cpu` forces the CPU; `cuda` forces the GPU. |

The microphone is the Windows default input device (Settings → System → Sound → Input).

## Speed

Measured with `large-v3-turbo` on a GTX 1050 Ti (4 GB): about 3 seconds for an 8-second
Romanian sentence. Newer GPUs are much faster; CPU-only is slower (try `FLOW_MODEL=small`).

## Troubleshooting

- `.venv\Scripts\python flow_lite.py --check` tests the model, microphone and clipboard;
  add 16-bit `.wav` files after `--check` to transcribe them.
- Nothing is inserted in apps running as administrator: Windows blocks input from normal
  apps into elevated ones. Run `start.bat` as administrator for those.
- An app ignores Ctrl+V: set `FLOW_INSERT=type`.
- "GPU not usable ... using CPU": the GPU or CUDA libraries are not available; it still works on the CPU.

## Pe scurt (română)

1. Instalează Python 3.13, descarcă folderul și rulează `install.bat` (o singură dată).
2. Pornește `start.bat` și așteaptă mesajul `GATA!`.
3. Dă click într-un câmp de text, ține apăsată **tasta Ctrl din dreapta** (singură, nu Ctrl+R),
   vorbește, apoi eliberează tasta: textul apare unde e cursorul.
   Totul rulează gratuit, pe calculatorul tău.
4. Dacă nu apare nimic, uită-te în fereastra Flow-lite: scrie dacă microfonul nu a captat
   sunet sau dacă ai ținut tasta prea puțin. Microfonul folosit este cel implicit din Windows.
