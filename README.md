<div align="center">

# tgup

**Ship files from Termux to Telegram in seconds.**

Upload files to your bot and auto-forward them to any channel, group, or forum topic.

[![Version](https://img.shields.io/badge/version-1.0.0-81d4fa?style=flat-square)](https://github.com/ixree/tgup/releases)
[![License](https://img.shields.io/badge/license-MIT-81d4fa?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8%2B-81d4fa?style=flat-square)](https://www.python.org)

[Install](#install) · [Setup](#setup) · [Features](#features) · [Channel](https://t.me/ixree_scripts)

</div>

---

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/ixree/tgup/main/install.sh | bash
```

Then run:

```bash
tg
```

The installer handles everything: Python check, `requests`, the script, and the `tg` shortcut.

---

## Setup

Five steps, one time.

**1.** Create a bot via [@BotFather](https://t.me/BotFather) and copy the token.

**2.** Open a chat with your bot and send it any message.
> ⚠️ Required — the bot cannot receive until you do this.

**3.** Get your chat id from [@userinfobot](https://t.me/userinfobot).

**4.** Run `tg` → **Settings** → **Bot config** and paste the token and chat id.

**5.** *(Optional)* Set a forward target: **Settings** → **Forward config**.

Done. Send files with option `[1]`.

---

## Features

| | |
|---|---|
| **Upload** | Pick files, send to your bot in one action |
| **Forward** | Auto-relay to any channel, group, or forum topic |
| **Modes** | `copy` (no source header) or `forward` (shows "Forwarded from") |
| **Smart links** | `@name` · `t.me/name` · `t.me/c/<id>` · `t.me/c/<id>/<topic>` · `-100…` |
| **Multi-select** | `1 2 3` · `1-5` · `all` · mixed |
| **File types** | 24 extensions · 9 on by default · toggle in Settings |
| **UI** | Colored TUI · aligned boxes · friendly error hints |
| **Config** | `~/.tgup.json` · chmod 600 · auto-saved |

---

## Menu

```
[1]  Send files
[2]  Delete files
[3]  Settings
     [1]  Bot config      (token · username · chat id)
     [2]  Forward config  (target · mode)
     [3]  File types      (pick extensions)
[4]  About
[0]  Exit
```

---

## How it works

```
Termux  →  bot DM  →  forward target
         sendDoc    copy / forward
```

Two API calls per file:

1. `sendDocument` — uploads the file to your bot's chat
2. `copyMessage` or `forwardMessage` — relays it to the target

No extra storage, no re-upload — Telegram reuses the file reference.

---

## Target formats

| You paste | Resolves to |
|---|---|
| `@mychannel` | channel / group |
| `t.me/mychannel` | channel / group |
| `https://t.me/c/4206268912` | private channel (General) |
| `https://t.me/c/4206268912/19` | private channel + topic 19 |
| `-1004206268912` | raw chat id |
| `4206268912` | auto-converts to `-100…` |

---

## Requirements

- Termux (Android)
- Python 3.8+
- `requests` (installed automatically)
- A Telegram bot (from @BotFather)

**Bot must be admin** in the forward target with **Post Messages** enabled.

---

## Files

| Path | Purpose |
|---|---|
| `~/tgup.py` | the script |
| `~/.tgup.json` | config (chmod 600) |
| `$PREFIX/bin/tg` | shortcut |

---

## Uninstall

```bash
rm ~/tgup.py ~/.tgup.json $PREFIX/bin/tg
```

Optionally remove the bot from your Telegram chats.

---

## License

MIT · © 2026 [IXREE](https://t.me/ixree_scripts)

Published on [t.me/ixree_scripts](https://t.me/ixree_scripts)
