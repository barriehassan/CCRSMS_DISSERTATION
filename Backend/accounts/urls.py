from rest_framework.routers import DefaultRouter
from .views import CitizenRegisterViewset, CitizenLoginViewset, StaffAdminLoginViewset, staff_admin_login_view, staff_logout_view, StaffDashboardView, AdminDashboardView, WardViewSet
from django.urls import path, include


router = DefaultRouter()
router.register(r'citizens/register', CitizenRegisterViewset, basename='citizen-register')
router.register(r'citizens/login', CitizenLoginViewset, basename='citizen-login')
router.register(r'staff/login', StaffAdminLoginViewset, basename='staff-login')
router.register(r"wards", WardViewSet, basename="wards")

urlpatterns = [
    path("", staff_admin_login_view, name="staff_login"),
    
    path("staff/dashboard/", StaffDashboardView.as_view(), name="staff_dashboard"),

    path("council/admin/dashboard/", AdminDashboardView.as_view(), name="admin_dashboard"),
    
    path("staff/logout/", staff_logout_view, name="staff_logout"),

    # ✅ ALL APIs live under /api/
    path("api/", include(router.urls)),

]
