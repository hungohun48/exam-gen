#!/usr/bin/env python3
"""deploy.py — generate + upload to S3."""

import os
import sys
import subprocess
import glob


# ── Load .env (same logic as generate.py) ────────────────────────────
def _load_dotenv():
    """Load .env file from script directory (simple key=value, no shell expansion)."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if not os.path.isfile(env_path):
        return
    with open(env_path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' not in line:
                continue
            key, _, value = line.partition('=')
            key = key.strip()
            value = value.strip().strip("'").strip('"')
            os.environ.setdefault(key, value)


_load_dotenv()

S3_BUCKET = os.environ.get('S3_BUCKET', '')
S3_REGION = os.environ.get('S3_REGION', 'us-east-1')
OUTPUT_DIR = os.environ.get('OUTPUT_DIR', './output')


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # 1. Run generate.py
    gen_script = os.path.join(script_dir, 'generate.py')
    print('[*] Running generate.py ...')
    result = subprocess.run([sys.executable, gen_script], cwd=script_dir)
    if result.returncode != 0:
        print('[!] generate.py failed')
        sys.exit(1)

    # 2. Check S3_BUCKET
    if not S3_BUCKET:
        print('[!] S3_BUCKET not set in .env. Skipping upload.')
        sys.exit(1)

    # 3. Find ZIP files
    output_dir = os.path.join(script_dir, OUTPUT_DIR) if not os.path.isabs(OUTPUT_DIR) else OUTPUT_DIR
    zips = glob.glob(os.path.join(output_dir, '*.zip'))
    if not zips:
        print('[!] No ZIP files found in', output_dir)
        sys.exit(1)

    # 4. Upload via boto3
    import boto3
    print(f'\n[*] Uploading to s3://{S3_BUCKET}/ (region: {S3_REGION})')
    s3 = boto3.client('s3', region_name=S3_REGION)

    for zp in zips:
        key = os.path.basename(zp)
        s3.upload_file(zp, S3_BUCKET, key)
        print(f'  [+] s3://{S3_BUCKET}/{key}')

    print(f'\n[+] Uploaded {len(zips)} file(s)')


if __name__ == '__main__':
    main()
