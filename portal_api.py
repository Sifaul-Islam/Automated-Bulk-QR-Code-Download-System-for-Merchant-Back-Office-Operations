from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import os
import io
import pandas as pd
import threading
from urllib.parse import parse_qs
from PIL import Image

try:
    import qrcode
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib.utils import ImageReader
    HAS_LIBS = True
except ImportError:
    HAS_LIBS = False
    print("Missing libraries! Run: pip install qrcode reportlab")

# User CREDENTIALS
USERNAME = "sifaul"
PASSWORD = "sifaul123"
TOKEN    = "sifaul_TOKEN_UPAY_2026"

# Load USER merchant data
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


def generate_qr_pdf(wallet_numbers, missing_wallets=None):
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
        if agents_df is not None and not agents_df.empty:
            w_str       = str(wallet).strip()
            w_no_zero   = w_str[1:] if w_str.startswith("0") else w_str
            w_with_zero = "0" + w_str if not w_str.startswith("0") else w_str
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

class PortalAPIHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass

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
        path = self.path.split('?')[0]
        query = self.path.split('?')[1] if '?' in self.path else ''

        params = {key: values[0] for key, values in parse_qs(query).items()}

        # ============================================
        # MERCHANT SEARCH API
        # ============================================
        if '/child_merchant/list/' in path or \
           '/parent_merchant/list/' in path or \
           '/micro_merchant/list/' in path:

            if '/child_merchant/list/' in path:
                merchant_type = "child"
            elif '/parent_merchant/list/' in path:
                merchant_type = "parent"
            else:
                merchant_type = "micro_merchant"

            wallet_number  = params.get('wallet_number', '')
            status_filter  = params.get('status', None)
            dba_filter     = params.get('dba', '')
            kam_filter     = params.get('kam', '')
            persona_filter = params.get('persona', '')
            limit  = int(params.get('limit',  30)) if str(params.get('limit',  '30')).strip() else 30
            offset = int(params.get('offset',  0)) if str(params.get('offset',  '0' )).strip() else 0

            total_count, results = search_merchants(
                wallet_number,
                merchant_type,
                status_filter,
                dba_filter     = dba_filter,
                kam_filter     = kam_filter,
                persona_filter = persona_filter,
                limit          = limit,
                offset         = offset
            )

            next_offset = offset + limit if offset + limit < total_count else None
            previous_offset = offset - limit if offset > 0 else None

            self.send_json({
                "code":    "MO_MLF200",
                "lang":    "en",
                "message": "Merchant List Found",
                "data": {
                    "count":    total_count,
                    "next":     next_offset,
                    "previous": previous_offset,
                    "results":  results
                }
            })

        else:
            self.send_json({"error": "Not found"}, 404)

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body           = self.rfile.read(content_length)

        try:
            data = json.loads(body)
        except:
            data = {}

        # ============================================
        # LOGIN
        # ============================================
        if '/auth/web/v1/login/' in self.path:
            username = data.get("username", "")
            password = data.get("password", "")

            if username == USERNAME and password == PASSWORD:
                self.send_json({
                    "code":    "MO_JTC200",
                    "lang":    "en",
                    "message": "Login Successful",
                    "token":   TOKEN
                })
            else:
                self.send_json({
                    "code":    "MO_JTC401",
                    "message": "Invalid credentials"
                }, 401)

        # ============================================
        # DOWNLOAD QR CODE
        # ============================================
        elif '/qr-code/download/' in self.path:
            auth = self.headers.get("authorization", "")
            if TOKEN not in auth:
                self.send_json({"error": "Unauthorized"}, 401)
                return

            global _batch_counter
            with _batch_counter_lock:
                batch_num     = _batch_counter
                _batch_counter += 1

            wallets = data.get("merchant_wallets", [])

            # Simulate batch failure
            if batch_num == FAIL_BATCH_INDEX:
                self.send_json({
                    "code":    "MO_MBQDF400",
                    "lang":    "en",
                    "message": "Merchant bulk qr cannot be downloaded due to some reason, please try again"
                }, 400)
                return

            # Simulate missing wallets in first batch
            missing = set()
            if batch_num == 0 and len(wallets) > MISSING_COUNT:
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

        # ============================================
        # GENERATE QR CODE
        # ============================================
        elif '/qr-code/generate/' in self.path:
            self.send_json({
                "code":    "MO_QGS200",
                "message": "QR codes generation started"
            })

        else:
            self.send_json({"error": "Not found"}, 404)


if __name__ == "__main__":
    PORT   = 8000
    server = HTTPServer(('0.0.0.0', PORT), PortalAPIHandler)
    server.timeout = 300  # 5 minutes timeout
    print(f"\n{'='*50}")
    print(f"  Upay Portal API running on port {PORT}")
    print(f"  credentials: {USERNAME} / {PASSWORD}")
    print(f"  Press Ctrl+C to stop")
    print(f"{'='*50}\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nAPI stopped.")