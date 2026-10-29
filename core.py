"""MakeBlazer: Ядро системы снапшотов."""
import os
import json
import hashlib
import shutil
import fnmatch
import zipfile
from pathlib import Path
from datetime import datetime

class Blazer:
    def __init__(self, target_dir="."):
        self.target = Path(target_dir).resolve()
        self.blazer_dir = self.target / ".blazer"
        self.objects_dir = self.blazer_dir / "objects"
        self.manifest_path = self.blazer_dir / "manifest.json"
        self.ignore_file = self.target / ".blazerignore"
        self.ignore_patterns = []
        self._init_db()

    def _init_db(self):
        self.objects_dir.mkdir(parents=True, exist_ok=True)
        if not self.manifest_path.exists():
            self.manifest_path.write_text("[]", encoding="utf-8")
        if not self.ignore_file.exists():
            default_ignore = "__pycache__/\n*.pyc\n.blazer/\n.venv/\nnode_modules/\n"
            self.ignore_file.write_text(default_ignore, encoding="utf-8")
        self._load_ignore()

    def _load_ignore(self):
        self.ignore_patterns = []
        if self.ignore_file.exists():
            for line in self.ignore_file.read_text("utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    self.ignore_patterns.append(line)

    def _is_ignored(self, rel_path):
        rel_str = str(rel_path).replace("\\", "/")
        parts = rel_str.split("/")
        for pattern in self.ignore_patterns:
            if pattern.endswith("/"):
                if pattern[:-1] in parts:
                    return True
            elif fnmatch.fnmatch(rel_str, pattern) or fnmatch.fnmatch(parts[-1], pattern):
                return True
        return False

    def _hash_file(self, filepath):
        hasher = hashlib.sha256()
        try:
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception:
            return None

    def snapshot(self, message="Manual snapshot"):
        files = []
        for root, dirs, filenames in os.walk(self.target):
            root_path = Path(root)
            if ".blazer" in root_path.parts:
                continue
            for f in filenames:
                full_path = root_path / f
                rel_path = full_path.relative_to(self.target)
                if self._is_ignored(rel_path):
                    continue
                file_hash = self._hash_file(full_path)
                if file_hash:
                    obj_path = self.objects_dir / file_hash
                    if not obj_path.exists():
                        shutil.copy2(full_path, obj_path)
                    files.append({"path": rel_path.as_posix(), "hash": file_hash})

        manifest = self.get_history()
        manifest.append({
            "message": message,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "files": files
        })
        self.manifest_path.write_text(json.dumps(manifest, indent=2), "utf-8")
        return len(files)

    def get_history(self):
        if not self.manifest_path.exists(): return []
        return json.loads(self.manifest_path.read_text("utf-8"))

    def restore_file(self, target_path, snapshot_index):
        manifest = self.get_history()
        if snapshot_index < 0 or snapshot_index >= len(manifest):
            return False, "Неверный индекс снапшота"
        snap = manifest[snapshot_index]
        norm_path = Path(target_path).as_posix()
        for f in snap["files"]:
            if f["path"] == norm_path:
                obj_path = self.objects_dir / f["hash"]
                dest = self.target / target_path
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(obj_path, dest)
                return True, f"Файл {target_path} восстановлен из {snap['timestamp']}"
        return False, "Файл не найден в этом снапшоте"

    def restore_snapshot(self, snapshot_index):
        manifest = self.get_history()
        if snapshot_index < 0 or snapshot_index >= len(manifest):
            return False, "Неверный индекс снапшота"
        snap = manifest[snapshot_index]
        snap_files = {f["path"]: f["hash"] for f in snap["files"]}
        
        for root, dirs, filenames in os.walk(self.target):
            root_path = Path(root)
            if ".blazer" in root_path.parts: continue
            for f in filenames:
                full_path = root_path / f
                rel_path = full_path.relative_to(self.target).as_posix()
                if not self._is_ignored(rel_path) and rel_path not in snap_files:
                    try: full_path.unlink()
                    except Exception: pass
                    
        for rel_path, file_hash in snap_files.items():
            obj_path = self.objects_dir / file_hash
            dest = self.target / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(obj_path, dest)
        return True, f"Полный откат выполнен к {snap['timestamp']}"

    def delete_snapshot(self, snapshot_index):
        """Удаляет снапшот из истории (файлы останутся до вызова GC)."""
        manifest = self.get_history()
        if 0 <= snapshot_index < len(manifest):
            deleted = manifest.pop(snapshot_index)
            self.manifest_path.write_text(json.dumps(manifest, indent=2), "utf-8")
            return True, f"Снапшот '{deleted['message']}' удалён."
        return False, "Неверный индекс."

    def garbage_collect(self):
        manifest = self.get_history()
        used_hashes = set()
        for snap in manifest:
            for f in snap["files"]:
                used_hashes.add(f["hash"])
        deleted = 0
        for obj in self.objects_dir.iterdir():
            if obj.is_file() and obj.name not in used_hashes:
                try:
                    obj.unlink()
                    deleted += 1
                except Exception:
                    pass
        return deleted

    def export_snapshot(self, snapshot_index, zip_path):
        manifest = self.get_history()
        if snapshot_index < 0 or snapshot_index >= len(manifest):
            return False, "Неверный индекс"
        snap = manifest[snapshot_index]
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for f in snap["files"]:
                obj_path = self.objects_dir / f["hash"]
                if obj_path.exists():
                    zipf.write(obj_path, arcname=f["path"])
        return True, f"Экспортировано в {zip_path}"

    def search_history(self, query):
        """Ищет текстовый запрос во всех исторических файлах (даже удаленных)."""
        manifest = self.get_history()
        results = []
        query_lower = query.lower()

        for i, snap in enumerate(manifest):
            for f in snap["files"]:
                obj_path = self.objects_dir / f["hash"]
                if not obj_path.exists(): continue
                try:
                    content = obj_path.read_text("utf-8", errors="replace")
                    for line_num, line in enumerate(content.splitlines(), 1):
                        if query_lower in line.lower():
                            results.append({
                                "snapshot_idx": i,
                                "timestamp": snap["timestamp"],
                                "message": snap["message"],
                                "file": f["path"],
                                "line": line_num,
                                "text": line.strip()
                            })
                except Exception:
                    continue
        return results

    def get_file_timeline(self, target_path):
        """Возвращает все версии конкретного файла за всю историю."""
        manifest = self.get_history()
        norm_path = Path(target_path).as_posix()
        timeline = []
        for i, snap in enumerate(manifest):
            for f in snap["files"]:
                if f["path"] == norm_path:
                    timeline.append({
                        "idx": i,
                        "timestamp": snap["timestamp"],
                        "message": snap["message"],
                        "hash": f["hash"]
                    })
                    break
        return timeline

    def get_storage_stats(self):
        """Показывает размер хранилища и количество объектов."""
        total_size = 0
        for obj in self.objects_dir.iterdir():
            if obj.is_file():
                total_size += obj.stat().st_size
        manifest = self.get_history()
        return {
            "snapshots": len(manifest),
            "objects": len(list(self.objects_dir.iterdir())),
            "size_mb": round(total_size / (1024 * 1024), 2)
        }

    def get_changed_files(self):
        """Возвращает список файлов, которые изменились с момента последнего снапшота."""
        manifest = self.get_history()
        if not manifest: return ["Файлов нет в истории (сделайте первый снапшот)"]
        
        last_snap = manifest[-1]
        snap_hashes = {f["path"]: f["hash"] for f in last_snap["files"]}
        
        changed = []
        for root, dirs, filenames in os.walk(self.target):
            root_path = Path(root)
            if ".blazer" in root_path.parts: continue
            for f in filenames:
                full_path = root_path / f
                rel_path = full_path.relative_to(self.target).as_posix()
                if self._is_ignored(rel_path): continue
                current_hash = self._hash_file(full_path)
                if snap_hashes.get(rel_path) != current_hash:
                    changed.append(rel_path)
                    
        for snap_path in snap_hashes:
            if not (self.target / snap_path).exists():
                changed.append(f"{snap_path} (Удалён)")
                
        return changed