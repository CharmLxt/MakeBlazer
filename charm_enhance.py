"""Мягкая интеграция с CharmPkk: красиво, если есть; обычно, если нет."""
import sys

_charm = None
_c = None
_available = False

try:
    from charmpkk import console as _c
    _charm = __import__("charmpkk")
    _available = True
except Exception:
    _available = False

def has_charm(): return _available
def console(): return _c
def theme(name="tokyo_night"): return _c.get_theme(name) if _available else None

def _fg(color):
    if not _available or not color: return None
    if isinstance(color, str) and color.startswith("#"): return _c.fg_hex(color)
    return color

def banner(title, subtitle=None, color="#7aa2ff", gradient=None):
    if _available: 
        try:
            # Пытаемся передать градиент (если версия CharmPkk новая)
            return _c.banner(title, subtitle, fg=_fg(color), gradient=gradient)
        except TypeError:
            # Если старая — рисуем без градиента
            return _c.banner(title, subtitle, fg=_fg(color))
    return f"\n=== {title} ===\n{subtitle}\n" if subtitle else f"\n=== {title} ===\n"

def box(content, title=None, color="#7aa2ff"):
    if _available: return _c.box(content, title=title, border_fg=_fg(color))
    lines = content if isinstance(content, list) else [content]
    return "\n".join([f"--- {title} ---" if title else "-"*20] + [str(l) for l in lines] + ["-"*20])

def table(headers, rows, header_color="#7aa2ff"):
    if _available: return _c.Table(headers=headers, rows=rows, header_fg=_fg(header_color)).render()
    all_rows = [list(headers)] + [list(r) for r in rows]
    n_cols = len(headers)
    widths = [max(len(str(r[i])) if i < len(r) else 0 for r in all_rows) for i in range(n_cols)]
    lines = []
    for i, row in enumerate(all_rows):
        cells = [str(row[j]) if j < len(row) else "" for j in range(n_cols)]
        lines.append(" | ".join(c.ljust(widths[j]) for j, c in enumerate(cells)))
        if i == 0: lines.append("-+-".join("-" * w for w in widths))
    return "\n".join(lines)

def info(msg): print(_c.info(msg)) if _available else print(f"[i] {msg}")
def success(msg): print(_c.success(msg)) if _available else print(f"[+] {msg}")
def warning(msg): print(_c.warning(msg)) if _available else print(f"[!] {msg}")
def error(msg): print(_c.error(msg)) if _available else print(f"[x] {msg}")

def ask(prompt, default=None):
    if _available: return _c.ask(prompt, default=default)
    hint = f" [{default}]" if default is not None else ""
    try: return input(f"? {prompt}{hint}: ").strip() or default
    except (EOFError, KeyboardInterrupt): return default

def confirm(prompt, default=False):
    if _available: return _c.confirm(prompt, default=default)
    d = "Y/n" if default else "y/N"
    try: v = input(f"? {prompt} ({d}): ").strip().lower()
    except (EOFError, KeyboardInterrupt): return default
    return v.startswith("y") if v else default

def select(title, options, color="#7aa2ff"):
    if not options: return None
    if _available: return _c.select(title, options, fg_cursor=_fg(color), fg_title=_fg(color))
    print(title)
    for i, opt in enumerate(options, 1): print(f"  {i}. {opt}")
    try:
        idx = int(input("> ").strip()) - 1
        if 0 <= idx < len(options): return options[idx]
    except Exception: return None

class _NullProgress:
    def __enter__(self): return self
    def __exit__(self, *exc): print()
    def update(self, current): sys.stdout.write(f"\r  {current}%"); sys.stdout.flush()
    def finish(self, msg=None): print(msg) if msg else None

def progress(total=100, label="", color="#7aa2ff"):
    if _available: return _c.FancyProgressBar(total=total, label=label, fg=_fg(color))
    return _NullProgress()