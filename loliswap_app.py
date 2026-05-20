import base64
import ctypes
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from ctypes import wintypes
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox


APP_TITLE = "LoliSwap"
APP_DIR = Path.home() / "Documents" / "LoliSwap"
PROFILES_DIR = APP_DIR / "profiles"
CONFIG_PATH = APP_DIR / "config.json"

IGNORED_DIR_NAMES = {
    "cache",
    "logs",
    "temp",
    "crash-reports",
    "downloads",
    "updates",
}

PROFILE_NAME_RE = re.compile(r"[A-Za-zА-Яа-я0-9_\- ]{1,40}")
AUTO_LOGIN_DELAY_DEFAULT = 6
AUTO_LOGIN_DELAY_MIN = 1
AUTO_LOGIN_DELAY_MAX = 60


class DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_char)),
    ]


def require_windows(feature):
    if os.name != "nt":
        raise RuntimeError(f"{feature} доступен только в Windows.")


def windows_error(message):
    return OSError(ctypes.get_last_error(), message)


def protect_secret(secret):
    require_windows("Защищённое хранение паролей")

    data = secret.encode("utf-8")
    buffer = ctypes.create_string_buffer(data)
    blob_in = DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))
    blob_out = DataBlob()

    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    crypt32.CryptProtectData.argtypes = [
        ctypes.POINTER(DataBlob),
        wintypes.LPCWSTR,
        ctypes.POINTER(DataBlob),
        wintypes.LPVOID,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(DataBlob),
    ]
    crypt32.CryptProtectData.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [wintypes.HLOCAL]
    kernel32.LocalFree.restype = wintypes.HLOCAL

    ok = crypt32.CryptProtectData(
        ctypes.byref(blob_in),
        "LoliSwap account password",
        None,
        None,
        None,
        0,
        ctypes.byref(blob_out),
    )

    if not ok:
        raise windows_error("Не удалось защитить пароль через Windows DPAPI.")

    try:
        encrypted = ctypes.string_at(blob_out.pbData, blob_out.cbData)
        return base64.b64encode(encrypted).decode("ascii")
    finally:
        if blob_out.pbData:
            kernel32.LocalFree(ctypes.cast(blob_out.pbData, wintypes.HLOCAL))


def unprotect_secret(token):
    require_windows("Чтение сохранённого пароля")

    data = base64.b64decode(token.encode("ascii"))
    buffer = ctypes.create_string_buffer(data)
    blob_in = DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))
    blob_out = DataBlob()

    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(DataBlob),
        ctypes.POINTER(wintypes.LPWSTR),
        ctypes.POINTER(DataBlob),
        wintypes.LPVOID,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(DataBlob),
    ]
    crypt32.CryptUnprotectData.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [wintypes.HLOCAL]
    kernel32.LocalFree.restype = wintypes.HLOCAL

    ok = crypt32.CryptUnprotectData(
        ctypes.byref(blob_in),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(blob_out),
    )

    if not ok:
        raise windows_error("Не удалось прочитать сохранённый пароль через Windows DPAPI.")

    try:
        decrypted = ctypes.string_at(blob_out.pbData, blob_out.cbData)
        return decrypted.decode("utf-8")
    finally:
        if blob_out.pbData:
            kernel32.LocalFree(ctypes.cast(blob_out.pbData, wintypes.HLOCAL))


