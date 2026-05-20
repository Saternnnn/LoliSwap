import json
import os
import re
import shutil
import subprocess
import sys
import threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox


APP_TITLE = "LoliSwap"
APP_DIR = Path.home() / "Documents" / "LoliSwap"
PROFILES_DIR = APP_DIR / "profiles"
CONFIG_PATH = APP_DIR / "config.json"

IGNORED_DIR_NAMES = {
    "cache",
    "Cache",
    "logs",
    "Logs",
    "temp",
    "Temp",
    "crash-reports",
    "downloads",
    "updates",
}


class ProfileManager:
    def __init__(self):
        self.ensure_dirs()
        self.config = self.load_config()

    @staticmethod
    def ensure_dirs():
        APP_DIR.mkdir(parents=True, exist_ok=True)
        PROFILES_DIR.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def load_config():
        if CONFIG_PATH.exists():
            try:
                return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass

        return {
            "loli_dir": "",
            "launcher_exe": "",
            "active_profile": "",
        }

    def save_config(self):
        CONFIG_PATH.write_text(
            json.dumps(self.config, ensure_ascii=False, indent=4),
            encoding="utf-8",
        )

    def set_loli_dir(self, path):
        path = Path(path).expanduser()

        if not path.exists() or not path.is_dir():
            raise FileNotFoundError(f"Папка не найдена: {path}")

        self.config["loli_dir"] = str(path)
        self.save_config()

    def set_launcher_exe(self, path):
        path = Path(path).expanduser()

        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"Файл лаунчера не найден: {path}")

        self.config["launcher_exe"] = str(path)
        self.save_config()

    def get_loli_dir(self):
        saved = self.config.get("loli_dir", "")

        if saved:
            path = Path(saved)
            if path.exists() and path.is_dir():
                return path

        candidates = self.find_loliland_dirs()

        if len(candidates) == 1:
            self.config["loli_dir"] = str(candidates[0])
            self.save_config()
            return candidates[0]

        raise RuntimeError(
            "Папка Loliland не задана. Нажми «Найти папку» или выбери её вручную."
        )

    @staticmethod
    def find_loliland_dirs():
        candidates = []

        for env_name in ("APPDATA", "LOCALAPPDATA"):
            base = os.environ.get(env_name)
            if not base:
                continue

            base_path = Path(base)
            if not base_path.exists():
                continue

            for item in base_path.iterdir():
                if item.is_dir() and re.search(r"loli|loliland", item.name, re.IGNORECASE):
                    candidates.append(item)

        appdata = os.environ.get("APPDATA")
        if appdata:
            minecraft_dir = Path(appdata) / ".minecraft"
            if minecraft_dir.exists():
                candidates.append(minecraft_dir)

        unique = []
        seen = set()

        for path in candidates:
            try:
                key = str(path.resolve()).lower()
            except OSError:
                key = str(path).lower()

            if key not in seen:
                unique.append(path)
                seen.add(key)

        return unique

    @staticmethod
    def should_ignore(path, full_copy=False):
        if full_copy:
            return False

        return path.name in IGNORED_DIR_NAMES

    def sync_dirs(self, source, destination, full_copy=False, progress=None):
        source = Path(source)
        destination = Path(destination)

        if not source.exists() or not source.is_dir():
            raise FileNotFoundError(f"Источник не найден: {source}")

        destination.mkdir(parents=True, exist_ok=True)

        if progress:
            progress(f"Источник: {source}")
            progress(f"Назначение: {destination}")

        # Удаляем из назначения то, чего нет в источнике.
        for dst_item in list(destination.rglob("*")):
            if self.should_ignore(dst_item, full_copy):
                continue

            relative = dst_item.relative_to(destination)
            src_item = source / relative

            if not src_item.exists():
                try:
                    if dst_item.is_dir():
                        shutil.rmtree(dst_item, ignore_errors=True)
                    else:
                        dst_item.unlink()
                except FileNotFoundError:
                    pass
                except PermissionError as error:
                    raise PermissionError(
                        f"Нет доступа к файлу: {dst_item}. Закрой лаунчер и повтори операцию."
                    ) from error

        # Копируем файлы из источника в назначение.
        files_copied = 0
        dirs_created = 0

        for src_item in source.rglob("*"):
            if self.should_ignore(src_item, full_copy):
                continue

            relative = src_item.relative_to(source)
            dst_item = destination / relative

            try:
                if src_item.is_dir():
                    dst_item.mkdir(parents=True, exist_ok=True)
                    dirs_created += 1
                else:
                    dst_item.parent.mkdir(parents=True, exist_ok=True)

                    # Если файл не изменился, не копируем его повторно.
                    if dst_item.exists():
                        try:
                            same_size = src_item.stat().st_size == dst_item.stat().st_size
                            same_mtime = int(src_item.stat().st_mtime) == int(dst_item.stat().st_mtime)
                            if same_size and same_mtime:
                                continue
                        except OSError:
                            pass

                    shutil.copy2(src_item, dst_item)
                    files_copied += 1

                    if progress and files_copied % 25 == 0:
                        progress(f"Скопировано файлов: {files_copied}")

            except PermissionError as error:
                raise PermissionError(
                    f"Нет доступа к файлу: {src_item}. Закрой лаунчер и повтори операцию."
                ) from error

        if progress:
            progress(f"Создано/проверено папок: {dirs_created}")
            progress(f"Скопировано файлов: {files_copied}")

    def list_profiles(self):
        if not PROFILES_DIR.exists():
            return []

        return sorted(
            profile.name
            for profile in PROFILES_DIR.iterdir()
            if profile.is_dir()
        )

    def save_profile(self, profile_name, full_copy=False, progress=None):
        profile_name = profile_name.strip()

        if not profile_name:
            raise ValueError("Имя профиля не указано.")

        if not re.fullmatch(r"[A-Za-zА-Яа-я0-9_\- ]{1,40}", profile_name):
            raise ValueError(
                "Имя профиля может содержать буквы, цифры, пробел, дефис и подчёркивание."
            )

        loli_dir = self.get_loli_dir()
        profile_dir = PROFILES_DIR / profile_name

        if progress:
            progress(f"Сохраняю профиль: {profile_name}")

        self.sync_dirs(loli_dir, profile_dir, full_copy=full_copy, progress=progress)

        self.config["active_profile"] = profile_name
        self.save_config()

        if progress:
            progress(f"Профиль сохранён: {profile_name}")

    def switch_profile(self, profile_name, full_copy=False, progress=None):
        profile_name = profile_name.strip()

        if not profile_name:
            raise ValueError("Имя профиля не указано.")

        loli_dir = self.get_loli_dir()
        target_profile_dir = PROFILES_DIR / profile_name

        if not target_profile_dir.exists():
            raise FileNotFoundError(f"Профиль не найден: {profile_name}")

        current_profile = self.config.get("active_profile", "")

        if current_profile and current_profile != profile_name:
            if progress:
                progress(f"Сначала сохраняю текущий активный профиль: {current_profile}")
            self.save_profile(current_profile, full_copy=full_copy, progress=progress)

        if progress:
            progress(f"Переключаюсь на профиль: {profile_name}")

        self.sync_dirs(target_profile_dir, loli_dir, full_copy=full_copy, progress=progress)

        self.config["active_profile"] = profile_name
        self.save_config()

        if progress:
            progress(f"Активный профиль: {profile_name}")

    def start_launcher(self):
        launcher_exe = self.config.get("launcher_exe", "")

        if not launcher_exe:
            raise RuntimeError("Файл лаунчера не выбран.")

        path = Path(launcher_exe)

        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"Файл лаунчера не найден: {path}")

        subprocess.Popen([str(path)], shell=False)

    def delete_profile(self, profile_name, progress=None):
        profile_name = profile_name.strip()

        if not profile_name:
            raise ValueError("Имя профиля не указано.")

        profile_dir = PROFILES_DIR / profile_name

        if not profile_dir.exists():
            raise FileNotFoundError(f"Профиль не найден: {profile_name}")

        shutil.rmtree(profile_dir)

        if self.config.get("active_profile") == profile_name:
            self.config["active_profile"] = ""
            self.save_config()

        if progress:
            progress(f"Профиль удалён: {profile_name}")


