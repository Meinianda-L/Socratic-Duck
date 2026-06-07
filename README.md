# 🐤 Socratic Duck

**An AI rubber duck that lives in your terminal. It reads your code, understands your problems,knows how to fix them, but *never* gives you the answer.**

Instead, it uses Socratic questioning to guide you to your own insight.

> ChatGPT gives you answers. Socratic Duck tell you how to get to those anwsers.

---

## Why?

[Rubber duck debugging](https://en.wikipedia.org/wiki/Rubber_duck_debugging) works — explaining your problem out loud forces you to think differently. But a real rubber duck can't ask follow-up questions or read your code. Socratic Duck can.

Backed by cognitive science: you remember solutions you discover far better than solutions you're told.

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/Meinianda-L/socratic-duck.git
cd socratic-duck

# 2. Install Node deps + build ink engine
cd ui-tui && npm install && cd ..
./run.sh build

# 3. Configure API (interactive)
./run.sh setup

# 4. Launch
./run.sh
```

Optional: symlink to your PATH so you can type `sorduck` from anywhere:

```bash
ln -s "$(pwd)/run.sh" ~/bin/sorduck   # ensure ~/bin is in $PATH
sorduck
```

**Prerequisites**: Python 3.9+, Node.js 18+, npm.

---

## How It Works

### 🐤 Socratic Mode (default)

Paste a file path, describe a bug, or just start thinking out loud. Socratic Duck reads your code, then asks targeted questions that guide you to the answer — *without ever telling you directly*.

```
>o) I see your login function on line 23 builds SQL by
    string interpolation. What happens when a single
    quote enters that query?

▸  It probably breaks the SQL syntax...

>o) What would you expect `cursor.execute()` to do with
    a malformed query?
```

When you have your "aha!" moment, the duck celebrates:

```
>o)✨  🎉 You figured it out! That's the Socratic way!  ✨
```

### 📁 File Reading

Just paste any file path in your message — Socratic Duck automatically reads it and includes it in context:

```
▸  src/auth.py handles the login flow but throws on line 47

>o) I've read src/auth.py (142 lines). What happens to the
    token variable when the user field is None on line 46?
```

Supports `.py`, `.js`, `.ts`, `.md`, `.txt`, `.docx`, and directory paths.

### ⚡ Code Sandbox

Paste Python code blocks — the duck runs them in a sandbox and shows the output:

````
▸  `\`\`\`python
   x = [1,2,3]
   print(x[3])
   \`\`\``

⚡ ran 1 code block(s)
>o) Interesting — IndexError at x[3]. What's the length of x?
````

### 🔍 Web Scraping

Paste a URL — the duck fetches the page and analyzes it.

### 📝 Analysis Notes

The duck writes private analysis notes as `[analysis]` blocks — parsed out of the visible response and saved per session for your reference.

---

## Commands

| Command | Description |
|---------|-------------|
| `/chats` | List saved sessions |
| `/chat <N>` | Switch to session N |
| `/rename <name>` | Rename current session |
| `/stat` | Show session info (model, CWD, messages) |
| `/setup` | Configure API provider |
| `/clear` | Clear current session |
| `/quit` | Exit Socratic Duck |

---

## Features

- **Polished TUI** — Hermes-style Ink/React terminal UI with gold theme
- **Zero Python deps** — gateway uses only stdlib (urllib, json, subprocess)
- **Session persistence** — auto-saved under `~/.socraticduck/sessions/`
- **File reading** — paths, directories, DOCX, PDF, URLs; auto-detected from messages
- **Code sandbox** — Python blocks executed live with output shown
- **Auto-compact** — long conversations automatically compacted
- **Celebration easter egg** — duck reacts when you figure things out
- **Multi-provider** — OpenAI, Anthropic, DeepSeek, or any compatible API

---

## Architecture

```
SocraticDuck/
├── run.sh                    # Launch script (builds hermes-ink, starts gateway + TUI)
├── tui_gateway/
│   ├── entry.py              # Main gateway — JSON-RPC, LLM calls, file/URL/sandbox
│   ├── config.py             # .env reader/writer
│   ├── setup.py              # Interactive setup wizard (sorduck setup)
│   ├── colors.py             # Terminal color helpers
│   └── secret_prompt.py      # Masked password prompt
├── ui-tui/                   # Hermes TUI frontend (React Ink)
│   ├── src/
│   │   ├── entry.tsx         # TUI entry point
│   │   ├── components/       # UI components (branding, layout, chrome, prompts)
│   │   ├── app/slash/        # Slash command handlers
│   │   └── lib/              # Core libraries (RPC, history, editor, terminal)
│   └── packages/hermes-ink/  # Ink rendering engine (forked from Hermes)
└── .env                      # API key & provider config (gitignored)
```

**Key dependencies**: Python 3.9+ (stdlib only), Node.js 18+ (TUI frontend).

---

## Configuration

Via `sorduck setup` (interactive) or manually in `.env`:

```bash
SOCRATIC_API_KEY="sk-..."        # Required
SOCRATIC_BASE_URL="https://..."  # API endpoint
SOCRATIC_MODEL="" # Model name
```

All config uses the `SOCRATIC_` prefix. No JSON config files.

---

## License

MIT
