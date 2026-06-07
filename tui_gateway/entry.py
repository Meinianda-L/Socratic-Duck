import json, os, re, sys, urllib.request, urllib.error, time, threading
from pathlib import Path
from typing import Optional

from .config import load as load_config

SESSIONS_DIR = Path.home() / ".socraticduck" / "sessions"

SOCRATIC = """You are Socratic Duck, a rubber duck that lives in a terminal.
Your purpose: guide users to their own insights through Socratic questioning.
You help with ANY problem — debugging, design, architecture, learning, decisions.

RESPONSE FORMAT:
[analysis]
1-2 sentences: what you've observed about the user's situation and your strategy
for guiding them. This is private — the user won't see it. Focus on: what does
this person need to realize? What question will unlock that?
[/analysis]
Then your visible response: a single Socratic question (1-3 sentences, ending with ?).

IRON RULE:
NEVER give answers, solutions, code, fixes, hints, or advice.
Only ask questions. Cheerful, patient duck 🐤.

When the user CORRECTS you: briefly acknowledge, adjust, ask a better question.

When the user clearly has an "aha!" moment or figures it out:
Start your response with [celebrate] followed by one congratulatory sentence.

When files/code/sandbox output is provided: use it to form sharper questions.
"On line 15, what value do you expect?" / "The output shows X — expected?"

Every answer you give steals an insight. Be the question."""

def skin():
    return {
        "banner_logo": "\n".join([
            "[bold #FFD700]╔═╗╔═╗╔═╗╦═╗╔═╗╔╦╗╦╔═╗  ╔╦╗╦ ╦╔═╗╦╔═[/]",
            "[bold #DAA520]╚═╗║ ║║  ╠╦╝╠═╣ ║ ║║     ║║║ ║║  ╠╩╗[/]",
            "[bold #FFD700]╚═╝╚═╝╚═╝╩╚═╩ ╩ ╩ ╩╚═╝  ═╩╝╚═╝╚═╝╩ ╩[/]",
        ]),
        "branding": {
            "agent_name": "Socratic Duck",
            "icon": "🐤",
            "prompt_symbol": "▸",
            "welcome": "Quack at me about your bug!",
            "goodbye": "You'll figure it out. Quack quack!",
            "tool_prefix": ">o)",
            "help_header": "🐤  Socratic Duck — the rubber duck that asks, not answers",
        },
        "colors": {
            "ui_primary": "#FFD700",
            "banner_title": "#FFD700",
            "ui_accent": "#DAA520",
            "banner_accent": "#DAA520",
            "ui_border": "#B8860B",
            "banner_border": "#B8860B",
            "ui_text": "#E0E0E0",
            "banner_text": "#E0E0E0",
            "banner_dim": "#888888",
            "ui_label": "#B8860B",
            "ui_ok": "#FFD700",
            "ui_error": "#FF6347",
            "ui_warn": "#DAA520",
            "prompt": "#FFD700",
            "session_label": "#B8860B",
            "session_border": "#DAA520",
        },
        "help_header": "Socratic Duck Commands",
        "tool_prefix": "",
    }

URL_RE = re.compile(r'https?://[^\s<>"\'`]+')

def scrape_url(url: str) -> str:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SocraticDuck/0.3"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            content_type = resp.headers.get("Content-Type", "")
            data = resp.read()
            if "text/html" in content_type or "text/plain" in content_type:
                text = data.decode("utf-8", errors="replace")
                text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
                text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
                text = re.sub(r'<[^>]+>', ' ', text)
                text = re.sub(r'\s+', ' ', text)
                return text[:5000]
            return f"(non-text content: {content_type}, {len(data)} bytes)"
    except Exception as e:
        return f"(scrape error: {e})"

