from django.shortcuts import redirect
from knox.models import AuthToken
from django.utils import timezone


class KnoxSessionRequiredMixin:
    login_url = "staff_login"

    def dispatch(self, request, *args, **kwargs):
        token_key = request.session.get("staff_token_key")
        if not token_key:
            request.session.flush()
            return redirect(self.login_url)

            print("SESSION:", dict(request.session))

        # ✅ Token must exist and not be expired
        is_valid = AuthToken.objects.filter(
            token_key=str(token_key),
            expiry__gt=timezone.now()
        ).exists()

        if not is_valid:
            AuthToken.objects.filter(token_key=str(token_key)).delete()
            request.session.flush()
            return redirect(self.login_url)

        return super().dispatch(request, *args, **kwargs)


class RoleRequiredMixin:
    """
    Ensures user_type matches required role.
    """
    required_role = None  # "STAFF" or "ADMIN"

    def dispatch(self, request, *args, **kwargs):
        if request.session.get("user_type") != self.required_role:
            request.session.flush()
            return redirect("staff_login")

        return super().dispatch(request, *args, **kwargs)


class SessionUserMixin:
    def dispatch(self, request, *args, **kwargs):
        uid = request.session.get("staff_user_id")
        if uid:
            request.user = User.objects.filter(id=uid).first()  # attach
        return super().dispatch(request, *args, **kwargs)