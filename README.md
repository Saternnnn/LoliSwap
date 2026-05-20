# LoliSwap GUI

**English** | [Русская версия](#русская-версия)

LoliSwap GUI is a Windows desktop application for switching between local Loliland Launcher profiles.

The application provides a graphical interface built with Python `tkinter`. It does not store passwords, does not perform automatic login, and does not bypass authentication. It only saves and restores local launcher profile files for user-owned accounts.

## Features

- Graphical interface for profile management
- Local Loliland Launcher folder selection
- Launcher executable selection
- Named profile saving
- Switching between saved profiles
- Optional launcher start after profile switching
- Saved profile deletion
- Local profile folder opening
- Standalone Windows `.exe` build support with PyInstaller

## Interface overview

| UI element | Purpose |
|---|---|
| **Loliland folder** | Path to the local Loliland Launcher data folder |
| **Launcher EXE** | Path to the launcher executable file |
| **Start launcher after switching** | Starts the launcher after profile switching |
| **Full copy** | Copies all files, including cache, logs, and temporary folders |
| **Profile** | Profile name, for example `main` or `alt` |
| **Find folder** | Searches for possible Loliland folders |
| **Save profile** | Saves the current launcher state as a profile |
| **Switch** | Restores the selected profile |
| **Delete profile** | Deletes the saved local copy of a profile |
| **Refresh list** | Reloads the saved profile list |
| **Open profiles folder** | Opens the local storage folder |
| **Log** | Shows operation progress and errors |

## Security notice

Saved profiles are stored locally in:

```text
C:\Users\YOUR_USER\Documents\LoliSwap
```

This folder may contain local session data. It is intentionally kept outside the project repository.

The following data should not be published:

```text
Documents\LoliSwap
profiles
config.json
*.session
*.token
*.cookie
*.cookies
*.sqlite
*.db
```

## Project structure

```text
LoliSwap
├── loliswap_app.py
├── build_exe.bat
├── requirements-dev.txt
├── .gitignore
├── LICENSE
├── SECURITY.md
└── README.md
```

## Requirements

For running from source:

- Windows
- Python 3.10 or newer

Runtime dependencies are not required. The application uses Python standard library modules, including:

- `tkinter`
- `pathlib`
- `json`
- `shutil`
- `subprocess`
- `threading`

For building a standalone executable, PyInstaller is used as a development dependency.

## Run from source

```bash
python loliswap_app.py
```

Alternative command for systems using the Python launcher:

```bash
py loliswap_app.py
```

## Build Windows executable

Using the included batch file:

```bash
build_exe.bat
```

Manual build:

```bash
python -m pip install --upgrade -r requirements-dev.txt
python -m PyInstaller --onefile --windowed --name LoliSwap loliswap_app.py
```

The generated executable will be located in:

```text
dist\LoliSwap.exe
```

## Usage

### 1. Start the application

Run the source file:

```bash
python loliswap_app.py
```

or start the compiled executable:

```text
LoliSwap.exe
```

### 2. Select the Loliland folder

Use **Find folder** to search for possible Loliland Launcher folders.

If exactly one matching folder is found, it will be selected automatically. If several folders are found, the correct folder can be selected manually.

### 3. Select the launcher executable

Use **Select .exe** to choose the Loliland Launcher executable.

This is required only when automatic launcher start after profile switching is needed.

### 4. Save a profile

1. Open Loliland Launcher.
2. Log in to an account.
3. Fully close Loliland Launcher.
4. Enter a profile name, for example:

```text
main
```

5. Click **Save profile**.

### 5. Save another profile

1. Open Loliland Launcher again.
2. Log in to another account.
3. Fully close the launcher.
4. Enter another profile name, for example:

```text
alt
```

5. Click **Save profile**.

### 6. Switch profiles

Select a saved profile and click **Switch**.

If **Start launcher after switching** is enabled, the selected launcher executable will be started after the profile switch is complete.

## Full copy mode

By default, LoliSwap skips temporary and heavy folders such as:

```text
cache
logs
temp
crash-reports
downloads
updates
```

This keeps profile copies smaller and improves switching speed.

Enable **Full copy** only when an exact folder copy is required.

## Local data storage

Saved profiles are stored outside the repository:

```text
C:\Users\YOUR_USER\Documents\LoliSwap
```

Example local structure:

```text
LoliSwap
├── config.json
└── profiles
    ├── main
    └── alt
```

## Troubleshooting

### Loliland folder is not found

Select the folder manually with the folder selection button.

### Launcher asks for a password after switching

The launcher may store part of the session elsewhere or validate the session server-side. LoliSwap does not bypass authentication and cannot guarantee passwordless switching.

### Access denied or file locked

The launcher may still be running. Close Loliland Launcher completely and check for remaining launcher processes in Task Manager.

### Compiled EXE does not start

First test the source version:

```bash
python loliswap_app.py
```

If the source version works, rebuild the executable:

```bash
python -m PyInstaller --onefile --windowed --name LoliSwap loliswap_app.py
```

## Disclaimer

LoliSwap GUI is not affiliated with Loliland. The application is intended only for personal local profile management with user-owned accounts.

---

# Русская версия

[English version](#loliswap-gui)

LoliSwap GUI — это Windows-приложение с графическим интерфейсом для переключения между локальными профилями Loliland Launcher.

Приложение написано на Python и использует стандартный модуль `tkinter` для интерфейса. Оно не хранит пароли, не выполняет автоматический вход и не обходит авторизацию. Программа только сохраняет и восстанавливает локальные файлы профиля лаунчера для аккаунтов, которыми владеет пользователь.

## Возможности

- Графический интерфейс для управления профилями
- Выбор локальной папки Loliland Launcher
- Выбор исполняемого файла лаунчера
- Сохранение профилей с отдельными именами
- Переключение между сохранёнными профилями
- Опциональный запуск лаунчера после переключения
- Удаление сохранённых профилей
- Открытие локальной папки профилей
- Сборка самостоятельного Windows `.exe` через PyInstaller

## Обзор интерфейса

| Элемент интерфейса | Назначение |
|---|---|
| **Папка Loliland** | Путь к локальной папке данных Loliland Launcher |
| **Файл лаунчера** | Путь к `.exe` файлу лаунчера |
| **Запускать лаунчер после переключения** | Запускает лаунчер после смены профиля |
| **Полное копирование** | Копирует все файлы, включая cache, logs и временные папки |
| **Профиль** | Имя профиля, например `main` или `alt` |
| **Найти папку** | Ищет возможные папки Loliland |
| **Сохранить профиль** | Сохраняет текущее состояние лаунчера |
| **Переключиться** | Восстанавливает выбранный профиль |
| **Удалить профиль** | Удаляет локальную копию сохранённого профиля |
| **Обновить список** | Обновляет список сохранённых профилей |
| **Открыть папку профилей** | Открывает папку, где лежат сохранённые профили |
| **Лог** | Показывает ход операции и ошибки |

## Предупреждение по безопасности

Сохранённые профили хранятся локально:

```text
C:\Users\ИМЯ_ПОЛЬЗОВАТЕЛЯ\Documents\LoliSwap
```

Эта папка может содержать локальные данные сессии. Она специально хранится вне папки проекта.

Следующие данные не должны публиковаться:

```text
Documents\LoliSwap
profiles
config.json
*.session
*.token
*.cookie
*.cookies
*.sqlite
*.db
```

## Структура проекта

```text
LoliSwap
├── loliswap_app.py
├── build_exe.bat
├── requirements-dev.txt
├── .gitignore
├── LICENSE
├── SECURITY.md
└── README.md
```

## Требования

Для запуска из исходного кода:

- Windows
- Python 3.10 или новее

Для обычного запуска дополнительные зависимости не нужны. Программа использует стандартные модули Python:

- `tkinter`
- `pathlib`
- `json`
- `shutil`
- `subprocess`
- `threading`

Для сборки самостоятельного исполняемого файла используется PyInstaller как dev-зависимость.

## Запуск из исходного кода

```bash
python loliswap_app.py
```

Альтернативная команда для систем с Python Launcher:

```bash
py loliswap_app.py
```

## Сборка Windows EXE

Через готовый batch-файл:

```bash
build_exe.bat
```

Ручная сборка:

```bash
python -m pip install --upgrade -r requirements-dev.txt
python -m PyInstaller --onefile --windowed --name LoliSwap loliswap_app.py
```

Готовый исполняемый файл будет создан здесь:

```text
dist\LoliSwap.exe
```

## Использование

### 1. Запуск приложения

Запуск исходного файла:

```bash
python loliswap_app.py
```

или запуск собранного файла:

```text
LoliSwap.exe
```

### 2. Выбор папки Loliland

Кнопка **Найти папку** запускает поиск возможных папок Loliland Launcher.

Если найдена только одна подходящая папка, она выбирается автоматически. Если найдено несколько папок, корректную папку можно выбрать вручную.

### 3. Выбор исполняемого файла лаунчера

Кнопка **Выбрать .exe** используется для выбора исполняемого файла Loliland Launcher.

Это требуется только для автоматического запуска лаунчера после переключения профиля.

### 4. Сохранение профиля

1. Открыть Loliland Launcher.
2. Выполнить вход в аккаунт.
3. Полностью закрыть Loliland Launcher.
4. Ввести имя профиля, например:

```text
main
```

5. Нажать **Сохранить профиль**.

### 5. Сохранение второго профиля

1. Снова открыть Loliland Launcher.
2. Выполнить вход в другой аккаунт.
3. Полностью закрыть лаунчер.
4. Ввести другое имя профиля, например:

```text
alt
```

5. Нажать **Сохранить профиль**.

### 6. Переключение профилей

Выбрать сохранённый профиль и нажать **Переключиться**.

Если включена опция **Запускать лаунчер после переключения**, выбранный исполняемый файл лаунчера будет запущен после завершения переключения.

## Режим полного копирования

По умолчанию LoliSwap пропускает временные и тяжёлые папки:

```text
cache
logs
temp
crash-reports
downloads
updates
```

Это уменьшает размер сохранённых профилей и ускоряет переключение.

Опцию **Полное копирование** следует включать только тогда, когда требуется точная копия всей папки.

## Локальное хранение данных

Сохранённые профили хранятся вне репозитория:

```text
C:\Users\ИМЯ_ПОЛЬЗОВАТЕЛЯ\Documents\LoliSwap
```

Пример локальной структуры:

```text
LoliSwap
├── config.json
└── profiles
    ├── main
    └── alt
```

## Возможные проблемы

### Папка Loliland не найдена

Папку можно выбрать вручную через кнопку выбора папки.

### После переключения лаунчер запрашивает пароль

Лаунчер может хранить часть сессии в другом месте или проверять сессию на сервере. LoliSwap не обходит авторизацию и не гарантирует переключение без повторного ввода пароля.

### Ошибка доступа или файл заблокирован

Лаунчер может оставаться запущенным. Необходимо полностью закрыть Loliland Launcher и проверить оставшиеся процессы в диспетчере задач.

### Собранный EXE не запускается

Сначала следует проверить запуск исходной версии:

```bash
python loliswap_app.py
```

Если исходная версия работает, исполняемый файл можно пересобрать:

```bash
python -m PyInstaller --onefile --windowed --name LoliSwap loliswap_app.py
```

## Отказ от ответственности

LoliSwap GUI не связан с Loliland. Приложение предназначено только для локального управления профилями аккаунтов, которыми владеет пользователь.
