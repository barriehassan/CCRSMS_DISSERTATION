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
    FCC-style Local Tax receipt (clean PDF).

    Updated to NEW LEONES (SLE).
    - Amount displays as SLE
    - Optional USD equivalent shown using settings.SLL_PER_USD (treated as SLE per USD)
    """

    buffer = io.BytesIO()
    page_w, page_h = A5
    p = canvas.Canvas(buffer, pagesize=A5)

    def safe(val):
        return (str(val) if val is not None else "").strip()

    full_name = safe(f"{user.first_name} {user.last_name}")
    ward_name = safe(getattr(user, "ward", "") or "")

    address = ""
    try:
        if hasattr(user, "citizenprofile") and user.citizenprofile and user.citizenprofile.address:
            address = safe(user.citizenprofile.address)
    except Exception:
        address = "Not Stated"

    receipt_no = f"{payment.id:06d}"

    paid_dt = payment.paid_at or timezone.now()
    date_str = paid_dt.strftime("%d/%m/%Y")
    time_str = paid_dt.strftime("%I:%M %p")

    # ✅ Amount stored in NEW LEONES (SLE)
    amount_sle = Decimal(bill.amount_due or 0)
    amount_sle_str = f"SLE {amount_sle:,.2f}"

    # ✅ USD equivalent (SLL_PER_USD is now treated as SLE per USD)
    sle_per_usd = Decimal(str(getattr(settings, "SLL_PER_USD", 12)))
    usd_amount = Decimal("0.00")
    if sle_per_usd and sle_per_usd > 0:
        usd_amount = (amount_sle / sle_per_usd).quantize(Decimal("0.01"))
    usd_str = f"${usd_amount}"

    txn_ref = safe(payment.stripe_payment_intent_id or payment.stripe_checkout_session_id or "")

    processed_by = getattr(settings, "RECEIPT_PROCESSED_BY", "CCRSMS Online Payment")
    designation = getattr(settings, "RECEIPT_DESIGNATION", "F.C.C")

    # Layout constants
    margin = 26
    x_left = margin
    x_right = page_w - margin
    y = page_h - margin

    # Header: Logo + Council name
    logo_path = os.path.join(settings.BASE_DIR, "uploads", "receipts", "template", "fcc_logo.png")
    if os.path.exists(logo_path):
        logo = ImageReader(logo_path)
        logo_w, logo_h = 70, 70
        p.drawImage(
            logo,
            (page_w - logo_w) / 2,
            y - logo_h,
            width=logo_w,
            height=logo_h,
            mask="auto",
        )

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

    # Amount + Receipt number
    p.setFont("Helvetica-Bold", 14)
    p.drawString(x_left, y, amount_sle_str)

    p.setFont("Helvetica-Bold", 11)
    p.drawRightString(x_right, y + 2, f"FCC {receipt_no}")
    y -= 16

    # ✅ USD equivalent line (optional but useful since Stripe shows USD)
    p.setFont("Helvetica", 9)
    p.drawString(x_left, y, f"Equivalent: {usd_str} (USD)")
    y -= 18

    # Holder / Address / Ward
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

    # Payment meta
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

    # Processed by / Designation
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

    # Footer
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

    def safe(s):
        return (str(s).strip() if s is not None else "")

    full_name = safe(f"{user.first_name} {user.last_name}") or "-"
    ward_name = safe(getattr(user, "ward", "")) or "-"

    receipt_no = f"{payment.id:06d}"
    dt = payment.paid_at or timezone.now()
    date_str = dt.strftime("%d/%m/%Y")
    time_str = dt.strftime("%I:%M %p")

    # Amounts stored in NEW LEONES (SLE)
    amount_sle = payment.amount or Decimal("0.00")
    amount_due = bill.amount_due or Decimal("0.00")
    amount_paid = bill.amount_paid or Decimal("0.00")
    balance = max(amount_due - amount_paid, Decimal("0.00"))

    amount_sle_str = f"SLE {amount_sle:,.2f}"
    due_str = f"SLE {amount_due:,.2f}"
    paid_str = f"SLE {amount_paid:,.2f}"
    bal_str  = f"SLE {balance:,.2f}"

    # USD equivalent (SLL_PER_USD now means SLE per USD)
    sle_per_usd = Decimal(str(getattr(settings, "SLL_PER_USD", 12)))
    usd_amount = Decimal("0.00")
    if sle_per_usd and sle_per_usd > 0:
        usd_amount = (amount_sle / sle_per_usd).quantize(Decimal("0.01"))
    usd_str = f"${usd_amount}"

    txn = safe(payment.stripe_payment_intent_id or payment.stripe_checkout_session_id) or "-"

    margin = 28
    y = page_h - margin

    # Logo
    logo_path = os.path.join(
        settings.BASE_DIR, "billing", "static", "billing", "branding", "fcc_logo.png"
    )
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
    p.drawString(margin, y3, amount_sle_str)

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
    p.line(margin, y5, page_w / 2 - 10, y5)
    p.line(page_w / 2 + 10, y5, page_w - margin, y5)

    p.setFont("Helvetica", 9)
    p.drawString(margin, y5 - 12, "Processed By (CCRSMS)")
    p.drawString(page_w / 2 + 10, y5 - 12, "Authorized By (F.C.C)")

    p.setFont("Helvetica-Oblique", 8)
    p.setFillColor(colors.grey)
    p.drawString(margin, margin, "System-generated receipt for Freetown City Council.")
    p.setFillColor(colors.black)

    p.showPage()
    p.save()

    buffer.seek(0)
    return ContentFile(buffer.read(), name=f"city_rate_receipt_{payment.id}.pdf")

def build_waste_collection_receipt_pdf(payment, user, bill, coverage):
    """
    Waste Collection Receipt (FCC style) - NEW FLOW:
    - Ward -> WasteWardMeta -> Block -> Provider
    - coverage contains: ward, block, provider, plan, start_date, end_date
    - Amount stored in NEW LEONES (SLE)
    """
    buffer = io.BytesIO()
    page_w, page_h = A5
    p = canvas.Canvas(buffer, pagesize=A5)

    margin = 28
    y = page_h - margin

    def safe(val):
        return (str(val).strip() if val is not None else "")

    # -----------------------
    # Core values
    # -----------------------
    full_name = safe(f"{user.first_name} {user.last_name}").strip() or "-"
    ward_name = safe(getattr(user, "ward", "")) or "-"

    block_label = "-"
    if coverage and getattr(coverage, "block", None):
        # WasteBlock.__str__ returns "Block X" (or name)
        block_label = safe(coverage.block) or "-"

    plan_name = "-"
    if coverage and getattr(coverage, "plan", None):
        plan_name = safe(coverage.plan.name) or safe(coverage.plan) or "-"

    provider_name = "-"
    provider_phone = "-"
    provider_email = "-"
    if coverage and getattr(coverage, "provider", None):
        provider = coverage.provider
        provider_name = safe(getattr(provider, "name", "")) or "-"
        provider_phone = safe(getattr(provider, "phone", "")) or "-"
        provider_email = safe(getattr(provider, "email", "")) or "-"

    receipt_no = f"{payment.id:06d}"
    paid_dt = payment.paid_at or timezone.now()
    date_str = paid_dt.strftime("%d/%m/%Y")
    time_str = paid_dt.strftime("%I:%M %p")

    # Amount stored in NEW LEONES (SLE)
    amount_sle = bill.amount_due or Decimal("0.00")
    amount_sle_str = f"SLE {amount_sle:,.2f}"

    # USD equivalent (SLL_PER_USD now means SLE per USD)
    sle_per_usd = Decimal(str(getattr(settings, "SLL_PER_USD", 12)))
    usd_amount = Decimal("0.00")
    if sle_per_usd and sle_per_usd > 0:
        usd_amount = (Decimal(amount_sle) / sle_per_usd).quantize(Decimal("0.01"))
    usd_str = f"${usd_amount}"

    txn = safe(payment.stripe_payment_intent_id or payment.stripe_checkout_session_id) or "-"

    period = "-"
    if coverage and getattr(coverage, "start_date", None) and getattr(coverage, "end_date", None):
        period = f"{coverage.start_date.strftime('%d/%m/%Y')}  →  {coverage.end_date.strftime('%d/%m/%Y')}"

    # -----------------------
    # Header (logo + titles)
    # -----------------------
    logo_path = os.path.join(
        settings.BASE_DIR, "billing", "static", "billing", "branding", "fcc_logo.png"
    )
    if os.path.exists(logo_path):
        logo = ImageReader(logo_path)
        p.drawImage(logo, margin, y - 70, width=60, height=60, mask="auto")

    p.setFont("Helvetica-Bold", 14)
    p.drawString(margin + 70, y - 22, "FREETOWN CITY COUNCIL")

    p.setFont("Helvetica-Bold", 12)
    p.drawString(margin + 70, y - 42, "WASTE COLLECTION RECEIPT")

    p.setLineWidth(1)
    p.setStrokeColor(colors.black)
    p.line(margin, y - 80, page_w - margin, y - 80)

    # -----------------------
    # Receipt no / date line
    # -----------------------
    y2 = y - 105
    p.setFont("Helvetica", 9)
    p.drawString(margin, y2, f"Receipt No: FCC {receipt_no}")
    p.drawRightString(page_w - margin, y2, f"Date: {date_str}  {time_str}")

    # -----------------------
    # Amount (big)
    # -----------------------
    y3 = y2 - 40
    p.setFont("Helvetica-Bold", 18)
    p.drawString(margin, y3, amount_sle_str)

    p.setFont("Helvetica", 9)
    p.drawRightString(page_w - margin, y3 + 4, f"Equivalent: {usd_str} (USD)")

    # -----------------------
    # Details block
    # -----------------------
    y4 = y3 - 30

    def label_value(label, value, font_value=10):
        nonlocal y4
        p.setFont("Helvetica-Bold", 10)
        p.drawString(margin, y4, label)
        p.setFont("Helvetica", font_value)
        p.drawString(margin + 95, y4, value)
        y4 -= 18

    label_value("Holder's Name:", full_name)
    label_value("Ward:", ward_name)
    label_value("Block:", block_label)
    label_value("Plan:", plan_name)
    label_value("Coverage:", period, font_value=9)
    label_value("Provider:", provider_name)

    # Provider contact line (under provider)
    y4 += 6  # pull up slightly
    p.setFont("Helvetica", 9)
    p.drawString(margin + 95, y4, f"Tel: {provider_phone}   Email: {provider_email}")
    y4 -= 18

    label_value("Payment Channel:", "Online Payment (Stripe)")
    label_value("Transaction Ref:", txn, font_value=8)

    # -----------------------
    # Sign lines
    # -----------------------
    y5 = y4 - 18
    p.setLineWidth(0.8)
    p.line(margin, y5, page_w / 2 - 10, y5)
    p.line(page_w / 2 + 10, y5, page_w - margin, y5)

    p.setFont("Helvetica", 9)
    p.drawString(margin, y5 - 12, "Processed By (CCRSMS)")
    p.drawString(page_w / 2 + 10, y5 - 12, "Authorized By (F.C.C)")

    # Footer note
    p.setFont("Helvetica-Oblique", 8)
    p.setFillColor(colors.grey)
    p.drawString(margin, margin, "System-generated receipt for Freetown City Council.")
    p.setFillColor(colors.black)

    p.showPage()
    p.save()

    buffer.seek(0)
    return ContentFile(buffer.read(), name=f"waste_receipt_{payment.id}.pdf")
