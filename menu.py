"""Интерактивное меню makeblazer (TUI)."""
import time
from pathlib import Path
from . import charm_enhance as ui
from .core import Blazer
from .diff import get_diff

# ============================================================
# Вспомогательные функции для меню
# ============================================================

def _validate_target(path_str):
    if not path_str: return None, "Пустой путь."
    p = Path(path_str).expanduser().resolve()
    if not p.exists(): return None, f"Папка не существует: {p}"
    if not p.is_dir(): return None, f"Это не папка: {p}"
    return p, None

def _render_dashboard(blazer):
    stats = blazer.get_storage_stats()
    changed = blazer.get_changed_files()
    
    lines = [
        f"📁 Рабочая папка: {blazer.target}",
        f"📸 Снапшотов: {stats['snapshots']}",
        f"💾 Занято места: {stats['size_mb']} MB",
    ]
    
    if changed and "Файлов нет" not in changed[0]:
        lines.append(f"⚠️  Несохраненных изменений: {len(changed)} файлов")
    else:
        lines.append("✅ Все файлы сохранены")
        
    return ui.box(lines, title="Статус системы", color="#7aa2ff")

# ============================================================
# Меню: Снапшоты
# ============================================================

def _menu_snapshots(blazer):
    while True:
        choice = ui.select("Управление снапшотами", [
            "📸 Создать новый снапшот",
            "🗑️  Удалить снапшот",
            "← Назад"
        ])
        if not choice or choice.startswith("←"): return
        
        if choice.startswith("📸"):
            msg = ui.ask("Название снапшота", default="Manual snapshot")
            if msg:
                ui.info("Сканирование файлов...")
                count = blazer.snapshot(message=msg)
                ui.success(f"Готово! Сохранено файлов: {count}")
                ui.ask("Enter — назад")
        elif choice.startswith("🗑"):
            history = blazer.get_history()
            if not history: ui.warning("История пуста."); continue
            options = [f"[{i}] {s['timestamp']} — {s['message']}" for i, s in enumerate(history)]
            target = ui.select("Какой снапшот удалить?", options + ["← Назад"])
            if target and not target.startswith("←"):
                idx = int(target.split("]")[0][1:])
                if ui.confirm("Удалить этот снапшот?", default=False):
                    ok, msg = blazer.delete_snapshot(idx)
                    (ui.success if ok else ui.error)(msg)
                    ui.info("Для освобождения места запустите GC в меню Обслуживания.")
                    ui.ask("Enter — назад")

# ============================================================
# Меню: Машина времени (История, Восстановление, Diff)
# ============================================================