class WindowsClipboard:
    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002

    @staticmethod
    def get_text():
        require_windows("Буфер обмена")

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

        user32.OpenClipboard.argtypes = [wintypes.HWND]
        user32.OpenClipboard.restype = wintypes.BOOL
        user32.CloseClipboard.argtypes = []
        user32.CloseClipboard.restype = wintypes.BOOL
        user32.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
        user32.IsClipboardFormatAvailable.restype = wintypes.BOOL
        user32.GetClipboardData.argtypes = [wintypes.UINT]
        user32.GetClipboardData.restype = wintypes.HANDLE
        kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalLock.restype = wintypes.LPVOID
        kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalUnlock.restype = wintypes.BOOL

        if not user32.OpenClipboard(None):
            return None

        try:
            if not user32.IsClipboardFormatAvailable(WindowsClipboard.CF_UNICODETEXT):
                return None

            handle = user32.GetClipboardData(WindowsClipboard.CF_UNICODETEXT)
            if not handle:
                return None

            pointer = kernel32.GlobalLock(handle)
            if not pointer:
                return None

            try:
                return ctypes.wstring_at(pointer)
            finally:
                kernel32.GlobalUnlock(handle)
        finally:
            user32.CloseClipboard()

    @staticmethod
    def set_text(text):
        require_windows("Буфер обмена")

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

        user32.OpenClipboard.argtypes = [wintypes.HWND]
        user32.OpenClipboard.restype = wintypes.BOOL
        user32.EmptyClipboard.argtypes = []
        user32.EmptyClipboard.restype = wintypes.BOOL
        user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
        user32.SetClipboardData.restype = wintypes.HANDLE
        user32.CloseClipboard.argtypes = []
        user32.CloseClipboard.restype = wintypes.BOOL
        kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
        kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
        kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalLock.restype = wintypes.LPVOID
        kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalUnlock.restype = wintypes.BOOL
        kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalFree.restype = wintypes.HGLOBAL

        data = (text + "\0").encode("utf-16le")

        if not user32.OpenClipboard(None):
            raise windows_error("Не удалось открыть буфер обмена.")

        handle = None

        try:
            user32.EmptyClipboard()

            handle = kernel32.GlobalAlloc(WindowsClipboard.GMEM_MOVEABLE, len(data))
            if not handle:
                raise windows_error("Не удалось выделить память для буфера обмена.")

            pointer = kernel32.GlobalLock(handle)
            if not pointer:
                raise windows_error("Не удалось записать текст в буфер обмена.")

            try:
                ctypes.memmove(pointer, data, len(data))
            finally:
                kernel32.GlobalUnlock(handle)

            if not user32.SetClipboardData(WindowsClipboard.CF_UNICODETEXT, handle):
                raise windows_error("Не удалось обновить буфер обмена.")

            handle = None
        finally:
            if handle:
                kernel32.GlobalFree(handle)
            user32.CloseClipboard()

    @staticmethod
    def clear():
        require_windows("Буфер обмена")

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.OpenClipboard.argtypes = [wintypes.HWND]
        user32.OpenClipboard.restype = wintypes.BOOL
        user32.EmptyClipboard.argtypes = []
        user32.EmptyClipboard.restype = wintypes.BOOL
        user32.CloseClipboard.argtypes = []
        user32.CloseClipboard.restype = wintypes.BOOL

        if not user32.OpenClipboard(None):
            return

        try:
            user32.EmptyClipboard()
        finally:
            user32.CloseClipboard()


class WindowsKeyboard:
    KEYEVENTF_KEYUP = 0x0002
    VK_CONTROL = 0x11
    VK_RETURN = 0x0D
    VK_TAB = 0x09
    VK_V = 0x56

    @staticmethod
    def press_key(vk_code):
        require_windows("Автоввод")

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.keybd_event.argtypes = [
            wintypes.BYTE,
            wintypes.BYTE,
            wintypes.DWORD,
            wintypes.ULONG,
        ]
        user32.keybd_event.restype = None

        user32.keybd_event(vk_code, 0, 0, 0)
        user32.keybd_event(vk_code, 0, WindowsKeyboard.KEYEVENTF_KEYUP, 0)
        time.sleep(0.08)

    @staticmethod
    def paste_text(text):
        require_windows("Автоввод")

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.keybd_event.argtypes = [
            wintypes.BYTE,
            wintypes.BYTE,
            wintypes.DWORD,
            wintypes.ULONG,
        ]
        user32.keybd_event.restype = None

        WindowsClipboard.set_text(text)
        time.sleep(0.08)
        user32.keybd_event(WindowsKeyboard.VK_CONTROL, 0, 0, 0)
        user32.keybd_event(WindowsKeyboard.VK_V, 0, 0, 0)
        user32.keybd_event(WindowsKeyboard.VK_V, 0, WindowsKeyboard.KEYEVENTF_KEYUP, 0)
        user32.keybd_event(WindowsKeyboard.VK_CONTROL, 0, WindowsKeyboard.KEYEVENTF_KEYUP, 0)
        time.sleep(0.12)


