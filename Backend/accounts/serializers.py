from rest_framework import serializers
from django.contrib.auth import get_user_model, authenticate
from .validators import validate_nin, validate_passport
from knox.models import AuthToken
import re
from .models import Ward

User = get_user_model()


class CitizenRegisterSerializer(serializers.ModelSerializer):
    identity_number = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'phone_number', 'ward', 'password', 'identity_number')
        extra_kwargs = {'password': {'write_only': True}}

    def validate_identity_number(self, value):
        value = value.strip().upper()
        nin_pattern = r'^\d{2}[A-Z]\d[A-Z]{3}\d$'
        passport_pattern = r'^[A-Z]{2,3}\d{6}$'

        if re.fullmatch(nin_pattern, value):
            validate_nin(value)
            return {"type": "NIN", "value": value}
        if re.fullmatch(passport_pattern, value):
            validate_passport(value)
            return {"type": "PASSPORT", "value": value}

        raise serializers.ValidationError("Enter a valid Sierra Leone NIN or Passport number.")

    def create(self, validated_data):
        identity_data = validated_data.pop('identity_number')
        password = validated_data.pop('password')

        # Create the user
        user = User.objects.create_user(
            **validated_data,
            password=password,
            user_type="CITIZEN"
        )

        # Store NIN or Passport on CustomUser
        if identity_data['type'] == 'NIN':
            user.nin = identity_data['value']
        else:
            user.passport_number = identity_data['value']

        user.save()
        # Profile is automatically created by signals
        return user


class CitizenLoginSerializer(serializers.Serializer):
    identifier = serializers.CharField()
    password = serializers.CharField(write_only=True)


class StaffAdminLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs["email"].strip()
        password = attrs["password"]

        user = authenticate(username=email, password=password)
        if not user:
            raise serializers.ValidationError("Invalid credentials.")
        if not user.is_active:
            raise serializers.ValidationError("Account is inactive.")
        if user.user_type not in ("STAFF", "ADMIN"):
            raise serializers.ValidationError("Not authorized.")

        token_obj, token = AuthToken.objects.create(user)

        return {
            "token": token,
            "token_key": token_obj.token_key,   # ✅ save the real token_key
            "user_id": user.id,
            "user_type": user.user_type,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
        }



class WardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ward
        fields = ("id", "name")



class UserPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "first_name", "last_name", "email", "phone_number", "user_type")
