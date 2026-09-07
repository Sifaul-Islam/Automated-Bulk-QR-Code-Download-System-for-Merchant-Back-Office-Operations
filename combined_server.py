from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import os
import sys
import threading
import uuid
import zipfile
import socket
import time
import re
import io
from datetime import datetime
from socketserver import ThreadingMixIn

try:
    import cgi
except ModuleNotFoundError:
    import types
    from email import policy
    from email.parser import BytesParser
    from io import BytesIO

    class _CompatFieldStorage:
        def __init__(self, fp, headers, environ):
            self._fields = {}
            self._files  = {}
            self._parse(fp, headers)

        def _parse(self, fp, headers):
            content_length = headers.get('Content-Length')
            content_type   = headers.get('Content-Type', '')
            body = fp.read(int(content_length)) if content_length else fp.read()
            if 'multipart/form-data' not in content_type:
                return
            boundary = None
            for part in content_type.split(';'):
                if part.strip().startswith('boundary='):
                    boundary = part.split('=', 1)[1].strip().strip('"')
                    break
            if not boundary:
                return
            message_text = (
                f"Content-Type: {content_type}\r\n\r\n".encode('utf-8') + body
            )
            message = BytesParser(policy=policy.default).parsebytes(message_text)
            for part in message.iter_parts():
                name     = part.get_param('name',     header='content-disposition')
                if not name:
                    continue
                filename = part.get_param('filename', header='content-disposition')
                payload  = part.get_payload(decode=True)
                if filename:
                    self._files[name] = types.SimpleNamespace(
                        filename=filename,
                        file=BytesIO(payload or b'')
                    )
                else:
                    value = payload.decode('utf-8', 'ignore') if isinstance(payload, bytes) else part.get_payload()
                    self._fields[name] = value

        def getvalue(self, key, default=None):
            return self._fields.get(key, default)

        def __getitem__(self, key):
            return self._files[key] if key in self._files else self._fields[key]

    cgi = types.SimpleNamespace(FieldStorage=_CompatFieldStorage)

import pandas as pd

try:
    import qrcode
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib.utils import ImageReader
    from PIL import Image
    import pdfplumber
    HAS_LIBS = True
except ImportError:
    HAS_LIBS = False

BASE_DIR   = os.path.dirname(__file__)
STATIC_DIR = os.path.join(BASE_DIR, 'static')
PORTAL_DIR = os.path.join(BASE_DIR, 'portal')
JOBS_DIR   = os.path.join(BASE_DIR, 'jobs')
os.makedirs(JOBS_DIR, exist_ok=True)

# ============================================
# DEMO CREDENTIALS
# ============================================
DEMO_USERNAME = "sifaul"
DEMO_PASSWORD = "sifaul123"
DEMO_TOKEN    = "DEMO_TOKEN_UPAY_2026"

# ============================================
# LOAD AGENTS
# ============================================
AGENTS_FILE = os.path.join(os.path.dirname(__file__), "agents.xlsx")
agents_df   = None

def load_agents():
    global agents_df
    try:
        agents_df = pd.read_excel(AGENTS_FILE)
        print(f"  Columns found: {list(agents_df.columns)}")

        # Normalize column name — handle any variation
        agents_df.columns = [str(c).strip() for c in agents_df.columns]

        # Find wallet column
        wallet_col = None
        for col in agents_df.columns:
            if "wallet" in col.lower():
                wallet_col = col
                break

        if wallet_col and wallet_col != "Wallet No.":
            agents_df = agents_df.rename(columns={wallet_col: "Wallet No."})

        agents_df["Wallet No."] = agents_df["Wallet No."].astype(str).str.strip()
        agents_df["Wallet No."] = agents_df["Wallet No."].apply(
            lambda w: w[:-2] if w.endswith(".0") else w
        )
        print(f"  Loaded {len(agents_df)} agents")
        print(f"  Sample wallets: {list(agents_df['Wallet No.'].head(3))}")
    except Exception as e:
        print(f"  Could not load agents: {e}")
        agents_df = pd.DataFrame()

load_agents()

# Batch counter for simulating failures
_batch_counter    = 0
_batch_counter_lock = threading.Lock()

FAIL_BATCH_INDEX = 3
MISSING_COUNT    = 5

