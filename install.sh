#!/data/data/com.termux/files/usr/bin/bash
# ─────────────────────────────────────────────────────────────
#  tgup — installer
#  © 2026 IXREE · t.me/ixree_scripts
# ─────────────────────────────────────────────────────────────
set -e

REPO_URL="https://raw.githubusercontent.com/ixree/tgup/main/tgup.py"
DEST="$HOME/tgup.py"
BIN="$PREFIX/bin/tg"
SRC_LOCAL="./tgup.py"

cyan()  { printf '\033[38;5;81m%s\033[0m\n' "$1"; }
green() { printf '\033[38;5;120m%s\033[0m\n' "$1"; }
grey()  { printf '\033[38;5;244m%s\033[0m\n' "$1"; }
red()   { printf '\033[38;5;210m%s\033[0m\n' "$1"; }

echo
cyan "  ▸  tgup installer"
grey "  ────────────────────────────────────────────"
echo

# ── 1. python ───────────────────────────────────────────────
if ! command -v python3 >/dev/null 2>&1; then
  grey "  installing python..."
  pkg install python -y >/dev/null 2>&1
fi
green "  ✓  python3 $(python3 --version 2>&1 | awk '{print $2}')"

# ── 2. requests ─────────────────────────────────────────────
if ! python3 -c "import requests" >/dev/null 2>&1; then
  grey "  installing requests..."
  pip install requests --quiet >/dev/null 2>&1
fi
green "  ✓  requests"

# ── 3. tgup.py ──────────────────────────────────────────────
if [ -f "$SRC_LOCAL" ] && [ "$(readlink -f "$SRC_LOCAL")" != "$(readlink -f "$DEST" 2>/dev/null || echo)" ]; then
  cp "$SRC_LOCAL" "$DEST"
  green "  ✓  tgup.py (local copy)"
elif [ -f "$DEST" ]; then
  green "  ✓  tgup.py (already present)"
elif command -v curl >/dev/null 2>&1; then
  grey "  downloading tgup.py..."
  curl -fsSL "$REPO_URL" -o "$DEST"
  green "  ✓  tgup.py"
else
  red "  ✗  curl missing — run: pkg install curl"
  exit 1
fi
chmod +x "$DEST"

# ── 4. verify syntax ────────────────────────────────────────
if ! python3 -c "import ast;ast.parse(open('$DEST').read())" 2>/dev/null; then
  red "  ✗  tgup.py failed to load — aborting"
  rm -f "$DEST"
  exit 1
fi
green "  ✓  syntax verified"

# ── 5. tg shortcut ──────────────────────────────────────────
mkdir -p "$PREFIX/bin"
cat > "$BIN" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
exec python3 "\$HOME/tgup.py" "\$@"
EOF
chmod +x "$BIN"
green "  ✓  tg shortcut installed"

echo
grey "  ────────────────────────────────────────────"
green "  ✓  installed"
echo
cyan "     run:  tg"
echo
grey "  © 2026 IXREE · t.me/ixree_scripts"
echo
