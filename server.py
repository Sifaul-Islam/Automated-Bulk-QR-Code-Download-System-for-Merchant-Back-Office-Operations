from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import os
import sys
import threading
import uuid
import zipfile
import socket
import time
from datetime import datetime

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

JOBS_DIR   = os.path.join(os.path.dirname(__file__), 'jobs')
STATIC_DIR = os.path.join(os.path.dirname(__file__), 'static')
os.makedirs(JOBS_DIR, exist_ok=True)

# ============================================
# POINT TO  API INSTEAD OF REAL UPAY API
# ============================================
API_BASE    = "http://localhost:8000/merchant_ops"
LOGIN_URL        = f"{API_BASE}/auth/web/v1/login/"
DOWNLOAD_URL     = f"{API_BASE}/qr_code/web/v1/bulk/qr-code/download/"
GENERATE_URL     = f"{API_BASE}/qr_code/web/v1/bulk/qr-code/generate/"
PRA_DOWNLOAD_URL = f"{API_BASE}/qr_code/web/v1/bulk/qr-code/download/"

all_jobs = {}


def log_job(job_id, message, progress=None):
    if job_id not in all_jobs:
        return
    entry = {"message": message}
    if progress is not None:
        entry["progress"] = progress
        all_jobs[job_id]["progress"] = progress
    all_jobs[job_id]["logs"].append(entry)


