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
)
from .permissions import *


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

    def get_queryset(self):
        # Staff sees complaints where citizen ward == staff ward
        return Complaint.objects.filter(
            citizen__ward=self.request.user.ward
        ).order_by("-created_at")


class StaffComplaintDetailView(
    SessionStaffUserMixin, KnoxSessionRequiredMixin, RoleRequiredMixin, DetailView
):
    template_name = "complaints/staff/complaint_detail.html"
    model = Complaint
    context_object_name = "complaint"
    required_role = "STAFF"

    def get_queryset(self):
        return Complaint.objects.filter(citizen__ward=self.request.user.ward)

class StaffComplaintUpdateView(SessionStaffUserMixin, KnoxSessionRequiredMixin, RoleRequiredMixin, UpdateView):
    template_name = "complaints/staff/complaint_update.html"
    model = Complaint
    context_object_name = "complaint"
    required_role = "STAFF"
    fields = ("status", "priority_level")

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

    def get_queryset(self):
        return Complaint.objects.all().order_by("-created_at")


class AdminComplaintDetailView(
    SessionStaffUserMixin, KnoxSessionRequiredMixin, RoleRequiredMixin, DetailView
):
    template_name = "complaints/admin/complaint_detail.html"
    model = Complaint
    context_object_name = "complaint"
    required_role = "ADMIN"


class AdminComplaintUpdateView(
    SessionStaffUserMixin, KnoxSessionRequiredMixin, RoleRequiredMixin, UpdateView
):
    template_name = "complaints/admin/complaint_update.html"
    model = Complaint
    context_object_name = "complaint"
    required_role = "ADMIN"

    # admin can update more fields (adjust as needed)
    fields = ("status", "priority_level", "category", "title", "description")

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
    template_name = "complaints/admin/complaint_confirm_delete.html"
    model = Complaint
    required_role = "ADMIN"
    success_url = reverse_lazy("admin_complaint_list")

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Complaint deleted successfully.")
        return super().delete(request, *args, **kwargs)
