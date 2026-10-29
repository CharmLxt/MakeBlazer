"""CLI для makeblazer."""
import sys
import argparse

def main():
    parser = argparse.ArgumentParser(
        prog="makeblazer",
        description="MakeBlazer — локальная машина времени для файлов."
    )
    parser.add_argument("-d", "--dir", default=".", metavar="PATH", help="Рабочая папка (по умолчанию текущая).")
    
    subparsers = parser.add_subparsers(dest="command", help="Команды")
    
    # snapshot
    p_snap = subparsers.add_parser("snapshot", help="Создать снапшот")
    p_snap.add_argument("-m", "--message", default="CLI snapshot", help="Сообщение")
    
    # history
    subparsers.add_parser("history", help="Показать историю снапшотов")
    
    # restore
    p_restore = subparsers.add_parser("restore", help="Восстановить файл")
    p_restore.add_argument("file", help="Путь к файлу")
    p_restore.add_argument("index", type=int, help="Индекс снапшота")
    
    # rollback
    p_rollback = subparsers.add_parser("rollback", help="Откатить всю папку")
    p_rollback.add_argument("index", type=int, help="Индекс снапшота")
    
    # search
    p_search = subparsers.add_parser("search", help="Поиск по истории")
    p_search.add_argument("query", help="Текст для поиска")
    
    # status
    subparsers.add_parser("status", help="Показать измененные файлы")
    
    # gc
    subparsers.add_parser("gc", help="Сборка мусора (очистка диска)")
    
    args = parser.parse_args()

    from .core import Blazer
    from . import charm_enhance as ui

    try:
        blazer = Blazer(args.dir)
    except Exception as e:
        print(f"Ошибка инициализации: {e}")
        return 1

    # Если не указана команда — запускаем TUI-меню
    if not args.command:
        from .menu import run
        try:
            return run(target_dir=args.dir)
        except KeyboardInterrupt:
            print()
            return 130

    # Обработка CLI-команд
    try:
        if args.command == "snapshot":
            ui.info("Сканирование...")
            count = blazer.snapshot(message=args.message)
            ui.success(f"Снапшот создан! Сохранено файлов: {count}")
            
        elif args.command == "history":
            history = blazer.get_history()
            if not history:
                ui.warning("История пуста.")
            else:
                headers = ["#", "Дата", "Сообщение", "Файлов"]
                rows = [[str(i), h["timestamp"], h["message"], str(len(h["files"]))] for i, h in enumerate(history)]
                print(ui.table(headers, rows))
                
        elif args.command == "restore":
            ok, msg = blazer.restore_file(args.file, args.index)
            (ui.success if ok else ui.error)(msg)
            
        elif args.command == "rollback":
            if ui.confirm(f"Откатить папку к снапшоту #{args.index}? Новые файлы будут удалены.", default=False):
                ok, msg = blazer.restore_snapshot(args.index)
                (ui.success if ok else ui.error)(msg)
            else:
                ui.warning("Отменено.")
                
        elif args.command == "search":
            ui.info("Поиск по истории...")
            results = blazer.search_history(args.query)
            if not results:
                ui.warning("Ничего не найдено.")
            else:
                ui.success(f"Найдено: {len(results)}")
                for r in results[:20]:
                    print(f"  [#{r['snapshot_idx']}] {r['file']}:{r['line']} — {r['text']}")
                if len(results) > 20:
                    ui.info(f"... и еще {len(results) - 20} совпадений.")
                    
        elif args.command == "status":
            changed = blazer.get_changed_files()
            if changed and "Файлов нет" not in changed[0]:
                ui.warning(f"Изменено файлов: {len(changed)}")
                for f in changed[:20]:
                    print(f"  M {f}")
            else:
                ui.success("Все файлы сохранены (рабочая директория чиста).")
                
        elif args.command == "gc":
            ui.info("Очистка неиспользуемых объектов...")
            deleted = blazer.garbage_collect()
            ui.success(f"Удалено объектов: {deleted}")
            
    except Exception as e:
        ui.error(f"Ошибка: {type(e).__name__}: {e}")
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())