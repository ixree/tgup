 cat tgup.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tgup — Termux → Telegram file uploader with optional forward to channel / group / topic.
"""
import os, sys, json, re, time, requests

__version__ = "1.0.0"
CONFIG_FILE = os.path.expanduser("~/.tgup.json")

# every extension the picker offers
EXT_CATALOG = (
    # docs
    ".txt", ".md", ".pdf", ".log",
    # code
    ".py", ".sh", ".js", ".html", ".css",
    # data
    ".json", ".csv", ".xml", ".yaml", ".yml", ".sql",
    # archives
    ".zip", ".tar", ".gz", ".7z",
    # config
    ".conf", ".cfg", ".ini", ".env", ".toml",
)

# default selection on first run
DEFAULT_EXT = (
    ".txt", ".py", ".sh", ".md", ".json", ".csv", ".log", ".pdf", ".zip",
)


# ─── COLORS ───────────────────────────────────────────────────────────────────
class C:
    R      = '\033[0m'
    BOLD   = '\033[1m'
    DIM    = '\033[2m'
    ACCENT = '\033[38;5;81m'
    TEXT   = '\033[38;5;253m'
    DIMTX  = '\033[38;5;244m'
    WHITE  = '\033[38;5;255m'
    TITLE  = '\033[1;97m'
    GREEN  = '\033[38;5;120m'
    YELLOW = '\033[38;5;221m'
    RED    = '\033[38;5;210m'
    PURPLE = '\033[38;5;183m'
    BLUE   = '\033[38;5;117m'
    PINK   = '\033[38;5;218m'
    ORANGE = '\033[38;5;216m'

    @classmethod
    def off(cls):
        for k in list(vars(cls)):
            if not k.startswith('_') and isinstance(getattr(cls, k), str):
                setattr(cls, k, '')


ANSI_RE = re.compile(r'\033\[[0-9;]*m')

def vlen(s): return len(ANSI_RE.sub('', s))

def line(): return "  " + C.DIMTX + ("─" * 44) + C.R

def pause():
    try: input("  " + C.DIMTX + "press ENTER" + C.R)
    except (EOFError, KeyboardInterrupt): print()


# ─── CONFIG ───────────────────────────────────────────────────────────────────
def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)
    try: os.chmod(CONFIG_FILE, 0o600)
    except OSError: pass


# ─── TELEGRAM API ─────────────────────────────────────────────────────────────
def api_get(token, method, **params):
    url = "https://api.telegram.org/bot" + token + "/" + method
    try:
        return requests.get(url, params=params, timeout=35).json()
    except Exception as e:
        return {"ok": False, "description": str(e)}

def api_post(token, method, **data):
    url = "https://api.telegram.org/bot" + token + "/" + method
    try:
        return requests.post(url, data=data, timeout=35).json()
    except Exception as e:
        return {"ok": False, "description": str(e)}


def detect_chat_id(token):
    try:
        r = api_get(token, "getUpdates", timeout=0)
        if r.get("ok") and r.get("result"):
            for u in reversed(r["result"]):
                if "message" in u:
                    m = u["message"]
                    return m["chat"]["id"], m["chat"].get("first_name", "User")
    except Exception:
        pass
    return None, None


def send_file(token, chat_id, path, name):
    url = "https://api.telegram.org/bot" + token + "/sendDocument"
    try:
        with open(path, "rb") as f:
            resp = requests.post(
                url,
                data={"chat_id": chat_id},
                files={"document": (name, f)},
                timeout=120,
            )
        r = resp.json()
        if r.get("ok"):
            return True, None, r["result"]["message_id"]
        return False, r.get("description", "unknown error"), None
    except Exception as e:
        return False, str(e), None


def relay_message(token, from_chat, message_id, to_chat, mode, thread_id=None):
    method = "forwardMessage" if mode == "forward" else "copyMessage"
    data = {
        "chat_id": to_chat,
        "from_chat_id": from_chat,
        "message_id": message_id,
    }
    if thread_id:
        data["message_thread_id"] = thread_id
    r = api_post(token, method, **data)
    if r.get("ok"):
        return True, None
    return False, r.get("description", "unknown error")


def upload_and_forward(token, upload_chat, forward_target, path, name,
                       mode, thread_id=None):
    ok, err, mid = send_file(token, upload_chat, path, name)
    if not ok:
        return False, err, None
    if not forward_target:
        return True, None, mid
    ok2, err2 = relay_message(token, upload_chat, mid, forward_target, mode, thread_id)
    if not ok2:
        return False, "relay: " + str(err2), mid
    return True, None, mid


# ─── TARGET RESOLUTION ────────────────────────────────────────────────────────
def resolve_chat(token, target):
    if isinstance(target, int):
        return target, None
    s = str(target).strip()
    if not s:
        return None, None

    s = re.sub(r'^https?://', '', s, flags=re.I)
    s = re.sub(r'^www\.', '', s, flags=re.I)
    s = re.sub(r'^telegram\.me/', 't.me/', s, flags=re.I)
    s = s.split('?')[0].split('#')[0].rstrip('/')
    s = re.sub(r'^t\.me/', '', s, flags=re.I)
    s = s.lstrip('/')
    if not s:
        return None, None

    m = re.match(r'^c/(\d+)(?:/(\d+))?(?:/\d+)?$', s)
    if m:
        cid = int("-100" + m.group(1))
        tid = int(m.group(2)) if m.group(2) else None
        return cid, tid

    if s.startswith('+') or s.lower().startswith('joinchat/'):
        return None, None

    m = re.match(r'^@?([A-Za-z0-9_]{4,})(?:/(\d+))?$', s)
    if m:
        name = "@" + m.group(1)
        topic = int(m.group(2)) if m.group(2) else None
        r = api_get(token, "getChat", chat_id=name)
        if not r.get("ok"):
            return None, None
        cid = r["result"]["id"]
        if topic and not r["result"].get("is_forum"):
            topic = None
        return cid, topic

    m = re.match(r'^(-?\d+)(?:/(\d+))?$', s)
    if m:
        raw = int(m.group(1))
        topic = int(m.group(2)) if m.group(2) else None
        candidates = [raw]
        if raw > 0:
            candidates.append(int("-100" + str(raw)))
        for c in candidates:
            r = api_get(token, "getChat", chat_id=c)
            if r.get("ok"):
                return c, topic
        return None, None

    return None, None


def friendly_error(err):
    if not err:
        return err
    e = str(err)
    if "TOPIC_CLOSED" in e:
        return e + "  → topic closed. Reopen it in the app."
    if "not enough rights" in e or "CHAT_ADMIN_REQUIRED" in e:
        return e + "  → make the bot admin in the target (Post Messages on)."
    if "chat not found" in e:
        return e + "  → check the link / add the bot to the target."
    if "message thread not found" in e:
        return e + "  → topic id wrong. Copy the topic link from the app."
    return e


# ─── FILE LISTING ─────────────────────────────────────────────────────────────
def active_exts(cfg):
    custom = cfg.get("file_custom")
    if custom is None:
        return DEFAULT_EXT
    return tuple(custom) if custom else (".__none__",)


def list_files(cfg):
    exts = active_exts(cfg)
    here = os.path.dirname(os.path.abspath(__file__))
    cwd = os.getcwd()
    for d in (cwd, here):
        if not d or not os.path.isdir(d):
            continue
        files = sorted(
            f for f in os.listdir(d)
            if f.endswith(exts)
            and os.path.isfile(os.path.join(d, f))
            and os.path.abspath(os.path.join(d, f)) != os.path.abspath(__file__)
        )
        if files:
            return d, files
    return cwd, []


def human_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return str(n) + " B" if unit == "B" else ("%.1f %s" % (n, unit))
        n /= 1024.0
    return "%.1f TB" % n


def print_file_list(files, folder):
    for i, f in enumerate(files, 1):
        full = os.path.join(folder, f)
        size = human_size(os.path.getsize(full))
        ext = f.rsplit(".", 1)[-1].lower()
        if ext == "py":
            ext_color, icon = C.BLUE + C.BOLD, "◆"
        elif ext in ("txt", "md"):
            ext_color, icon = C.YELLOW, "▪"
        elif ext in ("zip", "tar", "gz", "7z"):
            ext_color, icon = C.ORANGE, "▣"
        elif ext in ("json", "csv", "xml", "yaml", "yml", "sql"):
            ext_color, icon = C.PURPLE, "◈"
        else:
            ext_color, icon = C.TEXT, "·"
        print("  " + C.DIMTX + str(i).rjust(3) + C.R +
              "  " + ext_color + icon + C.R +
              "  " + ext_color + f.ljust(28) + C.R +
              "  " + C.DIMTX + size.rjust(9) + C.R)


def parse_selection(raw, max_n):
    raw = raw.strip().lower()
    if raw in ("all", "*", "a"):
        return list(range(1, max_n + 1))
    raw = raw.replace(",", " ").replace(":", "-")
    picked = set()
    for tok in raw.split():
        if "-" in tok:
            parts = tok.split("-")
            if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
                return None
            a, b = int(parts[0]), int(parts[1])
            if a > b: a, b = b, a
            if a < 1 or b > max_n: return None
            for n in range(a, b + 1): picked.add(n)
        else:
            if not tok.isdigit(): return None
            n = int(tok)
            if n < 1 or n > max_n: return None
            picked.add(n)
    return sorted(picked) if picked else None


def ask_numbers(files, prompt_text):
    try:
        raw = input("  " + C.PURPLE + "▸" + C.R + " " + C.TEXT + prompt_text + C.R + " ").strip()
    except (EOFError, KeyboardInterrupt):
        print(); return None
    if not raw: return None
    nums = parse_selection(raw, len(files))
    if nums is None:
        print("\n  " + C.RED + "✗ invalid selection" + C.R); return None
    return [files[n - 1] for n in nums]


# ─── BANNER + HEADER ──────────────────────────────────────────────────────────
def banner():
    if sys.stdout.isatty(): os.system('clear')
    art = [
        "████████╗ ██████╗ ██╗   ██╗ ██████╗",
        "╚══██╔══╝██╔════╝ ██║   ██║ ██╔══██╗",
        "   ██║   ██║  ███╗██║   ██║ ██████╔╝",
        "   ██║   ██║   ██║██║   ██║ ██╔═══╝ ",
        "   ██║   ╚██████╔╝╚██████╔╝ ██║     ",
        "   ╚═╝    ╚═════╝  ╚═════╝  ╚═╝     ",
    ]
    subtitle = "termux · telegram uploader"

    art_w = max(vlen(a) for a in art)
    art = [a + " " * (art_w - vlen(a)) for a in art]
    inner = art_w + 8

    grey = C.DIMTX
    top = grey + "╭" + "─" * inner + "╮" + C.R
    bot = grey + "╰" + "─" * inner + "╯" + C.R

    def row(text="", color=""):
        vis = vlen(text)
        pad_l = (inner - vis) // 2
        pad_r = inner - vis - pad_l
        body = color + text + (C.R if color else "")
        return grey + "│" + C.R + " " * pad_l + body + " " * pad_r + grey + "│" + C.R

    print()
    print(top)
    print(row())
    for a in art:
        print(row(a, C.TITLE))
    print(row())
    print(row(subtitle, C.DIMTX))
    print(row())
    print(bot)
    print()


def header(cfg):
    user = cfg.get("username", "bot")
    grey = C.DIMTX
    inner = 44

    tgt = cfg.get("forward_target_id")
    if tgt:
        th = cfg.get("forward_thread_id")
        topic = ("  " + grey + "·" + C.R + "  " +
                 C.TEXT + "topic " + str(th) + C.R) if th else ""
        status = "  " + grey + "·" + C.R + "  " + C.GREEN + C.BOLD + "on" + C.R
        rows = [
            ("bot",     C.ACCENT + C.BOLD + "@" + str(user) + C.R),
            ("mode",    C.TEXT + cfg.get("forward_mode", "copy") + C.R),
            ("forward", C.WHITE + str(tgt) + C.R + topic + status),
        ]
    else:
        status = "  " + grey + "·" + C.R + "  " + C.RED + C.BOLD + "off" + C.R
        rows = [
            ("bot",     C.ACCENT + C.BOLD + "@" + str(user) + C.R),
            ("forward", grey + "none" + C.R + status),
        ]

    label_w = max(len(l) for l, _ in rows)

    top = grey + "╭" + "─" * inner + "╮" + C.R
    bot = grey + "╰" + "─" * inner + "╯" + C.R

    print(top)
    for lbl, val in rows:
        body = ("  " + lbl + " " * (label_w - len(lbl)) + "  " + val)
        pad_r = max(0, inner - vlen(body))
        print(grey + "│" + C.R + body + " " * pad_r + grey + "│" + C.R)
    print(bot)
    print()


# ─── MAIN MENU ────────────────────────────────────────────────────────────────
def main_menu():
    while True:
        cfg = load_config()
        if not cfg.get("token") or not cfg.get("chat_id"):
            setup(cfg); continue

        banner(); header(cfg)

        print("  " + C.GREEN  + C.BOLD + "[1]" + C.R + "  " + C.TEXT + "Send files" + C.R)
        print("  " + C.ORANGE + C.BOLD + "[2]" + C.R + "  " + C.TEXT + "Delete files" + C.R)
        print("  " + C.YELLOW + C.BOLD + "[3]" + C.R + "  " + C.TEXT + "Settings" + C.R)
        print("  " + C.PURPLE + C.BOLD + "[4]" + C.R + "  " + C.TEXT + "About" + C.R)
        print("  " + C.RED    + C.BOLD + "[0]" + C.R + "  " + C.TEXT + "Exit" + C.R)
        print()

        try:
            choice = input("  " + C.PURPLE + "▸" + C.R + " " + C.TEXT +
                           "choice " + C.DIMTX + "(0-4)" + C.R + " ").strip()
        except (EOFError, KeyboardInterrupt):
            print(); return

        if choice == "0":
            if sys.stdout.isatty(): os.system('clear')
            print("\n  " + C.GREEN + "✦  bye" + C.R + "\n"); return
        elif choice == "1": send_menu(cfg)
        elif choice == "2": delete_menu(cfg)
        elif choice == "3": settings_menu(cfg)
        elif choice == "4": about_menu()


# ─── SETTINGS ─────────────────────────────────────────────────────────────────
def settings_menu(cfg):
    while True:
        cfg = load_config()
        if sys.stdout.isatty(): os.system('clear')
        banner()

        print("  " + C.YELLOW + C.BOLD + "▸  Settings" + C.R)
        print(line()); print()

        print("  " + C.ACCENT + C.BOLD + "[1]" + C.R + "  " + C.TEXT + "Bot config" + C.R +
              "  " + C.DIMTX + "(token · username · chat id)" + C.R)
        print("  " + C.PURPLE + C.BOLD + "[2]" + C.R + "  " + C.TEXT + "Forward config" + C.R +
              "  " + C.DIMTX + "(target · mode)" + C.R)
        print("  " + C.ORANGE + C.BOLD + "[3]" + C.R + "  " + C.TEXT + "File types" + C.R +
              "  " + C.DIMTX + "(pick extensions)" + C.R)
        print("  " + C.RED    + C.BOLD + "[0]" + C.R + "  " + C.TEXT + "Back" + C.R)
        print()

        try:
            c = input("  " + C.PURPLE + "▸" + C.R + " " + C.TEXT +
                      "choice " + C.DIMTX + "(0-3)" + C.R + " ").strip()
        except (EOFError, KeyboardInterrupt):
            print(); return

        if c == "0": return
        elif c == "1": setup(cfg, reconfigure=True)
        elif c == "2": relay_setup(cfg)
        elif c == "3": custom_editor(cfg)


def setup(cfg, reconfigure=False):
    if sys.stdout.isatty(): os.system('clear')
    banner()

    print("  " + C.PINK + C.BOLD + "▸  Bot config" + C.R)
    print(line()); print()
    print("  " + C.DIMTX + "1. Get a token from " + C.R + C.ACCENT + "@BotFather" + C.R)
    print("  " + C.DIMTX + "2. DM your bot anything, then continue" + C.R)
    print("  " + C.DIMTX + "3. Get your chat id from " + C.R + C.ACCENT + "@userinfobot" + C.R)
    print()

    cur_token = cfg.get("token", "")
    cur_user  = cfg.get("username", "")

    try:
        prompt = "token" + (" (ENTER = keep)" if cur_token else "")
        new_token = input("  " + C.PURPLE + "▸" + C.R + " " + C.TEXT + prompt + C.R + " ").strip()
        if new_token:
            cfg["token"] = new_token
        elif not cur_token:
            print("\n  " + C.RED + "✗ token required" + C.R); pause(); return

        prompt = "username (without @)" + (" (ENTER = keep)" if cur_user else "")
        new_user = input("  " + C.PURPLE + "▸" + C.R + " " + C.TEXT + prompt + C.R + " ").strip()
        if new_user:
            cfg["username"] = new_user.lstrip("@")

        print()
        print("  " + C.DIMTX + "send any message to your bot, then press ENTER..." + C.R)
        input()

        cid, name = detect_chat_id(cfg["token"])
        if cid:
            cfg["chat_id"] = cid
            if name and not cfg.get("username"):
                cfg["username"] = name
            print("  " + C.GREEN + "✓" + C.R + "  " + C.TEXT + "chat id " + C.R +
                  C.WHITE + str(cid) + C.R)
        else:
            print("  " + C.DIMTX + "auto-detect failed, enter manually:" + C.R)
            while True:
                v = input("  " + C.PURPLE + "▸" + C.R + " " + C.TEXT + "chat id" + C.R + " ").strip()
                if v.lstrip("-").isdigit():
                    cfg["chat_id"] = int(v); break
                print("  " + C.RED + "✗ numbers only" + C.R)

        save_config(cfg)
        print("\n  " + C.GREEN + "✓" + C.R + "  " + C.TEXT + "saved" + C.R +
              "  " + C.DIMTX + CONFIG_FILE + C.R + "\n")
        pause()
    except (EOFError, KeyboardInterrupt):
        print()


def relay_setup(cfg):
    if sys.stdout.isatty(): os.system('clear')
    banner()

    print("  " + C.PINK + C.BOLD + "▸  Forward config" + C.R)
    print(line()); print()
    print("  " + C.YELLOW + "!" + C.R + "  " + C.DIMTX +
          "bot must be admin in the target (Post Messages on)" + C.R)
    print("  " + C.DIMTX + "  paste:  t.me/c/<id>          → General" + C.R)
    print("  " + C.DIMTX + "          t.me/<name>  ·  @name  ·  -100…" + C.R)
    print()

    cur = cfg.get("forward_target", "")
    th_cur = cfg.get("forward_thread_id")
    if cur:
        shown = str(cur) + ("/" + str(th_cur) if th_cur else "")
        prompt = "target [" + shown + "]  (ENTER = keep · \"-\" = clear)"
    else:
        prompt = "target"

    try:
        raw = input("  " + C.PURPLE + "▸" + C.R + " " + C.TEXT + prompt + C.R + " ").strip()
    except (EOFError, KeyboardInterrupt):
        print(); return

    if raw == "-":
        cfg.pop("forward_target", None)
        cfg.pop("forward_target_id", None)
        cfg.pop("forward_thread_id", None)
        save_config(cfg)
        print("\n  " + C.DIMTX + "forward target cleared." + C.R + "\n")
        pause(); return

    if raw:
        cfg["forward_target"] = raw
    if not cfg.get("forward_target"):
        return

    cid, tid = resolve_chat(cfg["token"], cfg["forward_target"])
    if cid is None:
        print("\n  " + C.RED + "✗ could not resolve target" + C.R)
        print("  " + C.DIMTX + "check the link / bot must be a member." + C.R + "\n")
        pause(); return

    cfg["forward_target_id"] = cid
    if tid:
        cfg["forward_thread_id"] = tid
    else:
        cfg.pop("forward_thread_id", None)

    cur_mode = cfg.get("forward_mode", "copy")
    print()
    print("  " + C.DIMTX + "mode:  " + C.R +
          C.ACCENT + "[f]" + C.R + " forward " + C.DIMTX + "·" + C.R +
          "  " + C.ACCENT + "[c]" + C.R + " copy " +
          C.DIMTX + "(current " + cur_mode + ")" + C.R)
    print("  " + C.DIMTX + "  f = shows \"Forwarded from\"" + C.R)
    print("  " + C.DIMTX + "  c = posted as bot, no attribution" + C.R)
    try:
        m = input("  " + C.PURPLE + "▸" + C.R + " " + C.TEXT +
                  "mode (ENTER = keep)" + C.R + " ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print(); return
    if m == "c": cfg["forward_mode"] = "copy"
    elif m == "f": cfg["forward_mode"] = "forward"

    save_config(cfg)

    print()
    print("  " + C.GREEN + "✓" + C.R + "  " + C.TEXT + "forward → " + C.R +
          C.WHITE + str(cid) + C.R +
          ("  " + C.DIMTX + "topic " + str(tid) + C.R if tid else ""))
    print("  " + C.DIMTX + "  mode=" + cfg.get("forward_mode", "copy") + C.R)

    probe = api_post(cfg["token"], "sendMessage",
                     chat_id=cid,
                     text="🔗 tgup forward armed",
                     **({"message_thread_id": tid} if tid else {}))
    if probe.get("ok"):
        print("  " + C.GREEN + "✓" + C.R + "  " + C.TEXT + "probe delivered" + C.R)
    else:
        print("  " + C.RED + "✗" + C.R + "  " + C.TEXT +
              friendly_error(probe.get("description", "probe failed")) + C.R)
    print()
    pause()


def custom_editor(cfg):
    catalog = list(EXT_CATALOG)
    if "file_custom" not in cfg or cfg["file_custom"] is None:
        cfg["file_custom"] = list(DEFAULT_EXT)

    selected = set(cfg["file_custom"])

    while True:
        if sys.stdout.isatty(): os.system('clear')
        banner()

        print("  " + C.ORANGE + C.BOLD + "▸  File types" + C.R)
        print(line()); print()
        print("  " + C.DIMTX + "pick which extensions appear in the file list." + C.R)
        print("  " + C.DIMTX + "changes save automatically." + C.R)
        print()

        for i, ext in enumerate(catalog, 1):
            on = ext in selected
            bullet = (C.GREEN + "●" + C.R) if on else (C.DIMTX + "○" + C.R)
            name = (C.TEXT if on else C.DIMTX) + ext.ljust(8) + C.R
            print("  " + C.DIMTX + str(i).rjust(3) + C.R +
                  "  " + bullet + "  " + name)

        print()
        print("     " + C.ACCENT + "1 3 5" + C.R + "   " + C.DIMTX + "space separated" + C.R)
        print("     " + C.ACCENT + "1-5" + C.R + "     " + C.DIMTX + "range" + C.R)
        print("     " + C.ACCENT + "all" + C.R + "     " + C.DIMTX + "turn all on" + C.R)
        print("     " + C.ACCENT + "none" + C.R + "    " + C.DIMTX + "turn all off" + C.R)
        print("     " + C.ACCENT + "ENTER" + C.R + "   " + C.DIMTX + "save & go back" + C.R)
        print()
        print("  " + C.DIMTX + "selected  " + C.R +
              C.GREEN + C.BOLD + str(len(selected)) + C.R +
              "  " + C.DIMTX + "/ " + str(len(catalog)) + C.R)
        print()

        try:
            raw = input("  " + C.PURPLE + "▸" + C.R + " " + C.TEXT +
                        "toggle " + C.DIMTX + "(ENTER = back)" + C.R + " ").strip()
        except (EOFError, KeyboardInterrupt):
            print(); return

        if not raw or raw.lower() == "done":
            cfg["file_custom"] = [e for e in catalog if e in selected]
            save_config(cfg)
            return

        low = raw.lower()
        if low == "all":
            selected = set(catalog)
            continue
        if low == "none":
            selected = set()
            continue

        nums = parse_selection(raw, len(catalog))
        if nums is None:
            print("\n  " + C.RED + "✗ invalid selection" + C.R)
            time.sleep(0.8)
            continue

        for n in nums:
            ext = catalog[n - 1]
            if ext in selected:
                selected.discard(ext)
            else:
                selected.add(ext)


# ─── SEND / DELETE ────────────────────────────────────────────────────────────
def send_menu(cfg):
    if sys.stdout.isatty(): os.system('clear')
    banner()

    folder, files = list_files(cfg)
    if not files:
        print("  " + C.RED + "✗ no files found" + C.R)
        print("  " + C.DIMTX + "check Settings → File types  ·  or put files next to the script." + C.R + "\n")
        pause(); return

    target_id = cfg.get("forward_target_id")
    thread_id = cfg.get("forward_thread_id")
    mode = cfg.get("forward_mode", "copy")

    print("  " + C.PINK + C.BOLD + "▸  Available files" + C.R)
    print("  " + C.DIMTX + folder + C.R)
    print(line()); print()
    print_file_list(files, folder)
    print()
    print(line()); print()

    if target_id:
        th = ("  " + C.DIMTX + "topic " + str(thread_id) + C.R) if thread_id else ""
        print("  " + C.GREEN + "●" + C.R + "  " + C.DIMTX + "will forward to " + C.R +
              C.WHITE + str(target_id) + C.R + th +
              "  " + C.DIMTX + "(" + mode + " mode)" + C.R)
    else:
        print("  " + C.DIMTX + "●  no forward target — files land in bot chat only" + C.R)
        print("  " + C.DIMTX + "   set one in Settings → Forward config" + C.R)
    print()
    print("  " + C.DIMTX + "examples: " + C.R +
          C.ACCENT + "1 2 3" + C.R + "  " + C.DIMTX + "·" + C.R + "  " +
          C.ACCENT + "1-5" + C.R + "  " + C.DIMTX + "·" + C.R + "  " +
          C.ACCENT + "all" + C.R)
    print()

    chosen = ask_numbers(files, "numbers  (space-separated · 1-5 · all)")
    if not chosen: return

    print()
    print(line()); print()

    for name in chosen:
        path = os.path.join(folder, name)
        print("  " + C.PINK + "▸" + C.R + "  " + C.TEXT + name + C.R + "  " +
              C.DIMTX + "..." + C.R + " ", end="", flush=True)
        ok, err, _ = upload_and_forward(
            cfg["token"], cfg["chat_id"], target_id,
            path, name, mode, thread_id
        )
        if ok:
            print(C.GREEN + C.BOLD +
                  ("✓ sent + forwarded" if target_id else "✓ sent") + C.R)
        else:
            print(C.RED + C.BOLD + "✗ failed" + C.R)
            print("       " + C.DIMTX + friendly_error(err) + C.R)
        time.sleep(0.4)

    print()
    pause()


def delete_menu(cfg):
    if sys.stdout.isatty(): os.system('clear')
    banner()

    folder, files = list_files(cfg)
    if not files:
        print("  " + C.RED + "✗ no files found" + C.R)
        print("  " + C.DIMTX + "nothing to delete." + C.R + "\n")
        pause(); return

    print("  " + C.ORANGE + C.BOLD + "▸  Delete files" + C.R)
    print("  " + C.DIMTX + folder + C.R)
    print(line()); print()
    print_file_list(files, folder)
    print()
    print(line()); print()
    print("  " + C.DIMTX + "examples: " + C.R +
          C.ACCENT + "1 2 3" + C.R + "  " + C.DIMTX + "·" + C.R + "  " +
          C.ACCENT + "1-5" + C.R + "  " + C.DIMTX + "·" + C.R + "  " +
          C.ACCENT + "all" + C.R)
    print()

    chosen = ask_numbers(files, "numbers to delete  (space-separated · 1-5 · all)")
    if not chosen: return

    print()
    print(line()); print()
    print("  " + C.RED + C.BOLD + "will delete:" + C.R)
    for name in chosen:
        print("    " + C.RED + "✗" + C.R + "  " + C.TEXT + name + C.R)
    print()

    try:
        confirm = input("  " + C.RED + C.BOLD + "confirm? " + C.R +
                        C.DIMTX + "(y/N)" + C.R + " ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print(); return
    if confirm != "y":
        print("\n  " + C.DIMTX + "cancelled." + C.R + "\n"); return

    for name in chosen:
        path = os.path.join(folder, name)
        try:
            os.remove(path)
            print("  " + C.GREEN + "✓" + C.R + "  " + C.TEXT + name + C.R +
                  "  " + C.DIMTX + "deleted" + C.R)
        except OSError as e:
            print("  " + C.RED + "✗" + C.R + "  " + C.TEXT + name + C.R +
                  "  " + C.DIMTX + str(e) + C.R)
    print()
    pause()


# ─── ABOUT ────────────────────────────────────────────────────────────────────
def about_menu():
    if sys.stdout.isatty(): os.system('clear')
    banner()

    print("  " + C.BLUE + C.BOLD + "▸  About tgup" + C.R)
    print(line())
    print()
    print("  " + C.TEXT + "tgup" + C.R + C.DIMTX +
          " uploads files from Termux to Telegram." + C.R)
    print("  " + C.DIMTX + "Pick files, send them to your bot, done." + C.R)
    print()
    print("  " + C.DIMTX + "Optional: relay them onward to a channel, group," + C.R)
    print("  " + C.DIMTX + "or forum topic — see Forward mode below." + C.R)
    print()
    print("  " + C.PURPLE + C.BOLD + "❯❯  fast run shortcut  " + C.R +
          C.ACCENT + C.BOLD + "tg" + C.R)
    print()

    print("  " + C.ACCENT + C.BOLD + "Setup" + C.R)
    print("  " + C.DIMTX + "  1. create a bot via " + C.R + C.ACCENT + "@BotFather" + C.R +
          C.DIMTX + ", copy the token" + C.R)
    print("  " + C.DIMTX + "  2. open a chat with your bot and send it any message" + C.R)
    print("  " + C.YELLOW + C.BOLD + "     ⚠ required — the bot cannot receive until you do this" + C.R)
    print("  " + C.DIMTX + "  3. get your chat id from " + C.R + C.ACCENT + "@userinfobot" + C.R)
    print("  " + C.DIMTX + "  4. run " + C.R + C.TEXT + "tg" + C.R + C.DIMTX +
          "  →  [3] Settings  →  [1] Bot config" + C.R)
    print("  " + C.DIMTX + "     paste the token and chat id" + C.R)
    print()

    print("  " + C.ACCENT + C.BOLD + "File types" + C.R)
    print("  " + C.DIMTX + "  where  " + C.R +
          C.ORANGE + C.BOLD + "Settings → [3] File types" + C.R)
    print()
    print("  " + C.DIMTX + "  Termux folders get crowded — logs, caches, temp" + C.R)
    print("  " + C.DIMTX + "  files pile up fast. Without a filter the picker" + C.R)
    print("  " + C.DIMTX + "  would list hundreds of files you never send." + C.R)
    print()
    print("  " + C.DIMTX + "  So you choose which extensions show up." + C.R)
    print("  " + C.DIMTX + "  24 are available; 9 are on by default." + C.R)
    print("  " + C.DIMTX + "  Toggle them on or off — saved instantly." + C.R)
    print()
    print("  " + C.YELLOW + C.BOLD + "  tip  " + C.R +
          C.DIMTX + "only files matching your selection appear in" + C.R)
    print("  " + C.DIMTX + "       both " + C.R +
          C.ACCENT + C.BOLD + "Send files" + C.R +
          C.DIMTX + " and " + C.R +
          C.ORANGE + C.BOLD + "Delete files" + C.R)
    print()

    print("  " + C.ACCENT + C.BOLD + "Forward mode" + C.R)
    print("  " + C.DIMTX + "  Advanced. Files uploaded to the bot are relayed" + C.R)
    print("  " + C.DIMTX + "  to a channel / group / topic of your choice." + C.R)
    print()
    print("  " + C.DIMTX + "  set it up:  [3] Settings → [2] Forward config" + C.R)
    print("  " + C.DIMTX + "  the bot must be admin in the target with Post Messages." + C.R)
    print()
    print("  " + C.ACCENT + C.BOLD + "  Modes" + C.R)
    print("  " + C.YELLOW + "  copy mode    " + C.R + C.DIMTX +
          "→ posted by the bot, no source header" + C.R)
    print("  " + C.YELLOW + "  forward mode " + C.R + C.DIMTX +
          "→ shows \"Forwarded from\" above the file" + C.R)
    print()
    print("  " + C.ACCENT + C.BOLD + "  Accepted targets" + C.R)
    print("  " + C.DIMTX + "  t.me/c/<id>              → General topic" + C.R)
    print("  " + C.DIMTX + "  t.me/<name>  ·  @name    → channel / group" + C.R)
    print("  " + C.DIMTX + "  -100…                    → raw chat id" + C.R)
    print()

    print("  " + C.ACCENT + C.BOLD + "Files" + C.R)
    print("  " + C.DIMTX + "  ~/tgup.py            the script" + C.R)
    print("  " + C.DIMTX + "  ~/.tgup.json         config (chmod 600)" + C.R)
    print()

    print(line())
    print()
    print("  " + C.DIMTX + "© 2026  " + C.R +
          C.TEXT + C.BOLD + "IXREE" + C.R +
          C.DIMTX + "  ·  all rights reserved" + C.R)
    print("  " + C.DIMTX + "tgup v" + __version__ + "  ·  built for Termux" + C.R)
    print()
    print("  " + C.DIMTX + "published on " + C.R +
          C.ACCENT + C.BOLD + "t.me/ixree_scripts" + C.R)
    print("  " + C.DIMTX + "tools channel  ·  " + C.R +
          C.ACCENT + "@ixree_scripts" + C.R)
    print()

    pause()


# ─── ENTRY ────────────────────────────────────────────────────────────────────
def main():
    if not sys.stdout.isatty():
        C.off()
    try:
        main_menu()
    except KeyboardInterrupt:
        if sys.stdout.isatty(): os.system('clear')
        print("\n  " + C.GREEN + "✦  bye" + C.R + "\n"); sys.exit(130)


if __name__ == "__main__":
    main()
