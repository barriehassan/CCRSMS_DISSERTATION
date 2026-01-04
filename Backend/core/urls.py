from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    # API (React citizens)
    CitizenComplaintViewSet,
    ComplaintCategoryViewSet,

    # Templates (Staff/Admin)
    StaffComplaintListView,
    StaffComplaintDetailView,
    StaffComplaintUpdateView,

    AdminComplaintListView,
    AdminComplaintDetailView,
    AdminComplaintUpdateView,
    AdminComplaintDeleteView,

    StaffComplaintsGeoJSONView, 
    AdminComplaintsGeoJSONView,

    AdminWardCountsView, 
    AdminCategoryCountsView, 
    AdminDailyCountsView
)

router = DefaultRouter()

# ============================
# ✅ API ROUTES (React Citizen)
# ============================
router.register(r"citizens/complaints", CitizenComplaintViewSet, basename="citizen-complaints")
router.register(r"complaint-categories", ComplaintCategoryViewSet, basename="complaint-categories")

urlpatterns = router.urls + [
    # ======================================
    # ✅ TEMPLATE ROUTES (Django Staff/Admin)
    # ======================================

    # Staff (same ward complaints)
    path("staff/complaints/", StaffComplaintListView.as_view(), name="staff_complaint_list"),
    path("staff/complaints/<int:pk>/", StaffComplaintDetailView.as_view(), name="staff_complaint_detail"),
    path("staff/complaints/<int:pk>/update/", StaffComplaintUpdateView.as_view(), name="staff_complaint_update"),
    path("staff/complaints.geojson", StaffComplaintsGeoJSONView.as_view(), name="staff_complaints_geojson"),

    # Admin (all complaints)
    path("admin/complaints/", AdminComplaintListView.as_view(), name="admin_complaint_list"),
    path("admin/complaints/<int:pk>/", AdminComplaintDetailView.as_view(), name="admin_complaint_detail"),
    path("admin/complaints/<int:pk>/update/", AdminComplaintUpdateView.as_view(), name="admin_complaint_update"),
    path("admin/complaints/<int:pk>/delete/", AdminComplaintDeleteView.as_view(), name="admin_complaint_delete"),
    path("admin/complaints.geojson", AdminComplaintsGeoJSONView.as_view(), name="admin_complaints_geojson"),
    path("admin/analytics/ward-counts/", AdminWardCountsView.as_view(), name="admin_agg_ward_counts"),
    path("admin/analytics/category-counts/", AdminCategoryCountsView.as_view(), name="admin_agg_category_counts"),
    path("admin/analytics/daily-counts/", AdminDailyCountsView.as_view(), name="admin_agg_daily_counts"),
]

