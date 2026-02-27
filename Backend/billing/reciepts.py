import io
import os
from decimal import Decimal
from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone

from reportlab.lib.pagesizes import A5
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.lib import colors


def build_local_tax_receipt_pdf(payment, user, bill):
    """
    FCC-style Local Tax receipt (clean PDF, not the scanned image).

    - Logo + Council name header
    - Receipt title
    - Amount + FCC receipt number
    - Holder details (name, address, ward)
    - Payment info (date/time, transaction ref)
    - Processed-by + designation lines (replaces 'Issuing Officer')
    """

    buffer = io.BytesIO()
    page_w, page_h = A5
    p = canvas.Canvas(buffer, pagesize=A5)

    # -------------------------
    # Helpers (avoid descriptors)
    # -------------------------
    def safe(val):
        return (str(val) if val is not None else "").strip()

    full_name = safe(f"{user.first_name} {user.last_name}")  # ✅ instance values only
    ward_name = safe(getattr(user, "ward", "") or "")

    address = ""
    try:
        if hasattr(user, "citizenprofile") and user.citizenprofile and user.citizenprofile.address:
            address = safe(user.citizenprofile.address)
    except Exception:
        address = "Not Stated"

    # Receipt numbering (simple)
    receipt_no = f"{payment.id:06d}"  # 000011 style

    paid_dt = payment.paid_at or timezone.now()
    date_str = paid_dt.strftime("%d/%m/%Y")
    time_str = paid_dt.strftime("%I:%M %p")

    amount_sll = Decimal(bill.amount_due or 0)
    amount_sll_str = f"LE {int(amount_sll):,}"  # council style prints Le as whole amount

    txn_ref = safe(payment.stripe_payment_intent_id or payment.stripe_checkout_session_id or "")

    # Replace "Issuing Officer" with a system-aligned value
    # (you can later make this a settings value or the staff/admin name that processed it)
    processed_by = getattr(settings, "RECEIPT_PROCESSED_BY", "CCRSMS Online Payment")
    designation = getattr(settings, "RECEIPT_DESIGNATION", "F.C.C")

    # -------------------------
    # Layout constants
    # -------------------------
    margin = 26
    x_left = margin
    x_right = page_w - margin
    y = page_h - margin

    # -------------------------
    # Header: Logo + Council name
    # -------------------------
    logo_path = os.path.join(settings.BASE_DIR, "uploads", "receipts", "template", "fcc_logo.png")
    if os.path.exists(logo_path):
        logo = ImageReader(logo_path)
        # centered logo
        logo_w, logo_h = 70, 70
        p.drawImage(logo, (page_w - logo_w) / 2, y - logo_h, width=logo_w, height=logo_h, mask="auto")

    y -= 80

    p.setFont("Helvetica-Bold", 12)
    p.drawCentredString(page_w / 2, y, "FREETOWN CITY COUNCIL")
    y -= 18

    p.setFont("Helvetica-Bold", 13)
    p.drawCentredString(page_w / 2, y, "LOCAL TAX RECEIPT")
    y -= 14

    p.setStrokeColor(colors.black)
    p.setLineWidth(1)
    p.line(x_left, y, x_right, y)
    y -= 18

    # -------------------------
    # Amount + Receipt number (same line feel as council receipt)
    # -------------------------
    p.setFont("Helvetica-Bold", 14)
    p.drawString(x_left, y, amount_sll_str)

    p.setFont("Helvetica-Bold", 11)
    p.drawRightString(x_right, y + 2, f"FCC {receipt_no}")
    y -= 22

    # -------------------------
    # Holder / Address lines like the paper receipt
    # -------------------------
    p.setFont("Helvetica", 10)
    p.drawString(x_left, y, "Holder's Name:")
    p.setFont("Helvetica-Bold", 10)
    p.drawString(x_left + 95, y, full_name or "-")
    y -= 16

    p.setFont("Helvetica", 10)
    p.drawString(x_left, y, "Address:")
    p.setFont("Helvetica", 10)
    p.drawString(x_left + 95, y, address or "-")
    y -= 16

    p.setFont("Helvetica", 10)
    p.drawString(x_left, y, "Ward:")
    p.setFont("Helvetica-Bold", 10)
    p.drawString(x_left + 95, y, ward_name or "-")
    y -= 18

    # -------------------------
    # Payment meta (date/time + transaction reference)
    # -------------------------
    p.setFont("Helvetica", 9)
    p.drawString(x_left, y, f"Date: {date_str}    Time: {time_str}")
    y -= 14

    p.setFont("Helvetica", 9)
    p.drawString(x_left, y, "Transaction Ref:")
    p.setFont("Helvetica-Bold", 8.5)
    p.drawString(x_left + 95, y, txn_ref or "-")
    y -= 18

    # Divider
    p.setStrokeColor(colors.black)
    p.setLineWidth(0.8)
    p.line(x_left, y, x_right, y)
    y -= 18

    # -------------------------
    # “Issuing Officer” replacement (system aligned)
    # -------------------------
    p.setFont("Helvetica", 10)
    p.drawString(x_left, y, "Processed By:")
    p.setFont("Helvetica-Bold", 10)
    p.drawString(x_left + 95, y, safe(processed_by))
    y -= 16

    p.setFont("Helvetica", 10)
    p.drawString(x_left, y, "Designation:")
    p.setFont("Helvetica-Bold", 10)
    p.drawString(x_left + 95, y, safe(designation))
    y -= 28

    # Signature line
    p.setLineWidth(0.8)
    p.line(x_left, y, x_left + 180, y)
    p.setFont("Helvetica", 9)
    p.drawString(x_left, y - 12, "Authorized Signature")
    y -= 30

    # Footer note
    p.setFont("Helvetica-Oblique", 8)
    p.setFillColor(colors.grey)
    p.drawCentredString(page_w / 2, margin - 6, "System-generated receipt (CCRSMS) — Freetown City Council")
    p.setFillColor(colors.black)

    p.showPage()
    p.save()

    buffer.seek(0)
    return ContentFile(buffer.read(), name=f"local_tax_receipt_{payment.id}.pdf")


