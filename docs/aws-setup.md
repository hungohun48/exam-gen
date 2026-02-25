# AWS Setup для deploy.py

Инструкция по настройке AWS для автоматической загрузки ZIP-архивов в S3.

## 1. Создание S3 бакета

### Через консоль

1. Открыть [S3 Console](https://s3.console.aws.amazon.com/s3/)
2. **Create bucket**
3. Имя бакета — уникальное (например `exam-gen-artifacts`)
4. Регион — `us-east-1` (или другой)
5. **Block all public access** — оставить включённым
6. **Create bucket**

### Через CLI

```bash
aws s3 mb s3://exam-gen-artifacts --region us-east-1
```

## 2. Создание IAM пользователя

### Через консоль

1. Открыть [IAM Console](https://console.aws.amazon.com/iam/)
2. **Users → Create user**
3. Имя: `exam-gen-deployer`
4. **Attach policies directly → Create policy** (JSON):

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:PutObject",
                "s3:GetObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::exam-gen-artifacts",
                "arn:aws:s3:::exam-gen-artifacts/*"
            ]
        }
    ]
}
```

> Заменить `exam-gen-artifacts` на имя вашего бакета.

5. Назвать политику: `exam-gen-s3-access`
6. Прикрепить к пользователю
7. **Security credentials → Create access key → Command Line Interface (CLI)**
8. Сохранить **Access Key ID** и **Secret Access Key**

## 3. Настройка AWS CLI

### Установка

```bash
# Windows (winget)
winget install Amazon.AWSCLI

# Linux
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip && sudo ./aws/install
```

### Конфигурация

```bash
aws configure
```

Ввести:
- **AWS Access Key ID**: ключ из шага 2
- **AWS Secret Access Key**: секрет из шага 2
- **Default region name**: `us-east-1` (или ваш регион)
- **Default output format**: `json`

Данные сохраняются в `~/.aws/credentials` (default profile).

## 4. Установка boto3

```bash
pip install boto3
```

Или через requirements.txt проекта:

```bash
pip install -r requirements.txt
```

## 5. Настройка .env

Добавить в `.env`:

```env
S3_BUCKET=exam-gen-artifacts
S3_REGION=us-east-1
```

## 6. Проверка

```bash
# Генерация + загрузка
python deploy.py

# Проверить файлы на S3
aws s3 ls s3://exam-gen-artifacts/
```

Каждый запуск `deploy.py` перезаписывает файлы с одинаковыми именами (boto3 `upload_file` перезаписывает по умолчанию).