class LoliSwapApp:
    def __init__(self, root):
        self.root = root
        self.manager = ProfileManager()

        self.profile_var = tk.StringVar()
        self.loli_dir_var = tk.StringVar(value=self.manager.config.get("loli_dir", ""))
        self.launcher_exe_var = tk.StringVar(value=self.manager.config.get("launcher_exe", ""))
        self.start_launcher_var = tk.BooleanVar(value=False)
        self.full_copy_var = tk.BooleanVar(value=False)

        self.worker_running = False
        self.buttons = []

        self.setup_window()
        self.create_ui()
        self.refresh_profiles(log=False)

    def setup_window(self):
        self.root.title(APP_TITLE)
        self.root.geometry("820x600")
        self.root.minsize(780, 560)

        try:
            self.root.iconbitmap(default="")
        except Exception:
            pass

    def create_ui(self):
        outer = ttk.Frame(self.root, padding=16)
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0, 12))

        ttk.Label(
            header,
            text="LoliSwap",
            font=("Segoe UI", 18, "bold")
        ).pack(anchor="w")

        ttk.Label(
            header,
            text="Аккуратное переключение локальных профилей Loliland Launcher",
            font=("Segoe UI", 10)
        ).pack(anchor="w")

        settings = ttk.LabelFrame(outer, text="Настройки")
        settings.pack(fill="x", pady=(0, 12))

        self.add_path_row(
            parent=settings,
            row=0,
            label="Папка Loliland:",
            variable=self.loli_dir_var,
            command=self.choose_loli_dir,
            button_text="Выбрать папку",
        )

        self.add_path_row(
            parent=settings,
            row=1,
            label="Файл лаунчера:",
            variable=self.launcher_exe_var,
            command=self.choose_launcher_exe,
            button_text="Выбрать .exe",
        )

        options = ttk.Frame(settings)
        options.grid(row=2, column=1, columnspan=2, sticky="w", padx=8, pady=(0, 8))

        ttk.Checkbutton(
            options,
            text="Запускать лаунчер после переключения",
            variable=self.start_launcher_var,
        ).pack(side="left", padx=(0, 20))

        ttk.Checkbutton(
            options,
            text="Полное копирование",
            variable=self.full_copy_var,
        ).pack(side="left")

        profile_box = ttk.LabelFrame(outer, text="Профили")
        profile_box.pack(fill="x", pady=(0, 12))

        ttk.Label(profile_box, text="Профиль:").grid(row=0, column=0, padx=8, pady=8, sticky="w")

        self.profile_combo = ttk.Combobox(profile_box, textvariable=self.profile_var)
        self.profile_combo.grid(row=0, column=1, padx=8, pady=8, sticky="ew")

        profile_box.columnconfigure(1, weight=1)

        actions = ttk.Frame(profile_box)
        actions.grid(row=1, column=0, columnspan=2, padx=8, pady=(0, 8), sticky="ew")

        self.add_button(actions, "Найти папку", self.find_folder).pack(side="left", padx=(0, 8))
        self.add_button(actions, "Сохранить профиль", self.save_profile).pack(side="left", padx=(0, 8))
        self.add_button(actions, "Переключиться", self.switch_profile).pack(side="left", padx=(0, 8))
        self.add_button(actions, "Удалить профиль", self.delete_profile).pack(side="left", padx=(0, 8))
        self.add_button(actions, "Обновить список", lambda: self.refresh_profiles(log=True)).pack(side="left", padx=(0, 8))

        self.status_var = tk.StringVar(value="Готово.")
        ttk.Label(outer, textvariable=self.status_var).pack(anchor="w", pady=(0, 6))

        log_frame = ttk.LabelFrame(outer, text="Лог")
        log_frame.pack(fill="both", expand=True)

        self.log_text = tk.Text(log_frame, height=16, wrap="word", font=("Consolas", 10))
        self.log_text.pack(side="left", fill="both", expand=True)

        scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        scroll.pack(side="right", fill="y")
        self.log_text.configure(yscrollcommand=scroll.set)

        bottom = ttk.Frame(outer)
        bottom.pack(fill="x", pady=(8, 0))

        self.add_button(bottom, "Открыть папку профилей", self.open_profiles_dir).pack(side="left", padx=(0, 8))
        self.add_button(bottom, "Очистить лог", self.clear_log).pack(side="right")

        self.log("Важно: перед сохранением и переключением полностью закрой Loliland Launcher.")
        self.log(f"Папка данных приложения: {APP_DIR}")

    def add_path_row(self, parent, row, label, variable, command, button_text):
        ttk.Label(parent, text=label).grid(row=row, column=0, padx=8, pady=8, sticky="w")

        entry = ttk.Entry(parent, textvariable=variable)
        entry.grid(row=row, column=1, padx=8, pady=8, sticky="ew")

        button = ttk.Button(parent, text=button_text, command=command)
        button.grid(row=row, column=2, padx=8, pady=8, sticky="e")

        parent.columnconfigure(1, weight=1)

    def add_button(self, parent, text, command):
        button = ttk.Button(parent, text=text, command=command)
        self.buttons.append(button)
        return button

    def log(self, message):
        self.log_text.insert("end", str(message) + "\n")
        self.log_text.see("end")
        self.root.update_idletasks()

    def clear_log(self):
        self.log_text.delete("1.0", "end")

    def set_busy(self, busy, status=None):
        self.worker_running = busy

        for button in self.buttons:
            button.configure(state="disabled" if busy else "normal")

        if status:
            self.status_var.set(status)
        elif not busy:
            self.status_var.set("Готово.")

    def run_in_thread(self, title, action, on_success=None):
        if self.worker_running:
            return

        def worker():
            try:
                self.root.after(0, lambda: self.set_busy(True, title))
                self.root.after(0, lambda: self.log(""))
                self.root.after(0, lambda: self.log(f"=== {title} ==="))

                action()

                if on_success:
                    self.root.after(0, on_success)

                self.root.after(0, lambda: self.log("Операция завершена."))
                self.root.after(0, lambda: self.set_busy(False, "Готово."))

            except Exception as error:
                error_text = str(error)
                self.root.after(0, lambda: self.log(f"Ошибка: {error_text}"))
                self.root.after(0, lambda: self.set_busy(False, "Ошибка."))
                self.root.after(0, lambda: messagebox.showerror("Ошибка", error_text))

        threading.Thread(target=worker, daemon=True).start()

    def apply_settings_from_fields(self):
        loli_dir = self.loli_dir_var.get().strip()
        launcher_exe = self.launcher_exe_var.get().strip()

        if loli_dir:
            self.manager.set_loli_dir(loli_dir)

        if launcher_exe:
            self.manager.set_launcher_exe(launcher_exe)

    def choose_loli_dir(self):
        path = filedialog.askdirectory(title="Выбери папку Loliland Launcher")
        if path:
            self.loli_dir_var.set(path)
            try:
                self.manager.set_loli_dir(path)
                self.log(f"Папка Loliland сохранена: {path}")
            except Exception as error:
                messagebox.showerror("Ошибка", str(error))

    def choose_launcher_exe(self):
        path = filedialog.askopenfilename(
            title="Выбери файл лаунчера",
            filetypes=[("EXE files", "*.exe"), ("All files", "*.*")],
        )

        if path:
            self.launcher_exe_var.set(path)
            try:
                self.manager.set_launcher_exe(path)
                self.log(f"Файл лаунчера сохранён: {path}")
            except Exception as error:
                messagebox.showerror("Ошибка", str(error))

    def find_folder(self):
        candidates = self.manager.find_loliland_dirs()

        self.log("")
        self.log("=== Поиск папки Loliland ===")

        if not candidates:
            self.log("Папки не найдены.")
            messagebox.showinfo(
                "Поиск завершён",
                "Папки, похожие на Loliland, не найдены. Выбери папку вручную.",
            )
            return

        for index, path in enumerate(candidates, start=1):
            self.log(f"{index}. {path}")

        if len(candidates) == 1:
            self.loli_dir_var.set(str(candidates[0]))
            self.manager.set_loli_dir(candidates[0])
            self.log(f"Автоматически выбрана папка: {candidates[0]}")
            messagebox.showinfo("Готово", "Папка найдена и выбрана автоматически.")
        else:
            messagebox.showinfo(
                "Найдено несколько папок",
                "В логе показаны варианты. Выбери правильную папку вручную.",
            )

    def save_profile(self):
        profile_name = self.profile_var.get().strip()

        if not profile_name:
            messagebox.showwarning("Профиль", "Введи имя профиля, например main или alt.")
            return

        if not self.confirm_launcher_closed():
            return

        def action():
            self.apply_settings_from_fields()
            self.manager.save_profile(
                profile_name,
                full_copy=self.full_copy_var.get(),
                progress=lambda msg: self.root.after(0, lambda m=msg: self.log(m)),
            )

        def success():
            self.refresh_profiles(log=False)
            messagebox.showinfo("Готово", f"Профиль сохранён: {profile_name}")

        self.run_in_thread(f"Сохранение профиля: {profile_name}", action, success)

    def switch_profile(self):
        profile_name = self.profile_var.get().strip()

        if not profile_name:
            messagebox.showwarning("Профиль", "Выбери или введи имя профиля.")
            return

        if not self.confirm_launcher_closed():
            return

        def action():
            self.apply_settings_from_fields()
            self.manager.switch_profile(
                profile_name,
                full_copy=self.full_copy_var.get(),
                progress=lambda msg: self.root.after(0, lambda m=msg: self.log(m)),
            )

            if self.start_launcher_var.get():
                self.manager.start_launcher()

        def success():
            self.refresh_profiles(log=False)
            messagebox.showinfo("Готово", f"Активный профиль: {profile_name}")

        self.run_in_thread(f"Переключение на профиль: {profile_name}", action, success)

    def delete_profile(self):
        profile_name = self.profile_var.get().strip()

        if not profile_name:
            messagebox.showwarning("Профиль", "Выбери профиль для удаления.")
            return

        confirm = messagebox.askyesno(
            "Удалить профиль",
            f"Удалить сохранённый профиль «{profile_name}»?\n\nЭто не удалит аккаунт, только локальную копию профиля LoliSwap.",
        )

        if not confirm:
            return

        def action():
            self.manager.delete_profile(
                profile_name,
                progress=lambda msg: self.root.after(0, lambda m=msg: self.log(m)),
            )

        def success():
            self.profile_var.set("")
            self.refresh_profiles(log=False)
            messagebox.showinfo("Готово", f"Профиль удалён: {profile_name}")

        self.run_in_thread(f"Удаление профиля: {profile_name}", action, success)

    def refresh_profiles(self, log=True):
        profiles = self.manager.list_profiles()
        self.profile_combo["values"] = profiles

        active = self.manager.config.get("active_profile", "")

        if active and active in profiles:
            self.profile_var.set(active)
        elif profiles and not self.profile_var.get().strip():
            self.profile_var.set(profiles[0])

        if log:
            self.log("")
            self.log("=== Список профилей ===")
            if profiles:
                for profile in profiles:
                    marker = " *" if profile == active else ""
                    self.log(f"- {profile}{marker}")
            else:
                self.log("Профилей пока нет.")

    def confirm_launcher_closed(self):
        return messagebox.askyesno(
            "Проверка",
            "Loliland Launcher полностью закрыт?\n\nЕсли он открыт, часть файлов может быть заблокирована.",
        )

    def open_profiles_dir(self):
        PROFILES_DIR.mkdir(parents=True, exist_ok=True)

        if os.name == "nt":
            os.startfile(PROFILES_DIR)
        else:
            subprocess.Popen(["xdg-open", str(PROFILES_DIR)])


def main():
    root = tk.Tk()
    app = LoliSwapApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
