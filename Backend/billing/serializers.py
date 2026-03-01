from rest_framework import serializers
from .models import Bill, Payment, ServiceType
from decimal import Decimal
from .models import WastePlan, WasteCoverage, WasteServiceProvider


class BillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bill
        fields = "__all__"

class LocalTaxCheckoutSerializer(serializers.Serializer):
    # keep it simple: local tax is fixed amount (Le 10,000)
    # later you can include year, ward, etc.
    pass

class LocalTaxCheckoutResponseSerializer(serializers.Serializer):
    checkout_url = serializers.URLField()
    session_id = serializers.CharField()

class VerifySessionSerializer(serializers.Serializer):
    session_id = serializers.CharField()

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = "__all__"

class PaymentListSerializer(serializers.ModelSerializer):
    bill = BillSerializer(read_only=True)

    class Meta:
        model = Payment
        fields = (
            "id",
            "bill",
            "amount",
            "status",
            "paid_at",
            "receipt_pdf",
            "created_at",
        )

class PaymentDetailSerializer(serializers.ModelSerializer):
    bill = BillSerializer()

    class Meta:
        model = Payment
        fields = "__all__"

class CityRateCheckoutSerializer(serializers.Serializer):
    """
    City Rate varies per property:
    - amount_due (required ONLY for first payment when no bill exists yet)
    - pay_amount (installment amount for this checkout)
    """
    amount_due = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    pay_amount = serializers.DecimalField(max_digits=12, decimal_places=2)

    def validate(self, attrs):
        pay_amount = attrs["pay_amount"]
        if pay_amount <= 0:
            raise serializers.ValidationError({"pay_amount": "Amount must be greater than 0."})
        return attrs

class WastePlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = WastePlan
        fields = ("id", "name", "interval", "price", "is_active")


class WasteServiceProviderSerializer(serializers.ModelSerializer):
    class Meta:
        model = WasteServiceProvider
        fields = ("id", "name", "phone", "email")


class WasteCoverageSerializer(serializers.ModelSerializer):
    plan = WastePlanSerializer(read_only=True)
    provider = WasteServiceProviderSerializer(read_only=True)

    class Meta:
        model = WasteCoverage
        fields = (
            "id",
            "start_date",
            "end_date",
            "status",
            "plan",
            "provider",
            "created_at",
        )


class WasteCheckoutSerializer(serializers.Serializer):
    plan_id = serializers.IntegerField()

    def validate_plan_id(self, value):
        if not WastePlan.objects.filter(id=value, is_active=True).exists():
            raise serializers.ValidationError("Invalid or inactive plan.")
        return value