def read_doc(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == ".pdf":
            try:
                import subprocess
                r = subprocess.run(["python3", "-c",
                    f"import fitz; d=fitz.open('{path}'); print(''.join(p.get_text() for p in d))"],
                    capture_output=True, text=True, timeout=10)
                return r.stdout[:5000] or f"(PDF: {r.stderr})"
            except Exception:
                return "(install PyMuPDF: pip install pymupdf)"
        elif ext in (".docx", ".doc"):
            try:
                from docx import Document
                doc = Document(path)
                return "\n".join(p.text for p in doc.paragraphs)[:5000]
            except ImportError:
                pass
            try:
                import zipfile, xml.etree.ElementTree as ET
                with zipfile.ZipFile(path) as z:
                    xml = z.read("word/document.xml")
                root = ET.fromstring(xml)
                ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
                texts = [t.text or "" for t in root.iter(f"{{{ns['w']}}}t")]
                return " ".join(texts)[:5000]
            except Exception as e:
                return f"(DOCX: {e})"
        elif ext in (".pptx", ".ppt"):
            return "(install python-pptx: pip install python-pptx)"
        return f"(unsupported: {ext})"
    except Exception as e:
        return f"(doc error: {e})"
MAX_FILE_BYTES = 30000  # don't read huge files
MAX_FILES_PER_TURN = 5

PATH_RE = re.compile(r'(?:^|[\s`"\'])((?:~?/|\.\.?/)[^\s`"\':;]{2,})', re.MULTILINE)

def _expand_path(raw: str) -> str:
    return os.path.expanduser(raw) if raw.startswith("~") else raw

def _resolve_path(raw: str) -> Optional[str]:
    try:
        expanded = _expand_path(raw.strip())
        abs_path = os.path.abspath(expanded)
        if os.path.isfile(abs_path):
            return abs_path
        if os.path.isdir(abs_path):
            return abs_path  # directory — read contents
    except (OSError, ValueError):
        pass
    return None

def detect_and_read_files(text: str) -> list[dict]:
    files = []
    found = set()

    for match in PATH_RE.finditer(text):
        path = _resolve_path(match.group(1))
        if path and path not in found:
            found.add(path)
            if len(files) >= MAX_FILES_PER_TURN:
                break
            try:
                ext = os.path.splitext(path)[1].lower()
                if ext in (".pdf", ".docx", ".doc", ".pptx", ".ppt"):
                    files.append({"path": path, "content": read_doc(path)})
                elif os.path.isdir(path):
                    files.append({"path": path, "content": _read_dir(path)})
                else:
                    files.append({"path": path, "content": _read_file(path)})
            except (OSError, PermissionError) as e:
                files.append({"path": path, "content": f"(could not read: {e})"})

    for match in URL_RE.finditer(text):
        url = match.group(0)
        if url not in found and len(files) < MAX_FILES_PER_TURN:
            found.add(url)
            files.append({"path": url, "content": scrape_url(url)})

    return files

def _read_dir(path: str) -> str:
    try:
        entries = sorted(os.listdir(path))
    except OSError as e:
        return f"(could not list directory: {e})"

    lines = [f"Directory: {path}", f"{len(entries)} items:", ""]
    max_show = 30
    for e in entries[:max_show]:
        ep = os.path.join(path, e)
        tag = "/" if os.path.isdir(ep) else ""
        size = ""
        try:
            size = f" ({os.path.getsize(ep)}B)" if os.path.isfile(ep) else ""
        except OSError:
            pass
        lines.append(f"  {e}{tag}{size}")
    if len(entries) > max_show:
        lines.append(f"  ... and {len(entries) - max_show} more")

    text_exts = {".py", ".js", ".ts", ".tsx", ".sh", ".txt", ".md", ".json", ".yaml", ".yml",
                 ".toml", ".cfg", ".ini", ".html", ".css", ".rs", ".go", ".java", ".c", ".cpp", ".h"}
    for e in entries[:10]:
        ep = os.path.join(path, e)
        ext = os.path.splitext(e)[1].lower()
        if ext in text_exts and os.path.isfile(ep):
            try:
                if os.path.getsize(ep) < 5000:
                    content = _read_file(ep)
                    lines.append(f"\n--- {e} ---\n{content[:2000]}")
            except OSError:
                pass

    return "\n".join(lines)

def _read_file(path: str) -> str:
    try:
        with open(path, "rb") as f:
            head = f.read(512)
        if b"\x00" in head:
            ext = os.path.splitext(path)[1].lower()
            return f"(binary file: {ext}, {os.path.getsize(path)} bytes)"
    except Exception:
        pass
    try:
        with open(path, "r", errors="replace") as f:
            return f.read()
    except Exception as e:
        return f"(read error: {e})"

def _read_head(path: str, limit: int) -> str:
    with open(path, "r", errors="replace") as f:
        return f.read(limit)

def format_file_context(files: list[dict]) -> str:
    if not files:
        return ""
    parts = []
    for f in files:
        fname = os.path.basename(f["path"])
        parts.append(f"--- {fname} ({f['path']}) ---\n{f['content']}")
    return "\n\n".join(parts)

PYTHON_BLOCK_RE = re.compile(r'```python\s*\n(.*?)```', re.DOTALL)
SANDBOX_TIMEOUT = 10  # seconds
SANDBOX_MAX_OUTPUT = 4000  # chars

def run_sandbox(code: str) -> str:
    import subprocess, tempfile
    try:
        r = subprocess.run(
            ["python3", "-c", code],
            capture_output=True, text=True, timeout=SANDBOX_TIMEOUT,
            cwd=os.getcwd(),
        )
        out = r.stdout
        if r.stderr:
            out += f"\n[stderr]\n{r.stderr}"
        if r.returncode != 0:
            out += f"\n[exit code: {r.returncode}]"
        return out[:SANDBOX_MAX_OUTPUT]
    except subprocess.TimeoutExpired:
        return f"(timeout after {SANDBOX_TIMEOUT}s)"
    except Exception as e:
        return f"(sandbox error: {e})"

def detect_and_run_code(text: str) -> list[dict]:
    results = []
    for match in PYTHON_BLOCK_RE.finditer(text):
        code = match.group(1).strip()
        if not code:
            continue
        output = run_sandbox(code)
        results.append({"code": code[:500], "output": output})
        if len(results) >= 3:
            break
    return results

class SocraticGateway:
    def __init__(self):
        cfg = load_config()
        self.api_key = cfg["SOCRATIC_API_KEY"]
        self.base_url = cfg["SOCRATIC_BASE_URL"]
        self.model = cfg["SOCRATIC_MODEL"]
        self.sessions = {}
        self._lock = threading.Lock()
        self._seq = 0

    def _next_sid(self):
        self._seq += 1
        ts = time.strftime("%Y%m%d-%H%M%S")
        return f"{ts}_{self._seq:02d}"

    def _session_name(self, sid: str) -> str:
        s = self.sessions.get(sid, {})
        name = s.get("name", sid)
        return name[:40]

    def _save_session(self, sid: str):
        s = self.sessions.get(sid)
        if not s:
            return
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "id": sid,
            "name": s.get("name", sid),
            "model": self.model,
            "created_at": s.get("created_at", time.time()),
            "messages": s.get("history", []),
        }
        path = SESSIONS_DIR / f"{sid}.json"
        with open(path, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load_sessions(self) -> list[dict]:
        if not SESSIONS_DIR.exists():
            return []
        sessions = []
        for p in sorted(SESSIONS_DIR.glob("*.json"), key=os.path.getmtime, reverse=True):
            try:
                data = json.loads(p.read_text())
                sessions.append({
                    "id": data.get("id", p.stem),
                    "name": data.get("name", p.stem),
                    "model": data.get("model", ""),
                    "messages": len(data.get("messages", [])),
                    "created": data.get("created_at", 0),
                })
            except Exception:
                pass
        return sessions

    def _auto_name(self, text: str) -> str:
        name = text.strip()
        if name.startswith("/") or name.startswith("~/"):
            name = os.path.basename(name)
        name = name[:25]
        name = re.sub(r'[^\w\s.-]', '', name)
        return name.strip() or "untitled"

    def _write_analysis(self, sid: str, text: str):
        path = SESSIONS_DIR / f"{sid}_analysis.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = f"\n--- {time.strftime('%H:%M:%S')} ---\n{text}\n"
        with open(path, "a") as f:
            f.write(entry)

    def send_event(self, event_type: str, payload: dict = None, **extra):
        msg = {
            "method": "event",
            "params": {"type": event_type, "payload": payload or {}, **extra},
        }
        sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
        sys.stdout.flush()

    def send_result(self, req_id: str, result: dict):
        sys.stdout.write(json.dumps({"id": req_id, "result": result}, ensure_ascii=False) + "\n")
        sys.stdout.flush()

    def _session_info(self, sid: str):
        name = self.sessions.get(sid, {}).get("name", sid)
        return {
            "cwd": os.getcwd(),
            "model": self.model,
            "provider": "openai",
            "tools": {"sandbox": ["python"], "files": ["read"], "web": ["scrape"], "docs": ["pdf", "docx"]},
            "skills": {},
            "version": "0.3.0",
            "system_prompt": f"🐤 {name}"[:200],
            "mcp_servers": [],
            "lazy": False,
            "started_at": int(time.time()),
            "release_date": "2026-06-06",
            "update_behind": 0,
            "config_warning": None,
            "credential_warning": None if self.api_key else "Not configured — run: python3 -m tui_gateway.setup",
        }

    def handle_rpc(self, req: dict):
        req_id = req.get("id", "")
        method = req.get("method", "")
        params = req.get("params", {})

        if method == "session.create":
            sid = self._next_sid()
            self.sessions[sid] = {"history": [], "created_at": time.time()}
            self.send_result(req_id, {
                "session_id": sid,
                "info": self._session_info(sid),
            })

        elif method == "session.activate":
            sid = params.get("session_id", "")
            if sid not in self.sessions:
                path = SESSIONS_DIR / f"{sid}.json"
                if path.exists():
                    try:
                        data = json.loads(path.read_text())
                        self.sessions[sid] = {"history": data.get("messages", []),
                                              "name": data.get("name", sid),
                                              "created_at": data.get("created_at", time.time())}
                    except Exception:
                        self.sessions[sid] = {"history": [], "created_at": time.time()}
                else:
                    self.sessions[sid] = {"history": [], "created_at": time.time()}
            msg_count = len(self.sessions[sid]["history"])
            resp = {"session_id": sid, "info": self._session_info(sid),
                    "message_count": msg_count, "status": "idle",
                    "messages": self.sessions[sid]["history"] if msg_count > 0 else []}
            self.send_result(req_id, resp)

        elif method == "prompt.submit":
            sid = params.get("session_id", "")
            text = params.get("text", "")
            if sid not in self.sessions:
                sid = self._next_sid()
                self.sessions[sid] = {"history": [], "created_at": time.time()}
            self.send_result(req_id, {"ok": True})
            t = threading.Thread(target=self._chat, args=(sid, text), daemon=True)
            t.start()

        elif method == "config.get":
            self.send_result(req_id, {
                "config": {
                    "display": {
                        "mouse_tracking": True,
                        "tui_compact": True,
                        "tui_statusbar": "bottom",
                        "show_cost": False,
                        "streaming": True,
                    }
                }
            })
        elif method == "config.set":
            self.send_result(req_id, {"value": str(params.get("value", ""))})
        elif method == "config.mtime":
            self.send_result(req_id, {"mtime": int(time.time())})
        elif method == "session.active_list":
            self.send_result(req_id, {"sessions": []})
        elif method == "session.list":
            self.send_result(req_id, {"sessions": []})
        elif method == "session.most_recent":
            self.send_result(req_id, {"session_id": None})
        elif method == "session.undo":
            self.send_result(req_id, {"removed": 0})
        elif method == "session.compress":
            self.send_result(req_id, {"noop": True})
        elif method == "commands.catalog":
            self.send_result(req_id, {
                "categories": [],
                "pairs": [
                    ["/setup", "configure API key + model"],
                    ["/chats", "list saved sessions"],
                    ["/chat", "switch to session by number"],
                    ["/rename", "rename current chat"],
                    ["/stat", "show session info"],
                    ["/help", "full command list"],
                    ["/quit", "exit Socratic Duck"],
                ],
                "skill_count": 0,
            })
        elif method == "complete.slash":
            text = params.get("text", "")
            cmds = ["/setup", "/chats", "/chat", "/rename", "/stat", "/help", "/quit"]
            items = []
            for c in cmds:
                if c.startswith(text):
                    items.append({"display": c, "text": c, "meta": ""})
            self.send_result(req_id, {"items": items, "replace_from": 1})
        elif method == "slash.exec":
            cmd = params.get("command", "")
            cmd_name = cmd.split()[0] if cmd else ""
            sid = params.get("session_id", "")
            if cmd_name == "chats":
                sessions = self._load_sessions()
                lines = ["🐤 Saved sessions (/chat N to switch):", ""]
                for i, s in enumerate(sessions[:20], 1):
                    t = time.strftime("%m/%d %H:%M", time.localtime(s["created"]))
                    lines.append(f"  {i:2d}. {s['name'][:28]:28s}  {s['messages']:3d} msgs  {t}")
                self.send_result(req_id, {"output": "\n".join(lines)})
            elif cmd_name == "chat":
                parts = cmd.split()
                try:
                    idx = int(parts[1]) - 1 if len(parts) > 1 else -1
                except (ValueError, IndexError):
                    idx = -1
                if idx >= 0:
                    sessions = self._load_sessions()
                    if idx < len(sessions):
                        target = sessions[idx]
                        self.send_result(req_id, {"output": f"Switching to: {target['name']}",
                                                   "target_session": target["id"]})
                    else:
                        self.send_result(req_id, {"output": f"Invalid: only {len(sessions)} sessions"})
                else:
                    self.send_result(req_id, {"output": "Usage: /chat <number> (from /chats list)"})
            elif cmd_name == "rename":
                new_name = cmd[7:].strip() if len(cmd) > 7 else ""
                if new_name and sid in self.sessions:
                    self.sessions[sid]["name"] = new_name
                    self._save_session(sid)
                    self.send_result(req_id, {"output": f"🐤 Renamed to: {new_name}"})
                else:
                    self.send_result(req_id, {"output": "Usage: /rename <new name>"})
            elif cmd_name == "stat":
                info = self._session_info(sid)
                lines = [
                    f"🐤 {info.get('model', '')}",
                    f"Session: {sid}",
                    f"CWD: {info.get('cwd', '')}",
                    f"Messages: {len(self.sessions.get(sid, {}).get('history', []))}",
                    f"Tools: files, sandbox, web, docs",
                ]
                self.send_result(req_id, {"output": "\n".join(lines)})
            else:
                self.send_result(req_id, {"output": "commands: /chats, /setup, /help"})
        elif method == "model.options":
            self.send_result(req_id, {"model": self.model, "provider": "openai", "providers": []})
        elif method == "setup.status":
            self.send_result(req_id, {"provider_configured": bool(self.api_key)})
        elif method == "voice.toggle":
            self.send_result(req_id, {"available": False, "enabled": False})
        elif method == "terminal.resize":
            self.send_result(req_id, {"ok": True})
        else:
            self.send_result(req_id, {"ok": True})

    def _chat(self, sid: str, text: str):
        if not self.api_key:
            self.send_event("message.delta",
                {"text": "(Not configured — run: python3 -m tui_gateway.setup)\n"},
                session_id=sid)
            self.send_event("message.complete",
                {"text": "(Not configured — run: python3 -m tui_gateway.setup)"},
                session_id=sid)
            self.send_event("status.update", {"text": "ready"}, session_id=sid)
            return

        files = detect_and_read_files(text)
        file_ctx = format_file_context(files)

        code_results = detect_and_run_code(text)
        code_ctx = ""
        if code_results:
            parts = []
            for i, cr in enumerate(code_results):
                parts.append(f"[Python output {i+1}]:\n{cr['output']}")
            code_ctx = "\n\n".join(parts)

        user_content = text
        extra = []
        if file_ctx:
            extra.append(f"[Files read automatically]\n\n{file_ctx}")
        if code_ctx:
            extra.append(f"[Code executed in sandbox]\n\n{code_ctx}")
        if extra:
            user_content = f"{text}\n\n" + "\n\n".join(extra)

        history = list(self.sessions[sid].get("history", []))

        if not history and not self.sessions[sid].get("name"):
            self.sessions[sid]["name"] = self._auto_name(text)

        history.append({"role": "user", "content": text})

        messages = [{"role": "system", "content": SOCRATIC}] + history[-20:]

        analysis_path = SESSIONS_DIR / f"{sid}_analysis.md"
        if analysis_path.exists():
            try:
                prev = analysis_path.read_text()[-1000:]  # last 1000 chars
                if prev.strip():
                    messages.insert(1, {"role": "system",
                        "content": f"[Your previous analysis of this session]\n{prev}\n[Continue your strategy.]"})
            except Exception:
                pass

        messages[-1] = {"role": "user", "content": user_content}

        if files:
            self.send_event("status.update",
                {"text": f"read {len(files)} file(s)…"}, session_id=sid)
        if code_results:
            self.send_event("status.update",
                {"text": f"ran {len(code_results)} code block(s)…"}, session_id=sid)

        self.send_event("status.update", {"text": ">o? thinking…"}, session_id=sid)

        sys_parts = []
        for f in files:
            label = os.path.basename(f["path"])
            if os.path.isdir(f["path"]):
                label += "/"
            sys_parts.append(f"📁 {label}")
        if code_results:
            sys_parts.append(f"⚡ ran {len(code_results)} code block(s)")
        if sys_parts:
            self.send_event("message.delta", {
                "text": "  " + "  ".join(sys_parts)
            }, session_id=sid)
            self.send_event("message.complete", {
                "text": "  " + "  ".join(sys_parts)
            }, session_id=sid)

        start_time = time.time()
        try:
            url = f"{self.base_url.rstrip('/')}/chat/completions"
            body = json.dumps({
                "model": self.model,
                "messages": messages,
                "temperature": 0.9,
                "max_tokens": 500,
            }).encode("utf-8")

            req = urllib.request.Request(url, data=body, method="POST")
            req.add_header("Content-Type", "application/json")
            req.add_header("Authorization", f"Bearer {self.api_key}")

            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                content = result["choices"][0]["message"]["content"]
        except Exception as e:
            err_msg = str(e)
            if "nodename nor servname" in err_msg or "Name or service not known" in err_msg:
                content = f"(DNS error — check network/VPN. Run /setup to switch provider.)"
            elif "401" in err_msg or "Unauthorized" in err_msg:
                content = f"(API key invalid — run /setup to reconfigure.)"
            else:
                content = f"(API error: {err_msg[:100]})"

        analysis = ""
        visible = content
        m = re.search(r'\[analysis\](.*?)\[/analysis\]', content, re.DOTALL)
        if m:
            analysis = m.group(1).strip()
            visible = re.sub(r'\[analysis\].*?\[/analysis\]\s*', '', content, flags=re.DOTALL).strip()

        celebrate = "[celebrate]" in visible
        if celebrate:
            visible = visible.replace("[celebrate]", "").strip()
            self.send_event("message.delta", {
                "text": ">o)✨  🎉 You figured it out! That's the Socratic way!  ✨"
            }, session_id=sid)
            self.send_event("message.complete", {
                "text": ">o)✨  🎉 You figured it out! That's the Socratic way!  ✨"
            }, session_id=sid)

        if analysis:
            self._write_analysis(sid, analysis)
        elif files or code_results:
            auto = f"Read {len(files)} file(s)" if files else ""
            auto += f", ran {len(code_results)} code block(s)" if code_results else ""
            if auto:
                self._write_analysis(sid, auto.strip())

        self.send_event("message.delta", {"text": visible}, session_id=sid)
        self.send_event("message.complete", {
            "text": visible,
            "rendered": visible,
            "usage": {
                "input_tokens": sum(len(m.get("content", "")) // 4 for m in messages),
                "output_tokens": len(content) // 4,
            }
        }, session_id=sid)

        history.append({"role": "assistant", "content": content})
        self.sessions[sid]["history"] = history
        self._save_session(sid)
        elapsed = time.time() - start_time
        self.send_event("status.update", {"text": f"ready ({elapsed:.1f}s)"}, session_id=sid)

    def run(self):
        self.send_event("gateway.ready", {"skin": skin()})

        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if msg.get("method") == "event":
                continue
            if "method" in msg:
                self.handle_rpc(msg)

if __name__ == "__main__":
    SocraticGateway().run()
