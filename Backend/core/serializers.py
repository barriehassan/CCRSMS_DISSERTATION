from rest_framework import serializers
from django.contrib.gis.geos import Point
from .models import Complaint, ComplaintCategory


class ComplaintCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ComplaintCategory
        fields = ("id", "category_name", "description", "department")


class ComplaintSerializer(serializers.ModelSerializer):
    # Citizen should not send citizen field; backend uses request.user
    citizen = serializers.PrimaryKeyRelatedField(read_only=True)

    # Accept lat/lng from frontend and convert to Point
    latitude = serializers.FloatField(write_only=True, required=True)
    longitude = serializers.FloatField(write_only=True, required=True)

    class Meta:
        model = Complaint
        fields = (
            "id",
            "citizen",
            "category",
            "title",
            "description",
            "evidence_image",
            "latitude",
            "longitude",
            "location",
            "street_name",
            "district",
            "status",
            "priority_level",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("location", "status", "priority_level", "created_at", "updated_at")

    def validate(self, attrs):
        # Basic image safety checks (frontend enforces camera capture)
        img = attrs.get("evidence_image")
        if img:
            if img.size > 5 * 1024 * 1024:  # 5MB
                raise serializers.ValidationError({"evidence_image": "Image too large (max 5MB)."})
        return attrs

    def create(self, validated_data):
        lat = validated_data.pop("latitude")
        lng = validated_data.pop("longitude")

        # GeoDjango Point(x=lng, y=lat)
        validated_data["location"] = Point(lng, lat)

        request = self.context["request"]
        validated_data["citizen"] = request.user

        return super().create(validated_data)

    def update(self, instance, validated_data):
        # Allow updating location optionally if you want. If you don’t, remove this.
        lat = validated_data.pop("latitude", None)
        lng = validated_data.pop("longitude", None)
        if lat is not None and lng is not None:
            instance.location = Point(lng, lat)

        return super().update(instance, validated_data)