def build_city_rate_receipt_pdf(payment, user, bill):
    buffer = io.BytesIO()
    page_w, page_h = A5
    p = canvas.Canvas(buffer, pagesize=A5)

    def safe(s): return (s or "").strip()

    full_name = safe(f"{user.first_name} {user.last_name}")
    ward_name = safe(str(getattr(user, "ward", "") or ""))

    receipt_no = f"{payment.id:06d}"
    dt = payment.paid_at or timezone.now()
    date_str = dt.strftime("%d/%m/%Y")
    time_str = dt.strftime("%I:%M %p")

    amount_sll = payment.amount or Decimal("0.00")
    amount_due = bill.amount_due or Decimal("0.00")
    amount_paid = bill.amount_paid or Decimal("0.00")
    balance = max(amount_due - amount_paid, Decimal("0.00"))

    amount_sll_str = f"LE {int(amount_sll):,}"
    due_str = f"LE {int(amount_due):,}"
    paid_str = f"LE {int(amount_paid):,}"
    bal_str  = f"LE {int(balance):,}"

    sll_per_usd = Decimal(str(getattr(settings, "SLL_PER_USD", 25000)))
    usd_amount = (amount_sll / sll_per_usd).quantize(Decimal("0.01"))
    usd_str = f"${usd_amount}"

    txn = safe(payment.stripe_payment_intent_id or payment.stripe_checkout_session_id or "")

    margin = 28
    y = page_h - margin

    # Logo
    logo_path = os.path.join(settings.BASE_DIR, "billing", "static", "billing", "branding", "fcc_logo.png")
    if os.path.exists(logo_path):
        logo = ImageReader(logo_path)
        p.drawImage(logo, margin, y - 70, width=60, height=60, mask="auto")

    # Header
    p.setFont("Helvetica-Bold", 14)
    p.drawString(margin + 70, y - 22, "FREETOWN CITY COUNCIL")

    p.setFont("Helvetica-Bold", 12)
    p.drawString(margin + 70, y - 42, "CITY RATE RECEIPT")

    p.setStrokeColor(colors.black)
    p.setLineWidth(1)
    p.line(margin, y - 80, page_w - margin, y - 80)

    # Receipt meta
    y2 = y - 105
    p.setFont("Helvetica", 9)
    p.drawString(margin, y2, f"Receipt No: FCC {receipt_no}")
    p.drawRightString(page_w - margin, y2, f"Date: {date_str}  {time_str}")

    # Amount big
    y3 = y2 - 40
    p.setFont("Helvetica-Bold", 18)
    p.drawString(margin, y3, amount_sll_str)

    p.setFont("Helvetica", 9)
    p.drawRightString(page_w - margin, y3 + 4, f"Equivalent: {usd_str} (USD)")

    # Details
    y4 = y3 - 30

    def row(label, value, font_size=10):
        nonlocal y4
        p.setFont("Helvetica-Bold", 10)
        p.drawString(margin, y4, label)
        p.setFont("Helvetica", font_size)
        p.drawString(margin + 120, y4, value or "-")
        y4 -= 18

    row("Holder's Name:", full_name)
    row("Ward:", ward_name)
    row("Service:", "City Rate (Property Tax)")
    row("Installments Used:", f"{bill.installment_count} / {bill.max_installments}")
    row("Total Due:", due_str)
    row("Total Paid:", paid_str)
    row("Balance:", bal_str)
    row("Payment Channel:", "Online Payment (Stripe)")
    row("Transaction Ref:", txn, font_size=9)

    # Signature lines
    y5 = y4 - 20
    p.setLineWidth(0.8)
    p.line(margin, y5, page_w/2 - 10, y5)
    p.line(page_w/2 + 10, y5, page_w - margin, y5)
    p.setFont("Helvetica", 9)
    p.drawString(margin, y5 - 12, "Processed By (CCRSMS)")
    p.drawString(page_w/2 + 10, y5 - 12, "Authorized By (F.C.C)")

    p.setFont("Helvetica-Oblique", 8)
    p.setFillColor(colors.grey)
    p.drawString(margin, margin, "System-generated receipt for Freetown City Council.")
    p.setFillColor(colors.black)

    p.showPage()
    p.save()

    buffer.seek(0)
    return ContentFile(buffer.read(), name=f"city_rate_receipt_{payment.id}.pdf")

