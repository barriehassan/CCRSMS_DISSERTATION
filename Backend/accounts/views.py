from rest_framework import viewsets, permissions
from rest_framework.response import Response
from knox.models import AuthToken
from django.contrib import messages
from django.shortcuts import render, redirect
from django.views.generic import TemplateView
from .serializers import CitizenRegisterSerializer, CitizenLoginSerializer, StaffAdminLoginSerializer, WardSerializer, UserPublicSerializer
from .mixins import KnoxSessionRequiredMixin, RoleRequiredMixin
from .notifications import send_welcome_email, send_welcome_sms
from django.contrib.auth import get_user_model, authenticate
from .forms import StaffAdminLoginForm
from core.models import Complaint, ComplaintCategory
from .models import Ward, Department
from core.views import SessionStaffUserMixin



User = get_user_model()


class CitizenRegisterViewset(viewsets.ViewSet):
    permission_classes = [permissions.AllowAny]
    queryset = User.objects.all()
    serializer_class = CitizenRegisterSerializer

    def create(self, request):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            user = serializer.save()  # custom create handles NIN/Passport & profile
            # Return user info in response
            try:
                send_welcome_email(user.email, user.first_name)
            except Exception as e:
                print(f"[EMAIL ERROR] {e}")

            try:
                send_welcome_sms(str(user.phone_number), user.first_name)
            except Exception as e:
                print(f"[SMS ERROR] {e}")

            return Response(serializer.data)
        else:
            return Response(serializer.errors, status=400)



class CitizenLoginViewset(viewsets.ViewSet):
    permission_classes = [permissions.AllowAny]
    serializer_class = CitizenLoginSerializer

    def create(self, request):
        serializer = self.serializer_class(data=request.data)
        
        if serializer.is_valid():
            identifier = serializer.validated_data['identifier']
            password = serializer.validated_data['password']

            # Use authenticate with custom backend supporting email or phone
            user = authenticate(request, identifier=identifier, password=password)

            if user:
                _, token = AuthToken.objects.create(user)
                return Response(
                    {
                        "user": UserPublicSerializer(user).data,
                        "token": token
                    }
                )
            else:
                return Response({"error": "Invalid Credentials"}, status=401)
            
        else:
            return Response(serializer.errors, status=400)


# =========================================================
# STAFF/ADMIN API (optional, still available)
# =========================================================

class StaffAdminLoginViewset(viewsets.ViewSet):
    permission_classes = [permissions.AllowAny]
    serializer_class = StaffAdminLoginSerializer

    def create(self, request):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            return Response(serializer.validated_data, status=200)
        return Response(serializer.errors, status=400)


# =========================================================
# STAFF/ADMIN TEMPLATE (Django UI)
# =========================================================
def staff_admin_login_view(request):
    form = StaffAdminLoginForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        serializer = StaffAdminLoginSerializer(
            data=form.cleaned_data,
            context={"request": request}
        )

        if serializer.is_valid():
            data = serializer.validated_data

            request.session["staff_token"] = str(data["token"])
            request.session["staff_token_key"] = str(data["token_key"])  # ✅ new
            request.session["user_type"] = data["user_type"]
            request.session["staff_user_id"] = data["user_id"]
            request.session.modified = True

            print("LOGIN OK:", data["email"], data["user_type"], "token_key:", data["token_key"])

            if data["user_type"] == "ADMIN":
                return redirect("admin_dashboard")
            return redirect("staff_dashboard")

        messages.error(request, serializer.errors.get("non_field_errors", ["Login failed"])[0])

    return render(request, "accounts/login.html", {"form": form})



def staff_logout_view(request):
    token_key = request.session.get("staff_token_key")
    if token_key:
        AuthToken.objects.filter(token_key=str(token_key)).delete()

    request.session.flush()
    return redirect("staff_login")


class StaffDashboardView(
    SessionStaffUserMixin, KnoxSessionRequiredMixin, RoleRequiredMixin, TemplateView):
    template_name = "dashboards/staff/staff-dashboard.html"
    required_role = "STAFF"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        qs = Complaint.objects.filter(citizen__ward=self.request.user.ward)

        ctx["categories"] = ComplaintCategory.objects.all().order_by("category_name")
        ctx["recent_complaints"] = qs.select_related("category", "citizen").order_by("-created_at")[:5]

        ctx["staff_stats"] = {
            "total": qs.count(),
            "submitted": qs.filter(status="SUBMITTED").count(),
            "in_progress": qs.filter(status="IN_PROGRESS").count(),
            "resolved": qs.filter(status="RESOLVED").count(),
        }
        return ctx


class AdminDashboardView(KnoxSessionRequiredMixin, RoleRequiredMixin, TemplateView):
    template_name = "dashboards/admin/admin-dashboard.html"
    required_role = "ADMIN"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        qs = Complaint.objects.all()

        ctx["categories"] = ComplaintCategory.objects.all().order_by("category_name")
        ctx["wards"] = Ward.objects.all().order_by("name")
        ctx["departments"] = Department.objects.all().order_by("name")

        ctx["admin_stats"] = {
            "total": qs.count(),
            "submitted": qs.filter(status="SUBMITTED").count(),
            "in_progress": qs.filter(status="IN_PROGRESS").count(),
            "resolved": qs.filter(status="RESOLVED").count(),
        }
        return ctx

class WardViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Ward.objects.all().order_by("name")
    serializer_class = WardSerializer
    permission_classes = [permissions.AllowAny]


