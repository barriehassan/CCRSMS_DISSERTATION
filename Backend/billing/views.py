import stripe
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.utils import timezone
from django.db import transaction
from datetime import timedelta

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import (
    Bill, 
    Payment, 
    ServiceType, 
    BillStatus, 
    PaymentStatus,
    WastePlan, 
    WasteCoverage, 
    WasteServiceProvider,
    WasteInterval,
    CoverageStatus,
    WasteWardMeta,
    WasteBlockProvider,
    WasteBlock,
)
from .serializers import (
    LocalTaxCheckoutSerializer,
    LocalTaxCheckoutResponseSerializer,
    VerifySessionSerializer,
    PaymentSerializer,
    WastePlanSerializer,
    WasteCheckoutSerializer,
    WasteCoverageSerializer,
)
from .notifications import(
    notify_admin_payment_success,
    notify_citizen_payment_success,
    notify_staff_ward_payment_success
)
from .reciepts import (
    build_local_tax_receipt_pdf, 
    build_city_rate_receipt_pdf,
    build_waste_collection_receipt_pdf,
)
from django.db.models import Sum, Value, DecimalField
from django.db.models.functions import Coalesce
from .serializers import PaymentListSerializer, PaymentDetailSerializer, BillSerializer, CityRateCheckoutSerializer


stripe.api_key = settings.STRIPE_SECRET_KEY


LOCAL_TAX_AMOUNT = Decimal("10.00")  # Le 12.00 (your requirement)


