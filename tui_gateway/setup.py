#!/usr/bin/env python3
import os, sys
from pathlib import Path

from .colors import Colors, color

def print_header(title: str):
    print()
    print(color(f"◆ {title}", Colors.CYAN, Colors.BOLD))

def print_info(msg: str):
    print(color(f"  {msg}", Colors.DIM))

def print_success(msg: str):
    print(color(f"  ✓ {msg}", Colors.GREEN))

def print_warning(msg: str):
    print(color(f"  ⚠ {msg}", Colors.YELLOW))

def print_error(msg: str):
    print(color(f"  ✗ {msg}", Colors.RED))

def prompt(question: str, default: str = "", password: bool = False) -> str:
    display = f"{question} [{default}]: " if default else f"{question}: "
    try:
        if password:
            from .secret_prompt import masked_secret_prompt
            value = masked_secret_prompt(color(display, Colors.YELLOW))
        else:
            value = input(color(display, Colors.YELLOW))
        return value.strip() or default
    except (KeyboardInterrupt, EOFError):
        print()
        sys.exit(1)

def prompt_choice(question: str, choices: list, default: int = 0) -> int:
    print(color(question, Colors.YELLOW))
    for i, c in enumerate(choices):
        m = "●" if i == default else "○"
        line = color(f"  {m} {c}", Colors.GREEN) if i == default else f"  {m} {c}"
        print(line)
    print_info(f"  Enter for default ({default + 1})  Ctrl+C to exit")
    while True:
        try:
            val = input(color(f"  Select [1-{len(choices)}] ({default + 1}): ", Colors.DIM))
            if not val:
                return default
            idx = int(val) - 1
            if 0 <= idx < len(choices):
                return idx
            print_error(f"Please enter a number between 1 and {len(choices)}")
        except ValueError:
            print_error("Please enter a number")
        except (KeyboardInterrupt, EOFError):
            print()
            sys.exit(1)

def prompt_yes_no(question: str, default: bool = True) -> bool:
    ds = "Y/n" if default else "y/N"
    while True:
        try:
            val = input(color(f"{question} [{ds}]: ", Colors.YELLOW)).strip().lower()
        except (KeyboardInterrupt, EOFError):
            print(); sys.exit(1)
        if not val: return default
        if val in ("y", "yes"): return True
        if val in ("n", "no"): return False
        print_error("Please enter 'y' or 'n'")

def _env_path() -> Path:
    root = os.environ.get("SOCRATIC_ROOT", os.getcwd())
    return Path(root) / ".env"

def _read_env() -> dict:
    cfg = {}
    p = _env_path()
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            cfg[k.strip()] = v.strip().strip('"').strip("'")
    return cfg

def _write_env(cfg: dict):
    lines = []
    for k in ("SOCRATIC_API_KEY", "SOCRATIC_BASE_URL", "SOCRATIC_MODEL"):
        if cfg.get(k):
            lines.append(f"{k}={cfg[k]}")
    _env_path().write_text("\n".join(lines) + "\n")

PROVIDERS = [
    ("OpenAI",     "https://api.openai.com/v1",           "https://platform.openai.com/api-keys"),
    ("DeepSeek",   "https://api.deepseek.com/v1",         "https://platform.deepseek.com/api_keys"),
    ("Anthropic",  "https://api.anthropic.com/v1",        "https://console.anthropic.com/keys"),
    ("Groq",       "https://api.groq.com/openai/v1",      "https://console.groq.com/keys"),
    ("Together",   "https://api.together.xyz/v1",         "https://api.together.xyz/settings/api-keys"),
    ("Custom URL", "", ""),
]

DEFAULT_MODELS = {
    "https://api.openai.com/v1":          ["gpt-4o-mini", "gpt-4o", "gpt-4.1"],
    "https://api.deepseek.com/v1":        ["deepseek-v4-pro", "deepseek-chat", "deepseek-reasoner"],
    "https://api.anthropic.com/v1":       ["claude-sonnet-4-20250514", "claude-haiku-3-5"],
    "https://api.groq.com/openai/v1":     ["llama-4-maverick-17b", "deepseek-r1-distill-llama-70b"],
    "https://api.together.xyz/v1":        ["meta-llama/Llama-4-Maverick-17B", "deepseek-ai/DeepSeek-R1"],
}

BANNER = f"""
{color('╔═╗ ╦ ╦ ╔═╗ ╦╔═', Colors.YELLOW, Colors.BOLD)}
{color('║ ║ ║ ║ ║   ╠╩╗', Colors.YELLOW)}
{color('╚═╝ ╚═╝ ╚═╝ ╩ ╩', Colors.YELLOW, Colors.BOLD)}
{color('🐤  Socratic Duck — Setup Wizard', Colors.DIM)}
"""

def main():
    print(BANNER)
    cfg = _read_env()
    if cfg.get("SOCRATIC_API_KEY"):
        masked = "***" + cfg["SOCRATIC_API_KEY"][-4:]
        print()
        print_info(f"Current config: {_env_path()}")
        print_info(f"  Provider: {cfg.get('SOCRATIC_BASE_URL', '')}")
        print_info(f"  Model:    {cfg.get('SOCRATIC_MODEL', '')}")
        print_info(f"  API key:  {masked}")
        print()
        if not prompt_yes_no("Reconfigure?", default=False):
            print_success("Keeping existing config.")
            print_info("Run sorduck to start.")
            print()
            return

    print_header("Choose Provider")
    names = [f"{p[0]:12}  {p[1]}" if p[1] else f"{p[0]:12}  (enter your own URL)" for p in PROVIDERS]
    current_url = cfg.get("SOCRATIC_BASE_URL", "")
    default_idx = 0
    for i, p in enumerate(PROVIDERS):
        if p[1] == current_url:
            default_idx = i; break

    idx = prompt_choice("Select your LLM provider:", names, default_idx)
    _, base_url, key_url = PROVIDERS[idx]

    if not base_url:
        base_url = prompt("  Custom API base URL", current_url or "https://")
        key_url = ""

    print()
    print_header("API Key")
    if key_url:
        print_info(f"Get your key at: {key_url}")
    print_info(f"Stored in {_env_path()}")
    print()

    current_key = cfg.get("SOCRATIC_API_KEY", "")
    api_key = prompt("  API key", default="", password=True) or current_key
    if not api_key:
        print_warning("No API key provided. Run sorduck setup to configure later.")

    print()
    print_header("Choose Model")
    models = DEFAULT_MODELS.get(base_url, ["gpt-4o-mini"])
    current_model = cfg.get("SOCRATIC_MODEL", models[0])
    default_model_idx = models.index(current_model) if current_model in models else 0

    idx2 = prompt_choice("Select default model:", models, default_model_idx)
    model = models[idx2] if idx2 < len(models) else current_model

    cfg["SOCRATIC_API_KEY"] = api_key
    cfg["SOCRATIC_BASE_URL"] = base_url
    cfg["SOCRATIC_MODEL"] = model
    _write_env(cfg)

    print()
    print_header("Setup Complete")
    print_success(f"Config saved to {_env_path()}")
    print_info(f"  Provider: {base_url}")
    print_info(f"  Model:    {model}")
    print_info(f"  API key:  {'***' + api_key[-4:] if len(api_key) > 4 else '(not set)'}")
    print()
    print_info("Run:  sorduck")
    print()

if __name__ == "__main__":
    main()
