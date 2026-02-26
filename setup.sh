#!/usr/bin/env bash
set -euo pipefail

# ============================================================
#  exam-gen — bootstrap script for fresh Ubuntu
#  Run once on a clean server to install everything needed.
# ============================================================

REPO_URL="https://github.com/hungohun48/exam-gen.git"
REPO_DIR="exam-gen"

green()  { printf '\033[0;32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[0;33m%s\033[0m\n' "$*"; }
red()    { printf '\033[0;31m%s\033[0m\n' "$*"; }

# ── 1. System packages ──────────────────────────────────────
green "[1/6] Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-pip python3-venv git libreoffice-writer awscli
green "      Done."

# ── 2. Clone repo (if not already inside one) ───────────────
green "[2/6] Checking repository..."
if [ -f "generate.py" ]; then
    yellow "      Already inside exam-gen repo, skipping clone."
elif [ -d "$REPO_DIR" ]; then
    yellow "      Directory $REPO_DIR exists, entering it."
    cd "$REPO_DIR"
else
    git clone "$REPO_URL"
    cd "$REPO_DIR"
    green "      Cloned into $REPO_DIR."
fi

# ── 3. Python packages ──────────────────────────────────────
green "[3/6] Installing Python packages..."
pip3 install --quiet -r requirements.txt
green "      Done."

# ── 4. .env setup ───────────────────────────────────────────
green "[4/6] Configuring .env..."

if [ -f ".env" ]; then
    yellow "      .env already exists, keeping it."
else
    cp .env.example .env
    green "      Created .env from .env.example."
fi

# Helper: read a value, update .env
ask_var() {
    local var_name="$1"
    local prompt_text="$2"
    local current
    current=$(grep -oP "^${var_name}=\K.*" .env 2>/dev/null || true)

    if [ -n "$current" ] && [ "$current" != "your-api-key-here" ] \
       && [ "$current" != "your-bucket-name" ] \
       && [[ "$current" != https://xxx.* ]]; then
        yellow "      $var_name is already set ($current), skipping."
        return
    fi

    read -rp "      $prompt_text: " value
    if [ -z "$value" ]; then
        yellow "      Skipped (empty)."
        return
    fi

    if grep -q "^${var_name}=" .env; then
        sed -i "s|^${var_name}=.*|${var_name}=${value}|" .env
    else
        echo "${var_name}=${value}" >> .env
    fi
    green "      $var_name set."
}

ask_var "LAMBDA_URL" "Lambda Function URL"
ask_var "API_KEY"    "API Key (X-Api-Key header)"
ask_var "S3_BUCKET"  "S3 bucket name"
ask_var "S3_REGION"  "S3 region (e.g. us-east-1)"

# ── 5. AWS CLI configure (if not already done) ──────────────
green "[5/6] Checking AWS credentials..."

if [ -f "$HOME/.aws/credentials" ]; then
    yellow "      ~/.aws/credentials exists, skipping aws configure."
else
    yellow "      No AWS credentials found. Running 'aws configure'..."
    aws configure
fi

# ── 6. Done ─────────────────────────────────────────────────
green "[6/6] Setup complete!"
echo ""
echo "  Next steps:"
echo "    1. Review .env            — nano .env"
echo "    2. Add variant folders    — cp -r /path/to/variants ./variants/"
echo "    3. Generate artifacts     — python3 generate.py"
echo "    4. Generate + upload S3   — python3 deploy.py"
echo ""