class WindowsWindow:
    SW_RESTORE = 9

    @staticmethod
    def focus_process_window(pid, timeout=3):
        require_windows("Фокус окна лаунчера")

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        enum_windows_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        user32.EnumWindows.argtypes = [enum_windows_proc, wintypes.LPARAM]
        user32.EnumWindows.restype = wintypes.BOOL
        user32.IsWindowVisible.argtypes = [wintypes.HWND]
        user32.IsWindowVisible.restype = wintypes.BOOL
        user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.ShowWindow.restype = wintypes.BOOL
        user32.SetForegroundWindow.argtypes = [wintypes.HWND]
        user32.SetForegroundWindow.restype = wintypes.BOOL

        deadline = time.time() + timeout

        while time.time() < deadline:
            found_hwnd = []

            def callback(hwnd, lparam):
                window_pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))

                if window_pid.value == pid and user32.IsWindowVisible(hwnd):
                    found_hwnd.append(hwnd)
                    return False

                return True

            callback_ref = enum_windows_proc(callback)
            user32.EnumWindows(callback_ref, 0)

            if found_hwnd:
                hwnd = found_hwnd[0]
                user32.ShowWindow(hwnd, WindowsWindow.SW_RESTORE)
                return bool(user32.SetForegroundWindow(hwnd))

            time.sleep(0.2)

        return False


