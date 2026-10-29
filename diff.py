"""Сравнение файлов (Diff)."""
import difflib
from pathlib import Path

def get_diff(current_file, snapshot_file, context_lines=3):
    try:
        with open(current_file, "r", encoding="utf-8", errors="replace") as f:
            current_lines = f.readlines()
        with open(snapshot_file, "r", encoding="utf-8", errors="replace") as f:
            snapshot_lines = f.readlines()
    except Exception as e:
        return f"Ошибка чтения файлов: {e}"

    diff = difflib.unified_diff(
        snapshot_lines,
        current_lines,
        fromfile="Snapshot (Old)",
        tofile="Current (New)",
        n=context_lines
    )
    result = "".join(diff)
    return result if result else "Файлы идентичны."