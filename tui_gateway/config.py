import os

DEFAULTS = {
    "SOCRATIC_API_KEY": "",
    "SOCRATIC_BASE_URL": "https://api.deepseek.com/v1",
    "SOCRATIC_MODEL": "deepseek-v4-pro",
}

def load() -> dict:
    cfg = dict(DEFAULTS)
    root = os.environ.get("SOCRATIC_ROOT", os.getcwd())
    env_path = os.path.join(root, ".env")
    try:
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k in cfg:
                    cfg[k] = v
    except OSError:
        pass
    for k in cfg:
        if os.environ.get(k):
            cfg[k] = os.environ[k]
    if not cfg["SOCRATIC_API_KEY"] and os.environ.get("OPENAI_API_KEY"):
        cfg["SOCRATIC_API_KEY"] = os.environ["OPENAI_API_KEY"]
    return cfg

def is_configured() -> bool:
    return bool(load().get("SOCRATIC_API_KEY"))

def env_path() -> str:
    root = os.environ.get("SOCRATIC_ROOT", os.getcwd())
    return os.path.join(root, ".env")