class ProfileManager:
    def __init__(self):
        self.ensure_dirs()
        self.config = self.load_config()

    @staticmethod
    def default_config():
        return {
            "loli_dir": "",
            "launcher_exe": "",
            "active_profile": "",
            "auto_login": False,
            "auto_login_delay": AUTO_LOGIN_DELAY_DEFAULT,
            "accounts": {},
        }

    @staticmethod
    def ensure_dirs():
        APP_DIR.mkdir(parents=True, exist_ok=True)
        PROFILES_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def load_config(cls):
        config = cls.default_config()

        if CONFIG_PATH.exists():
            try:
                loaded = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    config.update(loaded)
            except json.JSONDecodeError:
                pass

        if not isinstance(config.get("accounts"), dict):
            config["accounts"] = {}

        return config

    def save_config(self):
        CONFIG_PATH.write_text(
            json.dumps(self.config, ensure_ascii=False, indent=4),
            encoding="utf-8",
        )

    @staticmethod
    def validate_profile_name(profile_name):
        profile_name = profile_name.strip()

        if not profile_name:
            raise ValueError("Имя профиля не указано.")

        if not PROFILE_NAME_RE.fullmatch(profile_name):
            raise ValueError(
                "Имя профиля может содержать буквы, цифры, пробел, дефис и подчёркивание."
            )

        return profile_name

    @staticmethod
    def profile_dir(profile_name):
        profile_name = ProfileManager.validate_profile_name(profile_name)
        profile_dir = PROFILES_DIR / profile_name

        try:
            profile_dir.resolve().relative_to(PROFILES_DIR.resolve())
        except ValueError as error:
            raise ValueError("Некорректный путь профиля.") from error

        return profile_dir

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

    def set_auto_login_options(self, enabled, delay):
        delay = int(delay)

        if delay < AUTO_LOGIN_DELAY_MIN or delay > AUTO_LOGIN_DELAY_MAX:
            raise ValueError(
                f"Задержка автологина должна быть от {AUTO_LOGIN_DELAY_MIN} до {AUTO_LOGIN_DELAY_MAX} секунд."
            )

        self.config["auto_login"] = bool(enabled)
        self.config["auto_login_delay"] = delay
        self.save_config()

    def has_account_credentials(self, profile_name):
        try:
            profile_name = self.validate_profile_name(profile_name)
        except ValueError:
            return False

        account = self.config.get("accounts", {}).get(profile_name)
        return bool(account and account.get("login") and account.get("password_dpapi"))

    def get_account_login(self, profile_name):
        try:
            profile_name = self.validate_profile_name(profile_name)
        except ValueError:
            return ""

        account = self.config.get("accounts", {}).get(profile_name, {})
        return account.get("login", "")

    def save_account_credentials(self, profile_name, login, password=None):
        profile_name = self.validate_profile_name(profile_name)
        login = login.strip()

        if not login:
            raise ValueError("Логин не указан.")

        accounts = self.config.setdefault("accounts", {})
        existing = accounts.get(profile_name, {})

        if not password:
            if not existing.get("password_dpapi"):
                raise ValueError("Пароль не указан.")
            password_dpapi = existing["password_dpapi"]
        else:
            password_dpapi = protect_secret(password)

        accounts[profile_name] = {
            "login": login,
            "password_dpapi": password_dpapi,
        }
        self.save_config()

    def get_account_credentials(self, profile_name):
        profile_name = self.validate_profile_name(profile_name)
        account = self.config.get("accounts", {}).get(profile_name)

        if not account:
            raise RuntimeError(f"Для профиля «{profile_name}» не сохранён логин и пароль.")

        login = account.get("login", "").strip()
        password_token = account.get("password_dpapi", "")

        if not login or not password_token:
            raise RuntimeError(f"Для профиля «{profile_name}» не сохранён логин и пароль.")

        return login, unprotect_secret(password_token)

    def delete_account_credentials(self, profile_name):
        profile_name = self.validate_profile_name(profile_name)
        accounts = self.config.setdefault("accounts", {})

        if profile_name in accounts:
            del accounts[profile_name]
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

        return any(part.lower() in IGNORED_DIR_NAMES for part in Path(path).parts)

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
            relative = dst_item.relative_to(destination)
            if self.should_ignore(relative, full_copy):
                continue

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
            relative = src_item.relative_to(source)
            if self.should_ignore(relative, full_copy):
                continue

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
        profile_name = self.validate_profile_name(profile_name)
        loli_dir = self.get_loli_dir()
        profile_dir = self.profile_dir(profile_name)

        if progress:
            progress(f"Сохраняю профиль: {profile_name}")

        self.sync_dirs(loli_dir, profile_dir, full_copy=full_copy, progress=progress)

        self.config["active_profile"] = profile_name
        self.save_config()

        if progress:
            progress(f"Профиль сохранён: {profile_name}")

    def switch_profile(self, profile_name, full_copy=False, progress=None):
        profile_name = self.validate_profile_name(profile_name)
        loli_dir = self.get_loli_dir()
        target_profile_dir = self.profile_dir(profile_name)

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

        return subprocess.Popen([str(path)], shell=False)

    def auto_login(self, profile_name, delay, launcher_process=None, progress=None):
        login, password = self.get_account_credentials(profile_name)
        delay = int(delay)

        if progress:
            progress(f"Автологин: жду {delay} сек., пока откроется окно лаунчера.")
            progress("Не переключай фокус окна до завершения автоввода.")

        time.sleep(delay)

        if launcher_process:
            if WindowsWindow.focus_process_window(launcher_process.pid):
                if progress:
                    progress("Автологин: окно лаунчера получило фокус.")
            elif progress:
                progress("Автологин: не удалось найти окно лаунчера, ввожу в активное окно.")

        previous_clipboard = WindowsClipboard.get_text()

        try:
            if progress:
                progress("Автологин: ввожу логин.")
            WindowsKeyboard.paste_text(login)
            WindowsKeyboard.press_key(WindowsKeyboard.VK_TAB)

            if progress:
                progress("Автологин: ввожу пароль.")
            WindowsKeyboard.paste_text(password)
            WindowsKeyboard.press_key(WindowsKeyboard.VK_RETURN)

            if progress:
                progress("Автологин: данные отправлены.")
        finally:
            if previous_clipboard is None:
                WindowsClipboard.clear()
            else:
                WindowsClipboard.set_text(previous_clipboard)

    def delete_profile(self, profile_name, progress=None):
        profile_name = self.validate_profile_name(profile_name)
        profile_dir = self.profile_dir(profile_name)

        if not profile_dir.exists():
            raise FileNotFoundError(f"Профиль не найден: {profile_name}")

        shutil.rmtree(profile_dir)

        if self.config.get("active_profile") == profile_name:
            self.config["active_profile"] = ""

        self.delete_account_credentials(profile_name)
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
        self.auto_login_var = tk.BooleanVar(value=bool(self.manager.config.get("auto_login", False)))
        self.auto_login_delay_var = tk.StringVar(
            value=str(self.manager.config.get("auto_login_delay", AUTO_LOGIN_DELAY_DEFAULT))
        )
        self.full_copy_var = tk.BooleanVar(value=False)
        self.login_var = tk.StringVar()
        self.password_var = tk.StringVar()
        self.credentials_status_var = tk.StringVar(value="Логин и пароль для профиля не сохранены.")

        self.worker_running = False
        self.buttons = []

        self.setup_window()
        self.create_ui()
        self.refresh_profiles(log=False)

    def setup_window(self):
        self.root.title(APP_TITLE)
        self.root.geometry("900x720")
        self.root.minsize(860, 680)

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
        ).grid(row=0, column=0, sticky="w", padx=(0, 20), pady=(0, 6))

        ttk.Checkbutton(
            options,
            text="Автологин после запуска",
            variable=self.auto_login_var,
        ).grid(row=0, column=1, sticky="w", padx=(0, 12), pady=(0, 6))

        ttk.Label(options, text="Задержка, сек.:").grid(row=0, column=2, sticky="w", padx=(0, 6), pady=(0, 6))

        ttk.Spinbox(
            options,
            from_=AUTO_LOGIN_DELAY_MIN,
            to=AUTO_LOGIN_DELAY_MAX,
            textvariable=self.auto_login_delay_var,
            width=5,
        ).grid(row=0, column=3, sticky="w", padx=(0, 20), pady=(0, 6))

        ttk.Checkbutton(
            options,
            text="Полное копирование",
            variable=self.full_copy_var,
        ).grid(row=0, column=4, sticky="w", pady=(0, 6))

        profile_box = ttk.LabelFrame(outer, text="Профили")
        profile_box.pack(fill="x", pady=(0, 12))

        ttk.Label(profile_box, text="Профиль:").grid(row=0, column=0, padx=8, pady=8, sticky="w")

        self.profile_combo = ttk.Combobox(profile_box, textvariable=self.profile_var)
        self.profile_combo.grid(row=0, column=1, padx=8, pady=8, sticky="ew")
        self.profile_combo.bind("<<ComboboxSelected>>", lambda event: self.load_account_fields())

        profile_box.columnconfigure(1, weight=1)

        credentials = ttk.Frame(profile_box)
        credentials.grid(row=1, column=0, columnspan=2, padx=8, pady=(0, 8), sticky="ew")
        credentials.columnconfigure(1, weight=1)
        credentials.columnconfigure(3, weight=1)

        ttk.Label(credentials, text="Логин:").grid(row=0, column=0, sticky="w", padx=(0, 8))

        ttk.Entry(credentials, textvariable=self.login_var).grid(
            row=0,
            column=1,
            sticky="ew",
            padx=(0, 12),
        )

        ttk.Label(credentials, text="Пароль:").grid(row=0, column=2, sticky="w", padx=(0, 8))

        ttk.Entry(credentials, textvariable=self.password_var, show="*").grid(
            row=0,
            column=3,
            sticky="ew",
            padx=(0, 12),
        )

        credential_buttons = ttk.Frame(credentials)
        credential_buttons.grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))

        self.add_button(credential_buttons, "Сохранить логин/пароль", self.save_account_credentials).pack(
            side="left",
            padx=(0, 8),
        )

        self.add_button(credential_buttons, "Удалить логин/пароль", self.delete_account_credentials).pack(
            side="left",
        )

        ttk.Label(credentials, textvariable=self.credentials_status_var).grid(
            row=1,
            column=2,
            columnspan=2,
            sticky="w",
            pady=(6, 0),
        )

        actions = ttk.Frame(profile_box)
        actions.grid(row=2, column=0, columnspan=2, padx=8, pady=(0, 8), sticky="ew")

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
        self.log("Автологин использует Windows DPAPI и автоввод в активное окно лаунчера.")
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

    def parse_auto_login_delay(self):
        raw_value = self.auto_login_delay_var.get().strip()

        try:
            delay = int(raw_value)
        except ValueError as error:
            raise ValueError("Задержка автологина должна быть числом секунд.") from error

        if delay < AUTO_LOGIN_DELAY_MIN or delay > AUTO_LOGIN_DELAY_MAX:
            raise ValueError(
                f"Задержка автологина должна быть от {AUTO_LOGIN_DELAY_MIN} до {AUTO_LOGIN_DELAY_MAX} секунд."
            )

        return delay

    def apply_settings_values(self, loli_dir, launcher_exe, auto_login_enabled, auto_login_delay):
        if loli_dir:
            self.manager.set_loli_dir(loli_dir)

        if launcher_exe:
            self.manager.set_launcher_exe(launcher_exe)

        self.manager.set_auto_login_options(auto_login_enabled, auto_login_delay)

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
        self.apply_settings_values(
            self.loli_dir_var.get().strip(),
            self.launcher_exe_var.get().strip(),
            self.auto_login_var.get(),
            self.parse_auto_login_delay(),
        )

    def load_account_fields(self):
        profile_name = self.profile_var.get().strip()

        self.password_var.set("")

        if self.manager.has_account_credentials(profile_name):
            self.login_var.set(self.manager.get_account_login(profile_name))
            self.credentials_status_var.set("Пароль сохранён в Windows DPAPI. Для замены введи новый пароль.")
        else:
            self.login_var.set("")
            self.credentials_status_var.set("Логин и пароль для профиля не сохранены.")

    def save_account_credentials(self):
        profile_name = self.profile_var.get().strip()
        login = self.login_var.get()
        password = self.password_var.get()

        try:
            self.manager.save_account_credentials(profile_name, login, password)
            self.password_var.set("")
            self.credentials_status_var.set("Логин и пароль сохранены для этого профиля.")
            self.log(f"Логин и пароль сохранены для профиля: {profile_name}")
        except Exception as error:
            messagebox.showerror("Ошибка", str(error))

    def delete_account_credentials(self):
        profile_name = self.profile_var.get().strip()

        try:
            self.manager.delete_account_credentials(profile_name)
            self.login_var.set("")
            self.password_var.set("")
            self.credentials_status_var.set("Логин и пароль для профиля не сохранены.")
            self.log(f"Логин и пароль удалены для профиля: {profile_name}")
        except Exception as error:
            messagebox.showerror("Ошибка", str(error))

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

        try:
            auto_login_delay = self.parse_auto_login_delay()
        except Exception as error:
            messagebox.showerror("Ошибка", str(error))
            return

        loli_dir = self.loli_dir_var.get().strip()
        launcher_exe = self.launcher_exe_var.get().strip()
        auto_login_enabled = self.auto_login_var.get()
        full_copy = self.full_copy_var.get()
        login = self.login_var.get()
        password = self.password_var.get()

        def action():
            self.apply_settings_values(loli_dir, launcher_exe, auto_login_enabled, auto_login_delay)
            self.manager.save_profile(
                profile_name,
                full_copy=full_copy,
                progress=lambda msg: self.root.after(0, lambda m=msg: self.log(m)),
            )

            if login or password:
                self.manager.save_account_credentials(profile_name, login, password)

        def success():
            self.password_var.set("")
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

        try:
            auto_login_delay = self.parse_auto_login_delay()
        except Exception as error:
            messagebox.showerror("Ошибка", str(error))
            return

        loli_dir = self.loli_dir_var.get().strip()
        launcher_exe = self.launcher_exe_var.get().strip()
        auto_login_enabled = self.auto_login_var.get()
        start_launcher = self.start_launcher_var.get() or auto_login_enabled
        full_copy = self.full_copy_var.get()
        login = self.login_var.get()
        password = self.password_var.get()

        def action():
            self.apply_settings_values(loli_dir, launcher_exe, auto_login_enabled, auto_login_delay)

            if login or password:
                self.manager.save_account_credentials(profile_name, login, password)

            self.manager.switch_profile(
                profile_name,
                full_copy=full_copy,
                progress=lambda msg: self.root.after(0, lambda m=msg: self.log(m)),
            )

            launcher_process = None

            if start_launcher:
                launcher_process = self.manager.start_launcher()

            if auto_login_enabled:
                self.manager.auto_login(
                    profile_name,
                    auto_login_delay,
                    launcher_process=launcher_process,
                    progress=lambda msg: self.root.after(0, lambda m=msg: self.log(m)),
                )

        def success():
            self.password_var.set("")
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

        self.load_account_fields()

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
