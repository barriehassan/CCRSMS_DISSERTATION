from django.contrib.auth import get_user_model
from phonenumber_field.phonenumber import PhoneNumber

User = get_user_model()

class EmailOrPhoneBackend:
    def authenticate(self, request, identifier=None, password=None, **kwargs):
        if not identifier or not password:
            return None

        identifier = str(identifier).strip()

        user = None

        # Email path
        if "@" in identifier:
            user = User.objects.filter(email__iexact=identifier).first()
        else:
            # Phone path: normalize to PhoneNumber (E.164)
            try:
                phone = PhoneNumber.from_string(phone_number=identifier, region="SL")
                # Some versions need .as_e164, others str(phone) is E.164
                user = User.objects.filter(phone_number=phone).first()
            except Exception:
                # fallback - try raw string (in case DB has raw)
                user = User.objects.filter(phone_number=identifier).first()

        if not user:
            return None
        if not user.is_active:
            return None

        return user if user.check_password(password) else None

    def get_user(self, user_id):
        return User.objects.filter(pk=user_id).first()