def run_job(job_id, username, password, excel_path, excel_name):
    try:
        import pandas as pd
        import requests
        import re
        import pdfplumber

        sys.path.insert(0, os.path.dirname(__file__))
        from excel_reader import load_agents, split_by_type, split_into_batches
        from qr_labeler   import label_qr_files

        job_folder   = os.path.join(JOBS_DIR, job_id)
        download_dir = os.path.join(job_folder, "downloads")
        output_dir   = os.path.join(job_folder, "labeled_qr_codes")
        os.makedirs(download_dir, exist_ok=True)
        os.makedirs(output_dir,   exist_ok=True)

        all_jobs[job_id]["folder"] = job_folder

        # Login to API
        log_job(job_id, "Logging in to Upay portal...", 2)
        response = requests.post(LOGIN_URL, json={
            "username": username,
            "password": password,
            "portal":   "merchant_back_ops"
        })

        if response.status_code != 200:
            raise Exception(f"Login failed: {response.text[:200]}")

        token = response.json().get("token")
        if not token:
            raise Exception("Token not found in response")

        log_job(job_id, "Login successful!", 5)

        session = requests.Session()
        session.headers.update({
            "authorization":   f"MERCHANT {token}",
            "accept":          "application/json, text/plain, */*",
            "accept-language": "en",
            "origin":          "https://merchantops.upaysystem.com",
            "referer":         "https://merchantops.upaysystem.com/",
            "user-agent":      "Mozilla/5.0"
        })

        log_job(job_id, f"Reading Excel file: {excel_name}...", 8)
        agents = load_agents(excel_path)
        log_job(job_id, f"Total agents loaded: {len(agents)}", 10)

        parents, children, pras = split_by_type(agents)
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

        def process_type(agents_list, agent_type):
            nonlocal completed_batches
            if not agents_list:
                return

            batches       = split_into_batches(agents_list, 30)
            merchant_type = get_merchant_type(agent_type)
            total_in_type = len(batches)

            log_job(job_id, f"Processing {len(agents_list)} {agent_type} merchants in {total_in_type} batches...")
            all_jobs[job_id]["current_type"]         = agent_type
            all_jobs[job_id]["current_batch"]         = 0
            all_jobs[job_id]["total_batches_in_type"] = total_in_type

            for batch_index, batch in enumerate(batches):
                all_jobs[job_id]["current_batch"] = batch_index + 1
                log_job(job_id, f"  [{agent_type}] Batch {batch_index + 1}/{total_in_type} — {len(batch)} agents...")

                wallets = [format_wallet(a["wallet"]) for a in batch]

                # PRA uses different payload
                if agent_type == "PRA":
                    actual_url = PRA_DOWNLOAD_URL
                    payload    = {
                        "merchant_wallets": wallets,
                        "regulation_type":  "bangla_qr",
                        "pdf_type":         ""
                    }
                else:
                    actual_url = DOWNLOAD_URL
                    payload    = {
                        "merchant_wallets": wallets,
                        "merchant_type":    merchant_type,
                        "regulation_type":  "bangla_qr",
                        "pdf_type":         ""
                    }

                response = session.post(actual_url, json=payload, timeout=300)

                if response.status_code == 400:
                    code = response.json().get("code", "")
                    if code == "MO_MBQDF400":
                        log_job(job_id, f"  Generating QR codes first...")

                        if agent_type == "PRA":
                            gen_payload = {
                                "merchant_wallets": wallets,
                                "regulation_type":  "bangla_qr"
                            }
                        else:
                            gen_payload = {
                                "merchant_wallets": wallets,
                                "merchant_type":    merchant_type,
                                "regulation_type":  "bangla_qr"
                            }

                        session.post(GENERATE_URL, json=gen_payload, timeout=120)
                        log_job(job_id, f"  Waiting 10 seconds for generation...")
                        time.sleep(10)
                        response = session.post(actual_url, json=payload, timeout=300)

                        if response.status_code == 400:
                            log_job(job_id, f"  Waiting 20 more seconds...")
                            time.sleep(20)
                            response = session.post(actual_url, json=payload, timeout=300)

                if response.status_code == 200 and (
                    "pdf" in response.headers.get("Content-Type", "") or
                    response.content[:4] == b"%PDF"
                ):
                    save_path = os.path.join(download_dir, f"batch_{batch_index + 1}_{agent_type}.pdf")
                    with open(save_path, "wb") as f:
                        f.write(response.content)
                    log_job(job_id, f"  [OK] Saved batch {batch_index + 1} ({len(response.content)} bytes)")
                    all_downloads.append({"path": save_path, "batch": batch})
                    all_jobs[job_id]["batches_done"] = all_jobs[job_id].get("batches_done", 0) + 1
                else:
                    content_type = response.headers.get("Content-Type", "unknown")
                    try:
                        resp_text = response.text[:300]
                    except:
                        resp_text = "Could not read response"
                    log_job(job_id, f"  [FAILED] Batch {batch_index + 1} failed — {response.status_code} | {resp_text}")
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
                "Parent/Child":    a["type"],
                "Wallet No.":      a["wallet"],
                "DBA":             a["name"],
                "Parent Merchant": a["parent"]
            } for a in all_failed])
            failed_df.to_excel(os.path.join(job_folder, "failed_agents.xlsx"), index=False)
            log_job(job_id, f"  {len(all_failed)} failed agents saved")

        log_job(job_id, "Labeling QR code files...", 75)
        label_qr_files(all_downloads, output_dir)
        log_job(job_id, "Labeling complete!", 80)

        log_job(job_id, "Checking PDFs for missing QR codes...", 82)
        all_partial_missing = []

        txt_files = sorted([f for f in os.listdir(output_dir) if f.endswith("_agents.txt")])
        for txt_file in txt_files:
            batch_prefix = txt_file.replace("_agents.txt", "")
            pdf_files    = [f for f in os.listdir(output_dir) if f.startswith(batch_prefix) and f.endswith(".pdf")]
            if not pdf_files:
                continue

            agents_txt = os.path.join(output_dir, txt_file)
            pdf_path   = os.path.join(output_dir, pdf_files[0])

            wallets      = {}
            data_started = False
            with open(agents_txt, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line: continue
                    if line.startswith("---"):
                        data_started = True
                        continue
                    if not data_started: continue
                    if line.lower().startswith("formatted"): continue
                    parts = line.split()
                    if len(parts) < 2: continue
                    formatted     = parts[0]
                    raw           = parts[1]
                    if not __import__('re').match(r'^\d[\d-]+\d$', formatted): continue
                    raw_with_zero = ("0" + raw) if len(raw) == 10 and raw.isdigit() else raw
                    wallets[raw]  = {
                        "formatted":     formatted,
                        "raw":           raw,
                        "raw_with_zero": raw_with_zero,
                        "name":          " ".join(parts[2:])
                    }

            with pdfplumber.open(pdf_path) as pdf:
                page_count = len(pdf.pages)

            agent_count = len(wallets)
            if page_count >= agent_count:
                log_job(job_id, f"  [OK] {batch_prefix}: {page_count}/{agent_count} complete")
                continue

            log_job(job_id, f"  [WARNING] {batch_prefix}: {page_count}/{agent_count} — checking missing...")

            downloaded_wallets = set()
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if not text: continue
                    all_digits = ""
                    for line in text.strip().split('\n'):
                        stripped = line.strip()
                        if not stripped: continue
                        if not __import__('re').search(r'[a-zA-Z]', stripped):
                            all_digits += __import__('re').sub(r'[^0-9]', '', stripped)
                    for match in __import__('re').findall(r'0\d{10}', all_digits):
                        downloaded_wallets.add(match)
                        downloaded_wallets.add(match[1:])
                    for match in __import__('re').findall(r'1\d{9}', all_digits):
                        downloaded_wallets.add(match)
                        downloaded_wallets.add("0" + match)

            missing = []
            for raw, info in wallets.items():
                if raw not in downloaded_wallets and \
                   info["raw_with_zero"] not in downloaded_wallets and \
                   info["formatted"].replace("-","") not in downloaded_wallets:
                    missing.append(info)
                    all_partial_missing.append(info)

            if missing:
                missing_path = agents_txt.replace("_agents.txt", "_MISSING.txt")
                with open(missing_path, "w", encoding="utf-8") as f:
                    f.write("MISSING QR CODES\n")
                    f.write("="*50 + "\n")
                    f.write(f"{'Formatted':<20} {'Wallet No.':<15} {'Name'}\n")
                    f.write("-"*50 + "\n")
                    for info in missing:
                        f.write(f"{info['formatted']:<20} {info['raw_with_zero']:<15} {info['name']}\n")
                log_job(job_id, f"  {len(missing)} missing saved to MISSING.txt")

        log_job(job_id, "PDF check complete!", 90)

        log_job(job_id, "Creating Excel report...", 92)
        df = pd.read_excel(excel_path)

        def clean_wallet(w):
            w = str(w).strip().replace("-", "").replace(" ", "")
            if w.endswith(".0"): w = w[:-2]
            if w.startswith("0") and len(w) == 11: w = w[1:]
            return w

        df["Wallet No."] = df["Wallet No."].apply(clean_wallet)

        def normalize_wallet(w):
            w = str(w).strip().replace("-", "").replace(" ", "")
            if w.startswith("0") and len(w) == 11:
                w = w[1:]
            return w

        all_missing_wallets = set()
        for agent in all_failed:
            all_missing_wallets.add(normalize_wallet(agent["wallet"]))
        for info in all_partial_missing:
            all_missing_wallets.add(normalize_wallet(info["raw"]))
            all_missing_wallets.add(normalize_wallet(info["raw_with_zero"]))
            all_missing_wallets.add(normalize_wallet(info["formatted"]))

        df["Status"]      = df.apply(
            lambda row: "Missing" if str(row["Wallet No."]).strip() in all_missing_wallets else "Downloaded",
            axis=1
        )
        downloaded_df     = df[df["Status"] == "Downloaded"].drop(columns=["Status"])
        missing_report_df = df[df["Status"] == "Missing"].drop(columns=["Status"])

        report_path = os.path.join(job_folder, "QR_Report.xlsx")
        with pd.ExcelWriter(report_path, engine="openpyxl") as writer:
            downloaded_df.to_excel(writer,     sheet_name="Downloaded", index=False)
            missing_report_df.to_excel(writer, sheet_name="Missing",    index=False)

        log_job(job_id, "Report created!", 95)

        log_job(job_id, "Creating ZIP file...", 97)
        zip_path = os.path.join(job_folder, f"{excel_name}_results.zip")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(output_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname   = os.path.relpath(file_path, job_folder)
                    zf.write(file_path, arcname)
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


class Handler(BaseHTTPRequestHandler):

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
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split('?')[0]

        if path == '/' or path == '/index.html':
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
            if path.endswith('.png'):
                self.serve_file(img_path, 'image/png')
            elif path.endswith('.jpg') or path.endswith('.jpeg'):
                self.serve_file(img_path, 'image/jpeg')
            elif path.endswith('.svg'):
                self.serve_file(img_path, 'image/svg+xml')    
            else:
                self.send_error(404)

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
            jobs_list = []
            for jid, job in all_jobs.items():
                jobs_list.append({
                    "job_id":           jid,
                    "excel_name":       job.get("excel_name", ""),
                    "status":           job.get("status", ""),
                    "downloaded_count": job.get("downloaded_count", 0),
                    "missing_count":    job.get("missing_count", 0),
                    "total_count":      job.get("total_count", 0),
                    "started_at":       job.get("started_at", "")
                })
            jobs_list.reverse()
            self.send_json(jobs_list)

        elif path.startswith('/api/download/'):
            job_id   = path.split('/')[-1]
            job      = all_jobs.get(job_id, {})
            zip_path = job.get("zip_path", "")

            if not zip_path or not os.path.exists(zip_path):
                self.send_error(404)
                return

            with open(zip_path, 'rb') as f:
                content = f.read()

            filename = f"{job.get('excel_name', 'results')}_results.zip"
            self.send_response(200)
            self.send_header('Content-Type', 'application/zip')
            self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)

        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == '/api/start':
            content_type = self.headers.get('Content-Type', '')
            if 'multipart/form-data' not in content_type:
                self.send_json({"error": "Invalid content type"}, 400)
                return

            form = cgi.FieldStorage(
                fp=self.rfile,
                headers=self.headers,
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
                "status":                "running",
                "excel_name":            excel_name,
                "folder":                job_folder,
                "progress":              0,
                "logs":                  [],
                "started_at":            datetime.now().strftime("%Y-%m-%d %H:%M"),
                "current_type":          "",
                "current_batch":         0,
                "total_batches_in_type": 0,
                "batches_done":          0,
                "batches_failed":        0
            }

            thread = threading.Thread(
                target=run_job,
                args=(job_id, username, password, excel_path, excel_name)
            )
            thread.daemon = True
            thread.start()

            self.send_json({"job_id": job_id})

        else:
            self.send_error(404)


if __name__ == "__main__":
    PORT     = 5000
    hostname = socket.gethostname()
    try:
        local_ip = socket.gethostbyname(hostname)
    except:
        local_ip = "localhost"

    server = HTTPServer(('0.0.0.0', PORT), Handler)

    print(f"\n{'='*50}")
    print(f"  UPAY QR Dashboard running!")
    print(f"  Local:   http://localhost:{PORT}")
    print(f"  Network: http://{local_ip}:{PORT}")
    print(f"  Press Ctrl+C to stop")
    print(f"{'='*50}\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