def _menu_time_machine(blazer):
    while True:
        choice = ui.select("Машина времени", [
            "🕒 История (Список снапшотов)",
            "⏪ Восстановить один файл",
            "💥 Полный откат папки (Rollback)",
            "📝 Показать различия (Diff)",
            "🕰️  История конкретного файла (Timeline)",
            "← Назад"
        ])
        if not choice or choice.startswith("←"): return

        if choice.startswith("🕒"):
            history = blazer.get_history()
            if not history: ui.warning("История пуста.")
            else:
                headers = ["#", "Дата", "Сообщение", "Файлов"]
                rows = [[str(i), h["timestamp"], h["message"], str(len(h["files"]))] for i, h in enumerate(history)]
                print(ui.table(headers, rows))
            ui.ask("Enter — назад")
            
        elif choice.startswith("⏪"):
            history = blazer.get_history()
            if not history: ui.warning("История пуста."); continue
            file_path = ui.ask("Путь к файлу", default="main.py")
            if not file_path: continue
            norm_path = Path(file_path).as_posix()
            valid = [(i, s) for i, s in enumerate(history) if any(f["path"] == norm_path for f in s["files"])]
            if not valid: ui.error("Файл не найден в истории."); continue
            options = [f"[{i}] {s['timestamp']}" for i, s in valid]
            target = ui.select("Из какой версии восстановить?", options + ["← Назад"])
            if target and not target.startswith("←"):
                idx = int(target.split("]")[0][1:])
                ok, msg = blazer.restore_file(file_path, idx)
                (ui.success if ok else ui.error)(msg)
                ui.ask("Enter — назад")

        elif choice.startswith("💥"):
            history = blazer.get_history()
            if not history: ui.warning("История пуста."); continue
            options = [f"[{i}] {s['timestamp']} — {s['message']}" for i, s in enumerate(history)]
            target = ui.select("К какой версии откатить ВСЮ папку?", options + ["← Назад"])
            if target and not target.startswith("←"):
                idx = int(target.split("]")[0][1:])
                if ui.confirm("⚠️ ВНИМАНИЕ: Новые файлы будут удалены. Продолжить?", default=False):
                    ok, msg = blazer.restore_snapshot(idx)
                    (ui.success if ok else ui.error)(msg)
                    ui.ask("Enter — назад")

        elif choice.startswith("📝"):
            history = blazer.get_history()
            if not history: ui.warning("История пуста."); continue
            file_path = ui.ask("Путь к файлу для сравнения", default="main.py")
            if not file_path: continue
            norm_path = Path(file_path).as_posix()
            valid = [(i, s) for i, s in enumerate(history) if any(f["path"] == norm_path for f in s["files"])]
            if not valid: ui.error("Файл не найден в истории."); continue
            options = [f"[{i}] {s['timestamp']}" for i, s in valid]
            target = ui.select("С чем сравниваем текущий файл?", options + ["← Назад"])
            if target and not target.startswith("←"):
                idx = int(target.split("]")[0][1:])
                snap = history[idx]
                file_hash = next((f["hash"] for f in snap["files"] if f["path"] == norm_path), None)
                diff_text = get_diff(blazer.target / file_path, blazer.objects_dir / file_hash)
                
                if ui.has_charm():
                    from charmpkk.console import colorize, fg_hex
                    colored = []
                    for line in diff_text.splitlines():
                        if line.startswith("+"): colored.append(colorize(line, fg=fg_hex("#22c55e")))
                        elif line.startswith("-"): colored.append(colorize(line, fg=fg_hex("#ef4444")))
                        elif line.startswith("@"): colored.append(colorize(line, fg=fg_hex("#7aa2ff")))
                        else: colored.append(line)
                    print("\n".join(colored))
                else:
                    print(diff_text)
                ui.ask("Enter — назад")

        elif choice.startswith("🕰"):
            file_path = ui.ask("Путь к файлу", default="main.py")
            if file_path:
                timeline = blazer.get_file_timeline(file_path)
                if not timeline: ui.warning("Файл не найден в истории.")
                else:
                    headers = ["Снапшот", "Дата", "Сообщение", "Хэш"]
                    rows = [[f"#{t['idx']}", t['timestamp'], t['message'], t['hash'][:8] + "..."] for t in timeline]
                    print(ui.table(headers, rows))
            ui.ask("Enter — назад")

# ============================================================
# Меню: Поиск и Авто-бэкап
# ============================================================

def _menu_live_tools(blazer):
    while True:
        choice = ui.select("Живые инструменты", [
            "🔎 Time-Search (Поиск по всей истории)",
            "🤖 Auto-Backup (Фоновый режим)",
            "← Назад"
        ])
        if not choice or choice.startswith("←"): return

        if choice.startswith("🔎"):
            query = ui.ask("Что ищем (текст внутри файлов)?")
            if query:
                ui.info("Сканирование всех снапшотов...")
                results = blazer.search_history(query)
                if not results: ui.warning("Ничего не найдено.")
                else:
                    ui.success(f"Найдено совпадений: {len(results)}")
                    headers = ["Снапшот", "Дата", "Файл", "Строка", "Текст"]
                    rows = [[f"#{r['snapshot_idx']}", r['timestamp'], r['file'], str(r['line']), r['text'][:40]] for r in results[:30]]
                    print(ui.table(headers, rows))
                    if len(results) > 30: ui.info(f"Показаны первые 30 из {len(results)}.")
            ui.ask("Enter — назад")

        elif choice.startswith("🤖"):
            print(ui.banner("Auto-Backup", "Фоновый режим (Ctrl+C для выхода)", color="#f59e0b"))
            ui.info(f"Слежу за изменениями в: {blazer.target}")
            last_snap = time.time()
            try:
                while True:
                    changed = blazer.get_changed_files()
                    if changed and "Файлов нет" not in changed[0]:
                        if time.time() - last_snap > 10:
                            ui.info(f"Обнаружены изменения ({len(changed)} файлов). Авто-бэкап...")
                            blazer.snapshot(message="Auto-backup")
                            last_snap = time.time()
                    time.sleep(5)
            except KeyboardInterrupt:
                ui.warning("Остановлено.")
                ui.ask("Enter — назад")

# ============================================================
# Меню: Настройки и Обслуживание
# ============================================================