# ============================================
# ALL JOBS STORE
# ============================================
all_jobs = {}

def log_job(job_id, message, progress=None):
    if job_id not in all_jobs:
        return
    entry = {"message": message}
    if progress is not None:
        entry["progress"] = progress
        all_jobs[job_id]["progress"] = progress
    all_jobs[job_id]["logs"].append(entry)

# ============================================
# QR PDF GENERATION
# ============================================
def generate_qr_pdf(wallet_numbers, missing_wallets=None, merchant_names=None):
    if not HAS_LIBS:
        return None
    if missing_wallets is None:
        missing_wallets = set()

    buffer = io.BytesIO()
    c      = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    for wallet in wallet_numbers:
        if wallet in missing_wallets:
            continue

        # Get DBA name
        dba = "Unknown Merchant"
        w_str     = str(wallet).strip()
        w_no_zero = w_str[1:] if w_str.startswith("0") else w_str
        w_with_zero = "0" + w_str if not w_str.startswith("0") else w_str

        if merchant_names:
            dba = merchant_names.get(w_str) or merchant_names.get(w_no_zero) or merchant_names.get(w_with_zero) or dba

        if dba == "Unknown Merchant" and agents_df is not None and not agents_df.empty:
            match = agents_df[
                (agents_df["Wallet No."] == w_str) |
                (agents_df["Wallet No."] == w_no_zero) |
                (agents_df["Wallet No."] == w_with_zero)
            ]
            if not match.empty:
                dba = str(match.iloc[0]["DBA"])

        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=2
        )
        qr.add_data(wallet)
        qr.make(fit=True)
        qr_img    = qr.make_image(fill_color="black", back_color="white")
        qr_buffer = io.BytesIO()
        qr_img.save(qr_buffer, format="PNG")
        qr_buffer.seek(0)

        # ===== BACKGROUND =====
        c.setFillColorRGB(1, 0.835, 0.016)
        c.rect(0, 0, width, height, fill=1)

        # ===== WHITE CARD =====
        card_w = 17 * cm
        card_h = 24 * cm
        card_x = (width - card_w) / 2
        card_y = (height - card_h) / 2
        c.setFillColorRGB(1, 1, 1)
        c.roundRect(card_x, card_y, card_w, card_h, 0.5 * cm, fill=1)

        # ===== LAYOUT ANCHORS =====
        top_y    = card_y + card_h        # top of card
        center_x = width / 2

        # ===== UPAY LOGO =====
        logo_path = os.path.join(
            os.path.dirname(__file__), 'static', 'images', 'upay_logo.png'
        )
        if os.path.exists(logo_path):
            try:
                pil_img      = Image.open(logo_path)
                img_w, img_h = pil_img.size
                crop_buf     = io.BytesIO()
                crop_buf.seek(0)
                logo_reader  = ImageReader(crop_buf)
            except:
                logo_reader  = ImageReader(logo_path)

            logo_w = 5 * cm
            logo_h = 2.5 * cm
            logo_x = center_x - logo_w / 2
            logo_y = top_y - 5.5 * cm
            c.drawImage(
                logo_reader, logo_x, logo_y,
                width=logo_w, height=logo_h,
                preserveAspectRatio=True,
                mask='auto'
            )

        # ===== DIVIDER AFTER LOGO =====
        divider_y = top_y - 6.0 * cm
        c.setStrokeColorRGB(0.88, 0.88, 0.88)
        c.setLineWidth(0.5)
        c.line(card_x + 1*cm, divider_y, card_x + card_w - 1*cm, divider_y)

        # ===== QR CODE — centered in card =====
        qr_reader = ImageReader(qr_buffer)
        qr_size   = 9 * cm
        qr_x      = center_x - qr_size / 2
        qr_y      = card_y + card_h / 2 - qr_size / 2 + 0.5 * cm
        c.drawImage(qr_reader, qr_x, qr_y, width=qr_size, height=qr_size)

        # ===== WALLET NUMBER — right below QR =====
        w = str(wallet)
        if len(w) == 11:
            formatted = f"{w[0:3]}-{w[3:7]}-{w[7:11]}"
        elif len(w) == 10:
            formatted = f"{w[0:3]}-{w[3:7]}-{w[7:10]}"
        else:
            formatted = w

        wallet_y = qr_y - 0.8 * cm
        c.setFillColorRGB(0.106, 0.227, 0.420)
        c.setFont("Helvetica-Bold", 18)
        c.drawCentredString(center_x, wallet_y, formatted)

        # ===== ACCOUNT LABEL =====
        label_y = wallet_y - 0.6 * cm
        c.setFont("Helvetica", 9)
        c.setFillColorRGB(0.55, 0.55, 0.55)
        c.drawCentredString(center_x, label_y, "Upay Merchant Account Number")

        # ===== DIVIDER BEFORE NAME =====
        bottom_divider_y = label_y - 0.6 * cm
        c.setStrokeColorRGB(0.88, 0.88, 0.88)
        c.line(card_x + 1*cm, bottom_divider_y, card_x + card_w - 1*cm, bottom_divider_y)

        # ===== MERCHANT NAME =====
        name_y = bottom_divider_y - 0.7 * cm
        c.setFillColorRGB(0.106, 0.227, 0.420)
        c.setFont("Helvetica-Bold", 14)
        display_name = dba[:28] + "..." if len(dba) > 28 else dba
        c.drawCentredString(center_x, name_y, display_name)

        # ===== MERCHANT LABEL =====
        c.setFont("Helvetica", 9)
        c.setFillColorRGB(0.55, 0.55, 0.55)
        c.drawCentredString(center_x, name_y - 0.5 * cm, "Merchant Name")

        c.showPage()

    c.save()
    buffer.seek(0)
    return buffer.read()


