from django.shortcuts import render
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, UpdateView, DeleteView

from rest_framework import viewsets, permissions
from rest_framework.parsers import MultiPartParser, FormParser

from accounts.mixins import KnoxSessionRequiredMixin, RoleRequiredMixin

from .models import Complaint, ComplaintCategory
from .serializers import ComplaintSerializer, ComplaintCategorySerializer
from .notifications import (
    notify_citizen_complaint_created,
    notify_staff_complaint_created,
    notify_citizen_complaint_updated,
    notify_staff_complaint_updated,
    notify_citizen_complaint_deleted
)
from .permissions import IsCitizen, IsOwnerCitizen, CitizenCanEditOnlyWhenSubmitted
from .forms import StaffComplaintUpdateForm, AdminComplaintUpdateForm
from django.db.models import Q
from django.http import JsonResponse
from django.core.serializers import serialize
from django.utils.dateparse import parse_date
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
import json
from django.db.models import Count
from django.db.models.functions import TruncDate



# Create your views here.

User = get_user_model()


# =========================================================
# API (REACT) — CITIZEN COMPLAINT CRUD
# =========================================================

class CitizenComplaintViewSet(viewsets.ModelViewSet):
    """
    Citizens use React:
    - Create complaint (with evidence + lat/lng handled in serializer)
    - List only their own complaints
    - Retrieve only their own complaint
    - Update only their own complaint
    - Delete only their own complaint
    """
    serializer_class = ComplaintSerializer
    permission_classes = [
            permissions.IsAuthenticated, 
            IsCitizen, 
            IsOwnerCitizen, 
            CitizenCanEditOnlyWhenSubmitted
        ]
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        return Complaint.objects.filter(citizen=self.request.user).order_by("-created_at")

    def perform_create(self, serializer):
        # citizen is set from request.user (either here or inside serializer)
        complaint = serializer.save(citizen=self.request.user)

        # Notifications: citizen + staff in same ward
        try:
            notify_citizen_complaint_created(complaint)
        except Exception as e:
            print("[COMPLAINT EMAIL ERROR] citizen create:", e)

        try:
            notify_staff_complaint_created(complaint)
        except Exception as e:
            print("[COMPLAINT EMAIL ERROR] staff ward create:", e)

    def perform_update(self, serializer):
        complaint = serializer.save()

        # Notifications: citizen + staff in ward (updated by CITIZEN)
        try:
            notify_citizen_complaint_updated(complaint, updated_by="CITIZEN")
        except Exception as e:
            print("[COMPLAINT EMAIL ERROR] citizen update:", e)

        try:
            notify_staff_complaint_updated(complaint, updated_by="CITIZEN")
        except Exception as e:
            print("[COMPLAINT EMAIL ERROR] staff ward update:", e)

    def destroy(self, request, *args, **kwargs):
        complaint = self.get_object()  # ensures it belongs to this citizen (via queryset)
        complaint_title = complaint.title

        response = super().destroy(request, *args, **kwargs)

        # Notify after deletion
        try:
            notify_citizen_complaint_deleted(request.user, complaint_title)
        except Exception as e:
            print("[COMPLAINT EMAIL ERROR] citizen delete:", e)

        return response


class ComplaintCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Public categories (React dropdown)
    """
    queryset = ComplaintCategory.objects.all().order_by("category_name")
    serializer_class = ComplaintCategorySerializer
    permission_classes = [permissions.AllowAny]


# =========================================================
# TEMPLATE (DJANGO UI) — STAFF / ADMIN
# =========================================================

class SessionStaffUserMixin:
    """
    Attaches the logged-in staff/admin user object to request.user
    using session staff_user_id saved at login.

    Requires in staff login view:
        request.session["staff_user_id"] = data["user_id"]
    """
    def dispatch(self, request, *args, **kwargs):
        staff_user_id = request.session.get("staff_user_id")
        if not staff_user_id:
            request.session.flush()
            return redirect("staff_login")

        user = User.objects.filter(id=staff_user_id).first()
        if not user:
            request.session.flush()
            return redirect("staff_login")

        request.user = user
        return super().dispatch(request, *args, **kwargs)


# -----------------------------
# STAFF: LIST + DETAIL
# -----------------------------

class StaffComplaintListView(
    SessionStaffUserMixin, KnoxSessionRequiredMixin, RoleRequiredMixin, ListView
):
    template_name = "dashboards/staff/complaints.html"
    context_object_name = "complaints"
    required_role = "STAFF"
    paginate_by = 10  # ✅ pagination

    def get_queryset(self):
        qs = Complaint.objects.filter(citizen__ward=self.request.user.ward).select_related("category", "citizen").order_by("-created_at")

        q = self.request.GET.get("q", "").strip()
        status = self.request.GET.get("status", "").strip()
        priority = self.request.GET.get("priority", "").strip()
        category = self.request.GET.get("category", "").strip()

        if q:
            # allow searching by id OR title
            qs = qs.filter(
                Q(title__icontains=q) |
                Q(id__icontains=q)
            )

        if status:
            qs = qs.filter(status=status)

        if priority:
            qs = qs.filter(priority_level=priority)

        if category:
            qs = qs.filter(category_id=category)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["categories"] = ComplaintCategory.objects.all().order_by("category_name")
        return ctx



class StaffComplaintDetailView(
    SessionStaffUserMixin, KnoxSessionRequiredMixin, RoleRequiredMixin, DetailView
):
    template_name = "dashboards/staff/complaint_detail.html"
    model = Complaint
    context_object_name = "complaint"
    required_role = "STAFF"

    def get_queryset(self):
        return Complaint.objects.filter(citizen__ward=self.request.user.ward)

class StaffComplaintUpdateView(
    SessionStaffUserMixin, KnoxSessionRequiredMixin, RoleRequiredMixin, UpdateView):
    template_name = "dashboards/staff/complaint_update.html"
    model = Complaint
    context_object_name = "complaint"
    required_role = "STAFF"
    form_class = StaffComplaintUpdateForm 

    def get_queryset(self):
        return Complaint.objects.filter(citizen__ward=self.request.user.ward)

    def form_valid(self, form):
        complaint = form.save()

        # notify citizen when staff updates
        try:
            notify_citizen_complaint_updated(complaint, updated_by="COUNCIL STAFF")
        except Exception as e:
            print("[EMAIL ERROR] citizen notified staff update:", e)

        messages.success(self.request, "Complaint updated successfully.")
        return redirect("staff_complaint_detail", pk=complaint.pk)


# -----------------------------
# ADMIN: LIST + DETAIL + UPDATE + DELETE
# -----------------------------

class AdminComplaintListView(
    SessionStaffUserMixin, KnoxSessionRequiredMixin, RoleRequiredMixin, ListView
):
    template_name = "dashboards/admin/complaints.html"
    context_object_name = "complaints"
    required_role = "ADMIN"
    paginate_by = 10  # ✅ pagination

    def get_queryset(self):
        qs = Complaint.objects.all().select_related("category", "citizen").order_by("-created_at")

        q = self.request.GET.get("q", "").strip()
        status = self.request.GET.get("status", "").strip()
        category = self.request.GET.get("category", "").strip()

        if q:
            qs = qs.filter(
                Q(title__icontains=q) |
                Q(description__icontains=q) |
                Q(id__icontains=q) |
                Q(citizen__first_name__icontains=q) |
                Q(citizen__last_name__icontains=q) |
                Q(citizen__email__icontains=q)
            )

        if status:
            qs = qs.filter(status=status)

        if category:
            qs = qs.filter(category_id=category)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["categories"] = ComplaintCategory.objects.all().order_by("category_name")
        return ctx



class AdminComplaintDetailView(
    SessionStaffUserMixin, KnoxSessionRequiredMixin, RoleRequiredMixin, DetailView
):
    template_name = "dashboards/admin/complaint_detail.html"
    model = Complaint
    context_object_name = "complaint"
    required_role = "ADMIN"


class AdminComplaintUpdateView(
    SessionStaffUserMixin, KnoxSessionRequiredMixin, RoleRequiredMixin, UpdateView
):
    template_name = "dashboards/admin/complaint_update.html"
    model = Complaint
    context_object_name = "complaint"
    required_role = "ADMIN"
    form_class = AdminComplaintUpdateForm 

    def form_valid(self, form):
        complaint = form.save()

        # Notify citizen of admin update (+ optionally staff ward)
        try:
            notify_citizen_complaint_updated(complaint, updated_by="ADMIN")
        except Exception as e:
            print("[COMPLAINT EMAIL ERROR] citizen notified admin update:", e)

        messages.success(self.request, "Complaint updated successfully.")
        return redirect("admin_complaint_detail", pk=complaint.pk)


class AdminComplaintDeleteView(
    SessionStaffUserMixin, KnoxSessionRequiredMixin, RoleRequiredMixin, DeleteView
):
    template_name = "dashboards/admin/complaint_confirm_delete.html"
    model = Complaint
    context_object_name = "complaint"
    required_role = "ADMIN"
    success_url = reverse_lazy("admin_complaint_list")

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Complaint deleted successfully.")
        return super().delete(request, *args, **kwargs)


@method_decorator(never_cache, name="dispatch")
class StaffComplaintsGeoJSONView(SessionStaffUserMixin, KnoxSessionRequiredMixin, RoleRequiredMixin, View):
    required_role = "STAFF"

    def get(self, request, *args, **kwargs):
        qs = Complaint.objects.filter(citizen__ward=request.user.ward).select_related("citizen", "category")

        qs = apply_complaint_filters(qs, request, allow_admin_filters=False)

        geojson = serialize(
            "geojson",
            qs,
            geometry_field="location",
            fields=("title", "status", "priority_level", "created_at"),
        )
        data = json.loads(geojson)
        for feat in data.get("features", []):
            pk = feat["properties"].get("pk")
            complaint = qs.filter(pk=pk).first()
            if complaint:
                feat["properties"]["complaint_id"] = complaint.pk
                feat["properties"]["category"] = complaint.category.category_name if complaint.category else ""
                feat["properties"]["citizen_name"] = f"{complaint.citizen.first_name} {complaint.citizen.last_name}".strip()
        return JsonResponse(data, safe=False)


@method_decorator(never_cache, name="dispatch")
class AdminComplaintsGeoJSONView(SessionStaffUserMixin, KnoxSessionRequiredMixin, RoleRequiredMixin, View):
    required_role = "ADMIN"

    def get(self, request, *args, **kwargs):
        qs = Complaint.objects.all().select_related("citizen", "category", "category__department")

        qs = apply_complaint_filters(qs, request, allow_admin_filters=True)

        geojson = serialize(
            "geojson",
            qs,
            geometry_field="location",
            fields=("title", "status", "priority_level", "created_at"),
        )
        data = json.loads(geojson)
        for feat in data.get("features", []):
            pk = feat["properties"].get("pk")
            complaint = qs.filter(pk=pk).first()
            if complaint:
                feat["properties"]["complaint_id"] = complaint.pk
                feat["properties"]["category"] = complaint.category.category_name if complaint.category else ""
                feat["properties"]["citizen_name"] = f"{complaint.citizen.first_name} {complaint.citizen.last_name}".strip()
        return JsonResponse(data, safe=False)


def apply_complaint_filters(qs, request, allow_admin_filters: bool):
    q_status = request.GET.get("status", "").strip()
    q_priority = request.GET.get("priority", "").strip()
    q_category = request.GET.get("category", "").strip()

    date_from = parse_date(request.GET.get("date_from", "") or "")
    date_to = parse_date(request.GET.get("date_to", "") or "")

    if q_status:
        qs = qs.filter(status=q_status)
    if q_priority:
        qs = qs.filter(priority_level=q_priority)
    if q_category:
        qs = qs.filter(category_id=q_category)

    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)

    if allow_admin_filters:
        ward_id = request.GET.get("ward", "").strip()
        dept_id = request.GET.get("department", "").strip()

        if ward_id:
            qs = qs.filter(citizen__ward_id=ward_id)
        if dept_id:
            qs = qs.filter(category__department_id=dept_id)

    return qs


class AdminWardCountsView(View):
    def get(self, request):
        data = (
            Complaint.objects
            .values("citizen__ward__name")
            .annotate(total=Count("id"))
            .order_by("-total")
        )
        return JsonResponse(list(data), safe=False)


class AdminCategoryCountsView(View):
    def get(self, request):
        data = (
            Complaint.objects
            .values("category__category_name")
            .annotate(total=Count("id"))
            .order_by("-total")
        )
        return JsonResponse(list(data), safe=False)


class AdminDailyCountsView(View):
    def get(self, request):
        data = (
            Complaint.objects
            .annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(total=Count("id"))
            .order_by("day")
        )
        # Convert date to string for JSON
        data = [{"day": str(x["day"]), "total": x["total"]} for x in data]
        return JsonResponse(data, safe=False)