def _menu_settings(blazer):
    while True:
        choice = ui.select("Настройки и Обслуживание", [
            "📁 Сменить рабочую папку",
            "🚫 Настроить .blazerignore",
            "📊 Статистика диска",
            "🗑️  Сборка мусора (GC)",
            "📦 Экспорт снапшота в ZIP",
            "← Назад"
        ])
        if not choice or choice.startswith("←"): return

        if choice.startswith("📁"):
            new_path = ui.ask("Новый путь (Enter — отмена)")
            if new_path:
                p, err = _validate_target(new_path)
                if err: ui.error(err)
                else:
                    new_blazer = Blazer(str(p))
                    ui.success(f"Переключено на {p}")
                    ui.ask("Enter — назад")
                    return new_blazer  # Возвращаем новый экземпляр

        elif choice.startswith("🚫"):
            print(ui.banner(".blazerignore", "Что игнорировать", color="#f59e0b"))
            blazer._load_ignore()
            if blazer.ignore_patterns:
                rows = [[str(i + 1), pat] for i, pat in enumerate(blazer.ignore_patterns)]
                print(ui.table(["#", "Шаблон"], rows))
            print(ui.box(f"Файл: {blazer.ignore_file}", title="Расположение", color="#f59e0b"))
            act = ui.select("Действие", ["➕ Добавить", "➖ Удалить", "🔄 Сброс", "← Назад"])
            if act and not act.startswith("←"):
                if act.startswith("➕"):
                    pat = ui.ask("Шаблон (пример: *.log)")
                    if pat:
                        with open(blazer.ignore_file, "a", encoding="utf-8") as f: f.write("\n" + pat)
                        ui.success("Добавлено.")
                elif act.startswith("➖"):
                    idx = ui.ask("Номер строки для удаления")
                    if idx and idx.isdigit() and 0 < int(idx) <= len(blazer.ignore_patterns):
                        del blazer.ignore_patterns[int(idx)-1]
                        blazer.ignore_file.write_text("\n".join(blazer.ignore_patterns) + "\n", encoding="utf-8")
                        ui.success("Удалено.")
                elif act.startswith("🔄"):
                    if ui.confirm("Сбросить к умолчаниям?", default=False):
                        blazer.ignore_file.write_text("__pycache__/\n*.pyc\n.blazer/\n.venv/\nnode_modules/\n", encoding="utf-8")
                        ui.success("Сброшено.")
                ui.ask("Enter — назад")

        elif choice.startswith("📊"):
            stats = blazer.get_storage_stats()
            print(ui.box([
                f"Всего снапшотов: {stats['snapshots']}",
                f"Уникальных объектов: {stats['objects']}",
                f"Занято места: {stats['size_mb']} MB"
            ], title="Статистика .blazer", color="#7aa2ff"))
            ui.ask("Enter — назад")

        elif choice.startswith("🗑"):
            ui.info("Очистка...")
            deleted = blazer.garbage_collect()
            ui.success(f"Удалено объектов: {deleted}")
            ui.ask("Enter — назад")

        elif choice.startswith("📦"):
            history = blazer.get_history()
            if history:
                options = [f"[{i}] {s['timestamp']}" for i, s in enumerate(history)]
                target = ui.select("Какой экспортировать?", options + ["← Назад"])
                if target and not target.startswith("←"):
                    idx = int(target.split("]")[0][1:])
                    zip_path = ui.ask("Имя файла", default=f"snapshot_{idx}.zip")
                    if zip_path:
                        ok, msg = blazer.export_snapshot(idx, zip_path)
                        (ui.success if ok else ui.error)(msg)
            else: ui.warning("История пуста.")
            ui.ask("Enter — назад")

# ============================================================
# Главный цикл
# ============================================================

def run(target_dir=None):
    initial_path = target_dir or "."
    path, err = _validate_target(initial_path)
    if err:
        ui.error(f"Неверная рабочая папка: {err}")
        return 1
    
    blazer = Blazer(str(path))
    mode_line = "CharmPkk: активен" if ui.has_charm() else "CharmPkk: не найден"
    
    while True:
        if ui.has_charm(): ui.console().terminal().clear()
        
        print(ui.banner("MAKEBLAZER", f"Time Machine | {mode_line}", gradient="cyberpunk"))
        print(_render_dashboard(blazer))
        
        choice = ui.select("Главное меню", [
            "📸 Снапшоты (Создать / Удалить)",
            "🕒 Машина времени (История / Откат)",
            "🔎 Поиск и Авто-бэкап",
            "⚙️  Настройки и Обслуживание",
            "❌ Выход",
        ])
        
        if choice is None or choice.startswith("❌"): break
        
        try:
            if choice.startswith("📸"): _menu_snapshots(blazer)
            elif choice.startswith("🕒"): _menu_time_machine(blazer)
            elif choice.startswith("🔎"): _menu_live_tools(blazer)
            elif choice.startswith("⚙"): 
                new_blazer = _menu_settings(blazer)
                if new_blazer: blazer = new_blazer
        except KeyboardInterrupt:
            pass
        except Exception as e:
            ui.error(f"Ошибка: {type(e).__name__}: {e}")
            ui.ask("Enter — назад")
            
    return 0