# ============================================
# MERCHANT SEARCH
# ============================================
def search_merchants(wallet_number, merchant_type, status_filter=None,
                     dba_filter=None, kam_filter=None, persona_filter=None,
                     limit=30, offset=0):
    if agents_df is None or agents_df.empty:
        return 0, []

    try:
        limit  = int(limit)
    except:
        limit  = 30
    try:
        offset = int(offset)
    except:
        offset = 0

    if limit  <= 0: limit  = 30
    if offset <  0: offset = 0

    type_map = {
        "parent":         "Parent",
        "child":          "Child",
        "micro_merchant": "PRA",
        "pra":            "PRA"
    }
    expected_type = type_map.get(merchant_type.lower(), "")

    # Filter by type
    filtered = agents_df[agents_df["Parent/Child"] == expected_type]

    # Filter by wallet
    if wallet_number and str(wallet_number).strip():
        filtered = filtered[
            filtered["Wallet No."].str.contains(str(wallet_number).strip(), na=False)
        ]

    # Filter by status
    if status_filter and "Status" in agents_df.columns:
        filtered = filtered[
            filtered["Status"].astype(str).str.casefold() == str(status_filter).strip().casefold()
        ]
    elif not status_filter:
        if "Status" in agents_df.columns:
            filtered = filtered[filtered["Status"] == "Active"]
        # If no Status column — show all records

    # Filter by DBA
    if dba_filter and str(dba_filter).strip() and "DBA" in agents_df.columns:
        filtered = filtered[
            filtered["DBA"].str.contains(str(dba_filter).strip(), case=False, na=False)
        ]
    print(f"  DBA filter: '{dba_filter}' | Columns: {list(agents_df.columns)} | After DBA filter: {len(filtered)} rows")

 

    # Filter by KAM
    if kam_filter and str(kam_filter).strip() and "KAM" in agents_df.columns:
        filtered = filtered[
            filtered["KAM"].str.contains(str(kam_filter).strip(), case=False, na=False)
        ]

    # Filter by Persona
    if persona_filter and str(persona_filter).strip() and "Persona" in agents_df.columns:
        filtered = filtered[
            filtered["Persona"].astype(str).str.casefold() == str(persona_filter).strip().casefold()
        ]

    total_count = len(filtered)
    page_data   = filtered.iloc[offset: offset + limit]

    results = []
    for _, row in page_data.iterrows():
        results.append({
            "wallet_number":        str(row["Wallet No."]),
            "dba":                  str(row.get("DBA", "—")),
            "parent_merchant_name": str(row.get("Parent Merchant", "—")),
            "merchant_id":          str(row.get("Merchant ID", "—")),
            "email":                str(row.get("Email", "—")),
            "merchant_type":        str(row.get("Merchant Type", "Corporate")),
            "persona":              str(row.get("Persona", "Regular")),
            "kam":                  str(row.get("KAM", "—")),
            "division":             str(row.get("Division", "—")),
            "status":               str(row.get("Status", "Active")),
            "type":                 str(row["Parent/Child"])
        })

    return total_count, results