class LocalTaxViewSet(viewsets.ViewSet):
    """
    Local Tax payment flow (Option C):
    1) POST /billing/local-tax/checkout/ -> returns Stripe Checkout URL + session_id
    2) GET  /billing/local-tax/verify/?session_id=cs_test_... -> verifies and marks paid
    """
    permission_classes = [permissions.IsAuthenticated]

    def _get_or_create_local_tax_bill(self, user) -> Bill:
        bill = Bill.objects.filter(
            user=user,
            service_type=ServiceType.LOCAL_TAX,
            status__in=[BillStatus.PENDING, BillStatus.PARTIAL],
        ).order_by("-created_at").first()

        if bill:
            return bill

        return Bill.objects.create(
            user=user,
            service_type=ServiceType.LOCAL_TAX,
            amount_due=LOCAL_TAX_AMOUNT,       # stored in SLE
            amount_paid=Decimal("0.00"),
            status=BillStatus.PENDING,
            allow_installments=False,
            max_installments=1,
            installment_count=0,
            due_date=None,
        )

    def _sll_to_usd_cents(self, amount_sll: Decimal) -> int:
        """
        Converts SLE -> USD cents for Stripe.
        Uses fixed FX rate from settings: SLL_PER_USD (e.g. 24)
        """
        sll_per_usd = Decimal(str(getattr(settings, "SLL_PER_USD", "24")))
        usd_amount = (amount_sll / sll_per_usd).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        cents = int((usd_amount * 100).to_integral_value(rounding=ROUND_HALF_UP))
        return max(cents, 50)

    @action(detail=False, methods=["post"], url_path="checkout")
    def checkout(self, request):
        serializer = LocalTaxCheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        bill = self._get_or_create_local_tax_bill(user)

        if bill.status == BillStatus.PAID:
            return Response({"error": "Local Tax already paid."}, status=status.HTTP_400_BAD_REQUEST)

        currency = getattr(settings, "STRIPE_CURRENCY", "usd")
        unit_amount_cents = self._sll_to_usd_cents(bill.amount_due)

        # Stripe minimum is $0.50 USD => 50 cents
        if unit_amount_cents < 50:
            return Response(
                {"error": "Stripe minimum is $0.50. Increase the service amount or adjust FX rate."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        success_url = "http://localhost:5173/payments/local-tax/success?session_id={CHECKOUT_SESSION_ID}"
        cancel_url = "http://localhost:5173/payments/local-tax/cancel"

        payment = Payment.objects.create(
            bill=bill,
            amount=bill.amount_due,  # store SLE amount
            status=PaymentStatus.INITIATED,
        )

        try:
            session = stripe.checkout.Session.create(
                mode="payment",
                payment_method_types=["card"],
                line_items=[
                    {
                        "price_data": {
                            "currency": currency,
                            "product_data": {"name": "Local Tax (Freetown City Council)"},
                            "unit_amount": unit_amount_cents,
                        },
                        "quantity": 1,
                    }
                ],
                metadata={
                    "payment_id": str(payment.id),
                    "bill_id": str(bill.id),
                    "service_type": ServiceType.LOCAL_TAX,
                    "user_id": str(user.id),
                    "amount_sll": str(bill.amount_due),
                    "fx_sll_per_usd": str(getattr(settings, "SLL_PER_USD", "24")),
                },
                success_url=success_url,
                cancel_url=cancel_url,
            )

            payment.stripe_checkout_session_id = session.id
            payment.save(update_fields=["stripe_checkout_session_id"])

            return Response(
                LocalTaxCheckoutResponseSerializer(
                    {"checkout_url": session.url, "session_id": session.id}
                ).data,
                status=200,
            )

        except Exception as e:
            payment.status = PaymentStatus.FAILED
            payment.save(update_fields=["status"])
            return Response({"error": str(e)}, status=400)

    @action(detail=False, methods=["get"], url_path="verify")
    def verify(self, request):
        serializer = VerifySessionSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        session_id = serializer.validated_data["session_id"]
        user = request.user

        payment = Payment.objects.select_related("bill").filter(
            stripe_checkout_session_id=session_id,
            bill__user=user,
            bill__service_type=ServiceType.LOCAL_TAX,
        ).first()

        if not payment:
            return Response({"error": "Payment session not found."}, status=404)

        if payment.status == PaymentStatus.PAID:
            return Response(PaymentSerializer(payment).data, status=200)

        try:
            session = stripe.checkout.Session.retrieve(session_id, expand=["payment_intent"])

            if session.payment_status != "paid":
                return Response({"status": "NOT_PAID", "payment_status": session.payment_status}, status=200)

            payment_intent_id = session.payment_intent.id if session.payment_intent else None

            with transaction.atomic():
                payment.status = PaymentStatus.PAID
                payment.paid_at = timezone.now()
                payment.stripe_payment_intent_id = payment_intent_id
                payment.save(update_fields=["status", "paid_at", "stripe_payment_intent_id"])

                bill = payment.bill
                bill.amount_paid = bill.amount_due
                bill.status = BillStatus.PAID
                bill.save(update_fields=["amount_paid", "status"])

                # Receipt PDF
                receipt_file = build_local_tax_receipt_pdf(payment=payment, user=user, bill=bill)
                payment.receipt_pdf.save(receipt_file.name, receipt_file, save=True)

                # Notifications (unchanged)
                try:
                    notify_citizen_payment_success(payment=payment, bill=bill, user=user)
                except Exception as e:
                    print("[PAYMENT EMAIL ERROR] citizen:", e)

                try:
                    notify_staff_ward_payment_success(payment=payment, bill=bill, user=user)
                except Exception as e:
                    print("[PAYMENT EMAIL ERROR] staff ward:", e)

                try:
                    notify_admin_payment_success(payment=payment, bill=bill, user=user)
                except Exception as e:
                    print("[PAYMENT EMAIL ERROR] admin:", e)

            return Response(PaymentSerializer(payment).data, status=200)

        except Exception as e:
            return Response({"error": str(e)}, status=400)

class PaymentDataViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Citizen React API:
    - /billing/payments/           -> list payment history for logged-in user
    - /billing/payments/{id}/      -> retrieve a payment + bill detail
    - /billing/payments/stats/     -> KPI stats for dashboard
    - /billing/payments/recent/    -> recent transactions (for dashboard widget)
    - /billing/payments/bills/     -> bills for user (pending/paid etc)
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Only payments that belong to the logged-in user via bill relation
        qs = Payment.objects.select_related("bill").filter(bill__user=self.request.user)

        # Optional filters (React can pass query params)
        service_type = self.request.query_params.get("service_type")
        pay_status = self.request.query_params.get("status")

        if service_type:
            qs = qs.filter(bill__service_type=service_type)
        if pay_status:
            qs = qs.filter(status=pay_status)

        return qs.order_by("-created_at")

    def get_serializer_class(self):
        if self.action == "retrieve":
            return PaymentDetailSerializer
        return PaymentListSerializer

    # -------------------------
    # Dashboard stats endpoint
    # -------------------------
    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request):
        user = request.user
        now = timezone.now()

        ytd_start = timezone.datetime(
            now.year, 1, 1, tzinfo=timezone.get_current_timezone()
        )

        zero_decimal = Value(0, output_field=DecimalField(max_digits=12, decimal_places=2))

        total_paid_ytd = Payment.objects.filter(
            bill__user=user,
            status=PaymentStatus.PAID,
            paid_at__gte=ytd_start
        ).aggregate(
            total=Coalesce(Sum("amount"), zero_decimal)
        )["total"]

        pending_total = Bill.objects.filter(
            user=user,
            status__in=[BillStatus.PENDING, BillStatus.PARTIAL]
        ).aggregate(
            total=Coalesce(Sum("amount_due"), zero_decimal)
        )["total"]

        last_payment = Payment.objects.select_related("bill").filter(
            bill__user=user,
            status=PaymentStatus.PAID
        ).order_by("-paid_at").first()

        return Response({
            "total_paid_ytd": str(total_paid_ytd),
            "pending_bills_total": str(pending_total),
            "last_payment": {
                "amount": str(last_payment.amount) if last_payment else "0.00",
                "paid_at": last_payment.paid_at if last_payment else None,
                "service_type": last_payment.bill.service_type if last_payment else None,
                "payment_id": last_payment.id if last_payment else None,
            }
        }, status=200)

    # -------------------------
    # Recent transactions
    # -------------------------
    @action(detail=False, methods=["get"], url_path="recent")
    def recent(self, request):
        qs = self.get_queryset().filter(status=PaymentStatus.PAID)[:5]
        return Response(PaymentListSerializer(qs, many=True).data, status=200)

    # -------------------------
    # Bills list (for Pending Bills section)
    # -------------------------
    @action(detail=False, methods=["get"], url_path="bills")
    def bills(self, request):
        user = request.user
        qs = Bill.objects.filter(user=user).order_by("-created_at")

        service_type = request.query_params.get("service_type")
        bill_status = request.query_params.get("status")  # PENDING / PARTIAL / PAID

        if service_type:
            qs = qs.filter(service_type=service_type)
        if bill_status:
            qs = qs.filter(status=bill_status)

        return Response(BillSerializer(qs, many=True).data, status=200)

class CityRateViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    # ---------------------------------------------------
    # Helpers
    # ---------------------------------------------------

    def _due_date_sept_30(self):
        today = timezone.now().date()
        return today.replace(month=9, day=30)

    def _sll_to_usd_cents(self, amount_sll: Decimal) -> int:
        """
        Convert NEW LEONES (SLE) -> USD cents for Stripe.
        Uses SLL_PER_USD from settings (e.g. 24 SLE = 1 USD)
        """
        sll_per_usd = Decimal(str(getattr(settings, "SLL_PER_USD", "24")))
        usd_amount = (amount_sll / sll_per_usd).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        cents = int((usd_amount * 100).to_integral_value(rounding=ROUND_HALF_UP))
        return max(cents, 50)

    def _get_or_create_city_rate_bill(self, user, amount_due: Decimal | None) -> Bill:
        bill = Bill.objects.filter(
            user=user,
            service_type=ServiceType.CITY_RATE,
            status__in=[BillStatus.PENDING, BillStatus.PARTIAL],
        ).order_by("-created_at").first()

        if bill:
            return bill

        if amount_due is None:
            raise ValueError("amount_due is required for first City Rate payment.")

        return Bill.objects.create(
            user=user,
            service_type=ServiceType.CITY_RATE,
            amount_due=amount_due,  # stored in SLE
            amount_paid=Decimal("0.00"),
            status=BillStatus.PENDING,
            allow_installments=True,
            max_installments=3,
            installment_count=0,
            due_date=self._due_date_sept_30(),
        )

    # ---------------------------------------------------
    # Checkout
    # ---------------------------------------------------

    @action(detail=False, methods=["post"], url_path="checkout")
    def checkout(self, request):
        serializer = CityRateCheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        amount_due = serializer.validated_data.get("amount_due")
        pay_amount = serializer.validated_data["pay_amount"]

        bill = self._get_or_create_city_rate_bill(user, amount_due)

        if bill.status == BillStatus.PAID:
            return Response({"error": "City Rate already fully paid."}, status=400)

        if bill.installment_count >= bill.max_installments:
            return Response({"error": "Maximum installments already used."}, status=400)

        remaining = bill.amount_due - bill.amount_paid

        if pay_amount > remaining:
            return Response(
                {"error": f"Pay amount exceeds remaining balance (SLE {remaining})."},
                status=400,
            )

        # ✅ Convert SLE -> USD cents
        unit_amount_cents = self._sll_to_usd_cents(pay_amount)

        # Stripe minimum = 50 cents ($0.50)
        if unit_amount_cents < 50:
            return Response(
                {
                    "error": "Stripe minimum is $0.50. "
                             "Increase pay_amount or adjust FX rate."
                },
                status=400,
            )

        currency = getattr(settings, "STRIPE_CURRENCY", "usd")
        success_url = "http://localhost:5173/payments/city-rate/success?session_id={CHECKOUT_SESSION_ID}"
        cancel_url = "http://localhost:5173/payments/city-rate/cancel"

        payment = Payment.objects.create(
            bill=bill,
            amount=pay_amount,  # stored in SLE
            status=PaymentStatus.INITIATED,
        )

        try:
            session = stripe.checkout.Session.create(
                mode="payment",
                payment_method_types=["card"],
                line_items=[{
                    "price_data": {
                        "currency": currency,
                        "product_data": {"name": "City Rate (Freetown City Council)"},
                        "unit_amount": unit_amount_cents,
                    },
                    "quantity": 1,
                }],
                metadata={
                    "payment_id": str(payment.id),
                    "bill_id": str(bill.id),
                    "service_type": ServiceType.CITY_RATE,
                    "user_id": str(user.id),
                    "pay_amount_sll": str(pay_amount),
                    "fx_sll_per_usd": str(getattr(settings, "SLL_PER_USD", "25")),
                },
                success_url=success_url,
                cancel_url=cancel_url,
            )

            payment.stripe_checkout_session_id = session.id
            payment.save(update_fields=["stripe_checkout_session_id"])

            return Response(
                LocalTaxCheckoutResponseSerializer(
                    {"checkout_url": session.url, "session_id": session.id}
                ).data,
                status=200,
            )

        except Exception as e:
            payment.status = PaymentStatus.FAILED
            payment.save(update_fields=["status"])
            return Response({"error": str(e)}, status=400)

    # ---------------------------------------------------
    # Verify
    # ---------------------------------------------------

    @action(detail=False, methods=["get"], url_path="verify")
    def verify(self, request):
        serializer = VerifySessionSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        session_id = serializer.validated_data["session_id"]
        user = request.user

        payment = Payment.objects.select_related("bill").filter(
            stripe_checkout_session_id=session_id,
            bill__user=user,
            bill__service_type=ServiceType.CITY_RATE,
        ).first()

        if not payment:
            return Response({"error": "Payment session not found."}, status=404)

        if payment.status == PaymentStatus.PAID:
            return Response(PaymentSerializer(payment).data, status=200)

        try:
            session = stripe.checkout.Session.retrieve(session_id, expand=["payment_intent"])

            if session.payment_status != "paid":
                return Response(
                    {"status": "NOT_PAID", "payment_status": session.payment_status},
                    status=200,
                )

            payment_intent_id = session.payment_intent.id if session.payment_intent else None

            with transaction.atomic():
                payment.status = PaymentStatus.PAID
                payment.paid_at = timezone.now()
                payment.stripe_payment_intent_id = payment_intent_id
                payment.save(update_fields=["status", "paid_at", "stripe_payment_intent_id"])

                bill = payment.bill
                bill.amount_paid += payment.amount
                bill.installment_count += 1

                if bill.amount_paid >= bill.amount_due:
                    bill.status = BillStatus.PAID
                else:
                    bill.status = BillStatus.PARTIAL

                bill.save(update_fields=["amount_paid", "installment_count", "status"])

                receipt_file = build_city_rate_receipt_pdf(payment=payment, user=user, bill=bill)
                payment.receipt_pdf.save(receipt_file.name, receipt_file, save=True)

                # Notifications
                try:
                    notify_citizen_payment_success(payment=payment, bill=bill, user=user)
                except Exception as e:
                    print("[PAYMENT EMAIL ERROR] citizen:", e)

                try:
                    notify_staff_ward_payment_success(payment=payment, bill=bill, user=user)
                except Exception as e:
                    print("[PAYMENT EMAIL ERROR] staff ward:", e)

                try:
                    notify_admin_payment_success(payment=payment, bill=bill, user=user)
                except Exception as e:
                    print("[PAYMENT EMAIL ERROR] admin:", e)

            return Response(PaymentSerializer(payment).data, status=200)

        except Exception as e:
            return Response({"error": str(e)}, status=400)
        
class WasteCollectionViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=["get"], url_path="plans")
    def plans(self, request):
        qs = WastePlan.objects.filter(is_active=True).order_by("price")
        return Response(WastePlanSerializer(qs, many=True).data, status=200)

    def _get_block_and_provider(self, user):
        ward = getattr(user, "ward", None)
        if not ward:
            return None, None

        meta = WasteWardMeta.objects.select_related("block").filter(ward=ward).first()
        if not meta or not meta.block:
            return None, None

        mapping = WasteBlockProvider.objects.select_related("provider").filter(block=meta.block).first()
        provider = mapping.provider if mapping else None
        return meta.block, provider

    def _get_or_create_bill(self, user, amount_due: Decimal) -> Bill:
        # single-payment bill for waste
        return Bill.objects.create(
            user=user,
            service_type=ServiceType.WASTE_COLLECTION,
            amount_due=amount_due,
            amount_paid=Decimal("0.00"),
            status=BillStatus.PENDING,
            allow_installments=False,
            max_installments=1,
            installment_count=0,
            due_date=None,
        )

    def _calculate_period(self, plan: WastePlan, base_date):
        if plan.interval == "WEEK":
            return base_date, base_date + timedelta(days=7)
        return base_date, base_date + timedelta(days=30)

    @action(detail=False, methods=["post"], url_path="checkout")
    def checkout(self, request):
        serializer = WasteCheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        plan = WastePlan.objects.get(id=serializer.validated_data["plan_id"], is_active=True)

        block, provider = self._get_block_and_provider(user)
        if not block or not provider:
            return Response(
                {"error": "No waste provider configured for your ward/block. Please contact FCC."},
                status=400
            )

        # Convert NEW LEONES (SLE) -> USD for Stripe
        # Keep your settings name SLL_PER_USD if you already use it,
        # but it now means "SLE per USD".
        sle_per_usd = Decimal(str(getattr(settings, "SLL_PER_USD", 24)))  # you said keep at 12
        usd_amount = (plan.price / sle_per_usd).quantize(Decimal("0.01"))
        unit_amount_cents = int((usd_amount * 100).to_integral_value(rounding=ROUND_HALF_UP))

        if unit_amount_cents < 50:
            return Response({"error": "Stripe minimum is $0.50. Increase plan price."}, status=400)

        currency = getattr(settings, "STRIPE_CURRENCY", "usd")
        success_url = "http://localhost:5173/payments/waste/success?session_id={CHECKOUT_SESSION_ID}"
        cancel_url = "http://localhost:5173/payments/waste/cancel"

        bill = self._get_or_create_bill(user, amount_due=plan.price)

        payment = Payment.objects.create(
            bill=bill,
            amount=plan.price,  # stored in SLE
            status=PaymentStatus.INITIATED,
        )

        try:
            session = stripe.checkout.Session.create(
                mode="payment",
                payment_method_types=["card"],
                line_items=[{
                    "price_data": {
                        "currency": currency,
                        "product_data": {"name": f"Waste Collection ({plan.name}) - FCC"},
                        "unit_amount": unit_amount_cents,
                    },
                    "quantity": 1
                }],
                metadata={
                    "payment_id": str(payment.id),
                    "bill_id": str(bill.id),
                    "service_type": ServiceType.WASTE_COLLECTION,
                    "user_id": str(user.id),
                    "plan_id": str(plan.id),
                    "block_id": str(block.id),
                    "provider_id": str(provider.id),
                },
                success_url=success_url,
                cancel_url=cancel_url,
            )

            payment.stripe_checkout_session_id = session.id
            payment.save(update_fields=["stripe_checkout_session_id"])

            return Response(
                LocalTaxCheckoutResponseSerializer({"checkout_url": session.url, "session_id": session.id}).data,
                status=200
            )
        except Exception as e:
            payment.status = PaymentStatus.FAILED
            payment.save(update_fields=["status"])
            return Response({"error": str(e)}, status=400)

    @action(detail=False, methods=["get"], url_path="verify")
    def verify(self, request):
        serializer = VerifySessionSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        session_id = serializer.validated_data["session_id"]
        user = request.user

        payment = Payment.objects.select_related("bill").filter(
            stripe_checkout_session_id=session_id,
            bill__user=user,
            bill__service_type=ServiceType.WASTE_COLLECTION,
        ).first()

        if not payment:
            return Response({"error": "Payment session not found."}, status=404)

        if payment.status == PaymentStatus.PAID:
            return Response(PaymentSerializer(payment).data, status=200)

        try:
            session = stripe.checkout.Session.retrieve(session_id, expand=["payment_intent"])
            if session.payment_status != "paid":
                return Response({"status": "NOT_PAID", "payment_status": session.payment_status}, status=200)

            payment_intent_id = session.payment_intent.id if session.payment_intent else None
            plan_id = int(session.metadata.get("plan_id"))

            plan = WastePlan.objects.get(id=plan_id)

            # Trust current mapping (ward->block->provider)
            block, provider = self._get_block_and_provider(user)

            with transaction.atomic():
                payment.status = PaymentStatus.PAID
                payment.paid_at = timezone.now()
                payment.stripe_payment_intent_id = payment_intent_id
                payment.save(update_fields=["status", "paid_at", "stripe_payment_intent_id"])

                bill = payment.bill
                bill.amount_paid = bill.amount_due
                bill.status = BillStatus.PAID
                bill.save(update_fields=["amount_paid", "status"])

                today = timezone.now().date()

                active_cov = WasteCoverage.objects.filter(
                    user=user,
                    status=CoverageStatus.ACTIVE,
                    end_date__gte=today
                ).order_by("-end_date").first()

                base_start = active_cov.end_date if active_cov else today
                start_date, end_date = self._calculate_period(plan, base_start)

                coverage = WasteCoverage.objects.create(
                    user=user,
                    ward=getattr(user, "ward", None),
                    block=block,
                    provider=provider,
                    plan=plan,
                    start_date=start_date,
                    end_date=end_date,
                    status=CoverageStatus.ACTIVE,
                    last_payment=payment,
                )

                receipt_file = build_waste_collection_receipt_pdf(
                    payment=payment, user=user, bill=bill, coverage=coverage
                )
                payment.receipt_pdf.save(receipt_file.name, receipt_file, save=True)

                # Notifications
                try:
                    notify_citizen_payment_success(payment=payment, bill=bill, user=user)
                except Exception as e:
                    print("[PAYMENT EMAIL ERROR] citizen:", e)

                try:
                    notify_staff_ward_payment_success(payment=payment, bill=bill, user=user)
                except Exception as e:
                    print("[PAYMENT EMAIL ERROR] staff ward:", e)

                try:
                    notify_admin_payment_success(payment=payment, bill=bill, user=user)
                except Exception as e:
                    print("[PAYMENT EMAIL ERROR] admin:", e)

            return Response(
                {
                    "payment": PaymentSerializer(payment).data,
                    "coverage": WasteCoverageSerializer(coverage).data,
                },
                status=200
            )
        except Exception as e:
            return Response({"error": str(e)}, status=400)