# ============================================
# AUTOMATION JOB RUNNER
# ============================================
def run_job(job_id, username, password, excel_path, excel_name):
    try:
        import requests
        from excel_reader import load_agents as load_agents_excel, split_by_type, split_into_batches
        from qr_labeler   import label_qr_files

        job_folder   = os.path.join(JOBS_DIR, job_id)
        download_dir = os.path.join(job_folder, "downloads")
        output_dir   = os.path.join(job_folder, "labeled_qr_codes")
        os.makedirs(download_dir, exist_ok=True)
        os.makedirs(output_dir,   exist_ok=True)

        log_job(job_id, "Logging in...", 2)

        if username == DEMO_USERNAME and password == DEMO_PASSWORD:
            token = DEMO_TOKEN
            log_job(job_id, "Login successful!", 5)
        else:
            log_job(job_id, "Invalid credentials", -1)
            all_jobs[job_id]["status"] = "failed"
            return

        log_job(job_id, f"Reading Excel: {excel_name}...", 8)
        agents_list = load_agents_excel(excel_path)
        merchant_names = {}
        for agent in agents_list:
            wallet_key = str(agent["wallet"]).strip()
            if wallet_key.endswith(".0"):
                wallet_key = wallet_key[:-2]
            merchant_name = str(agent["name"]).strip()
            merchant_names[wallet_key] = merchant_name
            if wallet_key.startswith("0"):
                merchant_names[wallet_key[1:]] = merchant_name
            else:
                merchant_names["0" + wallet_key] = merchant_name
        log_job(job_id, f"Total agents: {len(agents_list)}", 10)

        parents, children, pras = split_by_type(agents_list)
        log_job(job_id, f"Parent: {len(parents)} | Child: {len(children)} | PRA: {len(pras)}", 12)

        def batch_count(lst): return max(1, (len(lst) + 29) // 30) if lst else 0
        total_batches     = batch_count(parents) + batch_count(children) + batch_count(pras)
        completed_batches = 0
        all_downloads     = []
        all_failed        = []

        def get_merchant_type(agent_type):
            if agent_type == "PRA":    return "micro_merchant"
            if agent_type == "Parent": return "parent"
            return "child"

        def format_wallet(wallet):
            wallet = str(wallet).strip()
            if wallet.endswith(".0"): wallet = wallet[:-2]
            if len(wallet) == 10 and wallet.isdigit(): wallet = "0" + wallet
            return wallet

        def process_type(agents_list_type, agent_type):
            nonlocal completed_batches
            if not agents_list_type:
                return

            batches       = split_into_batches(agents_list_type, 30)
            merchant_type = get_merchant_type(agent_type)
            total_in_type = len(batches)

            log_job(job_id, f"Processing {len(agents_list_type)} {agent_type} in {total_in_type} batches...")
            all_jobs[job_id]["current_type"]          = agent_type
            all_jobs[job_id]["current_batch"]          = 0
            all_jobs[job_id]["total_batches_in_type"]  = total_in_type

            for batch_index, batch in enumerate(batches):
                all_jobs[job_id]["current_batch"] = batch_index + 1
                log_job(job_id, f"  [{agent_type}] Batch {batch_index+1}/{total_in_type} — {len(batch)} agents...")

                wallets = [format_wallet(a["wallet"]) for a in batch]

                global _batch_counter
                with _batch_counter_lock:
                    b_num = _batch_counter
                    _batch_counter += 1

                if b_num == FAIL_BATCH_INDEX:
                    log_job(job_id, f"  ✗ Batch {batch_index+1} failed (simulated)")
                    all_failed.extend(batch)
                    all_jobs[job_id]["batches_failed"] = all_jobs[job_id].get("batches_failed", 0) + 1
                else:
                    missing = set()
                    if b_num == 0 and len(wallets) > MISSING_COUNT:
                        missing = set(wallets[:MISSING_COUNT])

                    pdf_content = generate_qr_pdf(
                        wallets,
                        missing_wallets=missing,
                        merchant_names=merchant_names
                    )
                    if pdf_content:
                        save_path = os.path.join(download_dir, f"batch_{batch_index+1}_{agent_type}.pdf")
                        with open(save_path, "wb") as f:
                            f.write(pdf_content)
                        log_job(job_id, f"  ✓ Saved batch {batch_index+1} ({len(pdf_content)} bytes)")
                        all_downloads.append({"path": save_path, "batch": batch})
                        all_jobs[job_id]["batches_done"] = all_jobs[job_id].get("batches_done", 0) + 1
                    else:
                        log_job(job_id, f"  ✗ Batch {batch_index+1} failed")
                        all_failed.extend(batch)
                        all_jobs[job_id]["batches_failed"] = all_jobs[job_id].get("batches_failed", 0) + 1

                completed_batches += 1
                progress = 12 + int((completed_batches / max(total_batches, 1)) * 60)
                log_job(job_id, f"  Progress: {progress}%", progress)

        process_type(parents,  "Parent")
        process_type(children, "Child")
        process_type(pras,     "PRA")

        if all_failed:
            failed_df = pd.DataFrame([{
                "Parent/Child": a["type"], "Wallet No.": a["wallet"],
                "DBA": a["name"], "Parent Merchant": a["parent"]
            } for a in all_failed])
            failed_df.to_excel(os.path.join(job_folder, "failed_agents.xlsx"), index=False)
            log_job(job_id, f"  {len(all_failed)} failed agents saved")

        log_job(job_id, "Labeling files...", 75)
        label_qr_files(all_downloads, output_dir)
        log_job(job_id, "Labeling complete!", 80)

        log_job(job_id, "Checking for missing QR codes...", 82)
        all_partial_missing = []

        txt_files = sorted([f for f in os.listdir(output_dir) if f.endswith("_agents.txt")])
        for txt_file in txt_files:
            batch_prefix = txt_file.replace("_agents.txt", "")
            pdf_files    = [f for f in os.listdir(output_dir) if f.startswith(batch_prefix) and f.endswith(".pdf")]
            if not pdf_files:
                continue
            agents_txt = os.path.join(output_dir, txt_file)
            pdf_path   = os.path.join(output_dir, pdf_files[0])
            wallets    = {}
            data_started = False
            with open(agents_txt, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line: continue
                    if line.startswith("---"): data_started = True; continue
                    if not data_started: continue
                    if line.lower().startswith("formatted"): continue
                    parts = line.split()
                    if len(parts) < 2: continue
                    formatted = parts[0]; raw = parts[1]
                    if not re.match(r'^\d[\d-]+\d$', formatted): continue
                    raw_with_zero = ("0" + raw) if len(raw) == 10 and raw.isdigit() else raw
                    wallets[raw] = {"formatted": formatted, "raw": raw, "raw_with_zero": raw_with_zero, "name": " ".join(parts[2:])}

            with pdfplumber.open(pdf_path) as pdf:
                page_count = len(pdf.pages)

            if page_count >= len(wallets):
                log_job(job_id, f"  ✓ {batch_prefix}: {page_count}/{len(wallets)} complete")
                continue

            log_job(job_id, f"  ⚠ {batch_prefix}: {page_count}/{len(wallets)} — checking missing...")
            downloaded_wallets = set()
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if not text: continue
                    all_digits = ""
                    for line in text.strip().split('\n'):
                        stripped = line.strip()
                        if not stripped: continue
                        if not re.search(r'[a-zA-Z]', stripped):
                            all_digits += re.sub(r'[^0-9]', '', stripped)
                    for match in re.findall(r'0\d{10}', all_digits):
                        downloaded_wallets.add(match)
                        downloaded_wallets.add(match[1:])

            missing = []
            for raw, info in wallets.items():
                if raw not in downloaded_wallets and info["raw_with_zero"] not in downloaded_wallets and info["formatted"].replace("-","") not in downloaded_wallets:
                    missing.append(info)
                    all_partial_missing.append(info)

            if missing:
                missing_path = agents_txt.replace("_agents.txt", "_MISSING.txt")
                with open(missing_path, "w", encoding="utf-8") as f:
                    f.write("MISSING QR CODES\n" + "="*50 + "\n")
                    f.write(f"{'Formatted':<20} {'Wallet No.':<15} {'Name'}\n" + "-"*50 + "\n")
                    for info in missing:
                        f.write(f"{info['formatted']:<20} {info['raw_with_zero']:<15} {info['name']}\n")
                log_job(job_id, f"  {len(missing)} missing saved")

        log_job(job_id, "PDF check complete!", 90)
        log_job(job_id, "Creating Excel report...", 92)

        df = pd.read_excel(excel_path)

        def normalize_wallet(w):
            w = str(w).strip().replace("-", "").replace(" ", "")
            if w.endswith(".0"): w = w[:-2]
            if w.startswith("0") and len(w) == 11: w = w[1:]
            return w

        df["Wallet No."] = df["Wallet No."].apply(normalize_wallet)
        all_missing_wallets = set()
        for agent in all_failed:
            all_missing_wallets.add(normalize_wallet(agent["wallet"]))
        for info in all_partial_missing:
            all_missing_wallets.add(normalize_wallet(info["raw"]))
            all_missing_wallets.add(normalize_wallet(info.get("raw_with_zero", "")))

        df["Status"]      = df.apply(lambda row: "Missing" if normalize_wallet(str(row["Wallet No."])) in all_missing_wallets else "Downloaded", axis=1)
        downloaded_df     = df[df["Status"] == "Downloaded"].drop(columns=["Status"])
        missing_report_df = df[df["Status"] == "Missing"].drop(columns=["Status"])

        report_path = os.path.join(job_folder, "QR_Report.xlsx")
        with pd.ExcelWriter(report_path, engine="openpyxl") as writer:
            downloaded_df.to_excel(writer,     sheet_name="Downloaded", index=False)
            missing_report_df.to_excel(writer, sheet_name="Missing",    index=False)

        log_job(job_id, "Report created!", 95)
        log_job(job_id, "Creating ZIP...", 97)

        zip_path = os.path.join(job_folder, f"{excel_name}_results.zip")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(output_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    zf.write(file_path, os.path.relpath(file_path, job_folder))
            zf.write(report_path, "QR_Report.xlsx")
            failed_path = os.path.join(job_folder, "failed_agents.xlsx")
            if os.path.exists(failed_path):
                zf.write(failed_path, "failed_agents.xlsx")

        log_job(job_id, "ZIP created!", 99)

        all_jobs[job_id].update({
            "status":           "done",
            "zip_path":         zip_path,
            "downloaded_count": len(downloaded_df),
            "missing_count":    len(missing_report_df),
            "total_count":      len(df)
        })
        log_job(job_id, "ALL DONE!", 100)

    except Exception as e:
        import traceback
        log_job(job_id, f"ERROR: {str(e)}", -1)
        log_job(job_id, traceback.format_exc())
        all_jobs[job_id]["status"] = "failed"


# ============================================
# COMBINED REQUEST HANDLER
# ============================================
class CombinedHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass

    def serve_file(self, filepath, content_type):
        try:
            with open(filepath, 'rb') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_error(404)

    def send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(body))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.end_headers()

    def do_GET(self):
        path  = self.path.split('?')[0]
        query = self.path.split('?')[1] if '?' in self.path else ''
        params = {}
        for part in query.split('&'):
            if '=' in part:
                k, v = part.split('=', 1)
                import urllib.parse
                params[k] = urllib.parse.unquote_plus(v)

        # ===== PORTAL (demo merchant back office) =====
        if path == '/portal' or path == '/portal/':
            self.serve_file(os.path.join(PORTAL_DIR, 'index.html'), 'text/html')

        elif path == '/portal/portal.css':
            self.serve_file(os.path.join(PORTAL_DIR, 'portal.css'), 'text/css')

        elif path == '/portal/portal.js':
            self.serve_file(os.path.join(PORTAL_DIR, 'portal.js'), 'application/javascript')

        # ===== AUTOMATION DASHBOARD =====
        elif path == '/':
            # Redirect root to demo portal
            self.send_response(302)
            self.send_header('Location', '/portal/')
            self.end_headers()

        elif path == '/dashboard' or path == '/dashboard/':
            # Automation dashboard accessible at /dashboard
            self.serve_file(os.path.join(STATIC_DIR, 'index.html'), 'text/html')

        elif path == '/index.html':
            self.serve_file(os.path.join(STATIC_DIR, 'index.html'), 'text/html')

        elif path == '/progress.html':
            self.serve_file(os.path.join(STATIC_DIR, 'progress.html'), 'text/html')

        elif path == '/results.html':
            self.serve_file(os.path.join(STATIC_DIR, 'results.html'), 'text/html')

        elif path == '/style.css':
            self.serve_file(os.path.join(STATIC_DIR, 'style.css'), 'text/css')

        elif path == '/app.js':
            self.serve_file(os.path.join(STATIC_DIR, 'app.js'), 'application/javascript')

        elif path.startswith('/images/'):
            img_path = os.path.join(STATIC_DIR, path.lstrip('/'))
            ext = path.split('.')[-1].lower()
            ct  = 'image/png' if ext == 'png' else 'image/jpeg' if ext in ['jpg','jpeg'] else 'image/svg+xml'
            self.serve_file(img_path, ct)

        # ===== DASHBOARD API =====
        elif path.startswith('/api/status/'):
            job_id = path.split('/')[-1]
            job    = all_jobs.get(job_id, {})
            self.send_json({
                "status":                job.get("status", "not_found"),
                "progress":              job.get("progress", 0),
                "logs":                  job.get("logs", []),
                "downloaded_count":      job.get("downloaded_count", 0),
                "missing_count":         job.get("missing_count", 0),
                "total_count":           job.get("total_count", 0),
                "excel_name":            job.get("excel_name", ""),
                "current_type":          job.get("current_type", ""),
                "current_batch":         job.get("current_batch", 0),
                "total_batches_in_type": job.get("total_batches_in_type", 0),
                "batches_done":          job.get("batches_done", 0),
                "batches_failed":        job.get("batches_failed", 0)
            })

        elif path == '/api/jobs':
            jobs_list = [{"job_id": jid, "excel_name": j.get("excel_name",""), "status": j.get("status",""),
                          "downloaded_count": j.get("downloaded_count",0), "missing_count": j.get("missing_count",0),
                          "total_count": j.get("total_count",0), "started_at": j.get("started_at","")}
                         for jid, j in all_jobs.items()]
            self.send_json(list(reversed(jobs_list)))

        elif path.startswith('/api/download/'):
            job_id   = path.split('/')[-1]
            job      = all_jobs.get(job_id, {})
            zip_path = job.get("zip_path", "")
            if not zip_path or not os.path.exists(zip_path):
                self.send_error(404)
                return
            with open(zip_path, 'rb') as f:
                content = f.read()
            filename = f"{job.get('excel_name','results')}_results.zip"
            self.send_response(200)
            self.send_header('Content-Type', 'application/zip')
            self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)

        # ===== PORTAL API (fake Upay backend) =====
        elif '/merchant_ops/auth/' in path:
            self.send_json({"error": "Use POST"}, 405)

        elif '/child_merchant/list/' in path or '/parent_merchant/list/' in path or '/micro_merchant/list/' in path:
            if '/child_merchant/list/' in path:   merchant_type = "child"
            elif '/parent_merchant/list/' in path: merchant_type = "parent"
            else:                                   merchant_type = "micro_merchant"

            wallet_number  = params.get('wallet_number', '')
            status_filter  = params.get('status', None)
            dba_filter     = params.get('dba', '')
            kam_filter     = params.get('kam', '')
            persona_filter = params.get('persona', '')
            try:    limit  = int(params.get('limit',  30))
            except: limit  = 30
            try:    offset = int(params.get('offset',  0))
            except: offset = 0

            total_count, results = search_merchants(
                wallet_number, merchant_type, status_filter,
                dba_filter=dba_filter, kam_filter=kam_filter,
                persona_filter=persona_filter, limit=limit, offset=offset
            )
            next_offset = offset + limit if offset + limit < total_count else None
            prev_offset = offset - limit if offset > 0 else None
            self.send_json({
                "code": "MO_MLF200", "message": "Merchant List Found",
                "data": {"count": total_count, "next": next_offset, "previous": prev_offset, "results": results}
            })

        else:
            self.send_error(404)

    def do_POST(self):
        path = self.path.split('?')[0]
        content_length = int(self.headers.get('Content-Length', 0))

        # ===== PORTAL API LOGIN =====
        if '/merchant_ops/auth/web/v1/login/' in path:
            body = self.rfile.read(content_length)
            try:    data = json.loads(body)
            except: data = {}
            username = data.get("username", "")
            password = data.get("password", "")
            if username == DEMO_USERNAME and password == DEMO_PASSWORD:
                self.send_json({"code": "MO_JTC200", "message": "Login Successful", "token": DEMO_TOKEN})
            else:
                self.send_json({"code": "MO_JTC401", "message": "Invalid credentials"}, 401)

        # ===== PORTAL QR DOWNLOAD =====
        elif '/merchant_ops/qr_code/web/v1/bulk/qr-code/download/' in path:
            auth = self.headers.get("authorization", "")
            if DEMO_TOKEN not in auth:
                self.send_json({"error": "Unauthorized"}, 401)
                return
            body = self.rfile.read(content_length)
            try:    data = json.loads(body)
            except: data = {}
            wallets = data.get("merchant_wallets", [])

            global _batch_counter
            with _batch_counter_lock:
                b_num = _batch_counter
                _batch_counter += 1

            if b_num == FAIL_BATCH_INDEX:
                self.send_json({"code": "MO_MBQDF400", "message": "Merchant bulk qr cannot be downloaded due to some reason, please try again"}, 400)
                return

            missing = set()
            if b_num == 0 and len(wallets) > MISSING_COUNT:
                missing = set(wallets[:MISSING_COUNT])

            pdf_content = generate_qr_pdf(wallets, missing_wallets=missing)
            if not pdf_content:
                self.send_json({"error": "Could not generate PDF"}, 500)
                return

            self.send_response(200)
            self.send_header('Content-Type', 'application/pdf')
            self.send_header('Content-Length', len(pdf_content))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(pdf_content)

        # ===== PORTAL QR GENERATE =====
        elif '/merchant_ops/qr_code/web/v1/bulk/qr-code/generate/' in path:
            self.rfile.read(content_length)
            self.send_json({"code": "MO_QGS200", "message": "QR codes generation started"})

        # ===== AUTOMATION DASHBOARD START JOB =====
        elif path == '/api/start':
            content_type = self.headers.get('Content-Type', '')
            if 'multipart/form-data' not in content_type:
                self.send_json({"error": "Invalid content type"}, 400)
                return

            form = cgi.FieldStorage(
                fp=self.rfile, headers=self.headers,
                environ={'REQUEST_METHOD': 'POST', 'CONTENT_TYPE': content_type}
            )

            username   = form.getvalue('username', '')
            password   = form.getvalue('password', '')
            excel_item = form['excel_file']

            if not username or not password or not excel_item:
                self.send_json({"error": "All fields required"}, 400)
                return

            job_id     = str(uuid.uuid4())[:8]
            excel_name = os.path.splitext(excel_item.filename)[0]
            job_folder = os.path.join(JOBS_DIR, job_id)
            os.makedirs(job_folder, exist_ok=True)

            excel_path = os.path.join(job_folder, excel_item.filename)
            with open(excel_path, 'wb') as f:
                f.write(excel_item.file.read())

            all_jobs[job_id] = {
                "status": "running", "excel_name": excel_name,
                "folder": job_folder, "progress": 0, "logs": [],
                "started_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "current_type": "", "current_batch": 0,
                "total_batches_in_type": 0, "batches_done": 0, "batches_failed": 0
            }

            thread = threading.Thread(target=run_job, args=(job_id, username, password, excel_path, excel_name), daemon=True)
            thread.start()
            self.send_json({"job_id": job_id})

        else:
            self.send_error(404)


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 5000))

    # Generate demo data if not exists
    if not os.path.exists(AGENTS_FILE):
        print("Generating demo data...")
        try:
            import demo_data
        except:
            pass
        load_agents()

    server = ThreadedHTTPServer(('0.0.0.0', PORT), CombinedHandler)

    print(f"\n{'='*50}")
    print(f"  Upay Demo System running on port {PORT}")
    print(f"  Automation Dashboard: http://localhost:{PORT}/")
    print(f"  Demo Portal:          http://localhost:{PORT}/portal/")
    print(f"  Demo Login:           sifaul / sifaul123")
    print(f"{'='*50}\n")

    server.serve_forever()