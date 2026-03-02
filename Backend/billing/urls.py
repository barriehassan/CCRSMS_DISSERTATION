from django.urls import path
from .views import (
    LocalTaxViewSet, 
    PaymentDataViewSet, 
    CityRateViewSet, 
    WasteCollectionViewSet,
    BusinessLicensePaymentViewSet,
    # STAFF
    StaffPaymentListView, StaffPaymentDetailView,
    StaffBillListView, StaffBillDetailView,
    CitizenBusinessViewSet,
    CitizenBusinessLicenseNoticeViewSet,
    StaffBusinessNoticeListView,
    StaffBusinessNoticeDetailView,
    StaffBusinessNoticeUpdateView,
    # ADMIN
    AdminPaymentListView, AdminPaymentDetailView,
    AdminBillListView, AdminBillDetailView, 
    AdminBusinessNoticeListView, 
    AdminBusinessNoticeDetailView, 
    AdminBusinessNoticeUpdateView,

)

from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register("local-tax", LocalTaxViewSet, basename="local-tax")
router.register("city-rate", CityRateViewSet, basename="city-rate")
router.register("waste-collection", WasteCollectionViewSet, basename="waste-collection")
router.register("business-license/payment", BusinessLicensePaymentViewSet, basename="business-license-payment")
# React (Citizen) APIs
router.register("citizens/businesses", CitizenBusinessViewSet, basename="citizen-businesses")
router.register("citizens/business-license/notices", CitizenBusinessLicenseNoticeViewSet, basename="citizen-business-license-notices")
router.register("payments", PaymentDataViewSet, basename="payment-data")



urlpatterns = router.urls + [
    # =========================
    # STAFF (WARD SCOPED)
    # =========================
    path("staff/payments/", StaffPaymentListView.as_view(), name="staff_payment_list"),
    path("staff/payments/<int:pk>/", StaffPaymentDetailView.as_view(), name="staff_payment_detail"),

    path("staff/bills/", StaffBillListView.as_view(), name="staff_bill_list"),
    path("staff/bills/<int:pk>/", StaffBillDetailView.as_view(), name="staff_bill_detail"),
        # Staff templates
    path("staff/business-license/notices/", StaffBusinessNoticeListView.as_view(), name="staff_business_notice_list"),
    path("staff/business-license/notices/<int:pk>/", StaffBusinessNoticeDetailView.as_view(), name="staff_business_notice_detail"),
    path("staff/business-license/notices/<int:pk>/update/", StaffBusinessNoticeUpdateView.as_view(), name="staff_business_notice_update"),

    # =========================
    # ADMIN (ALL)
    # =========================
    path("admin/payments/", AdminPaymentListView.as_view(), name="admin_payment_list"),
    path("admin/payments/<int:pk>/", AdminPaymentDetailView.as_view(), name="admin_payment_detail"),

    path("admin/bills/", AdminBillListView.as_view(), name="admin_bill_list"),
    path("admin/bills/<int:pk>/", AdminBillDetailView.as_view(), name="admin_bill_detail"),
    # ADMIN — Business License Notices
    path("admin/business-license/notices/", AdminBusinessNoticeListView.as_view(), name="admin_business_notice_list"),
    path("admin/business-license/notices/<int:pk>/", AdminBusinessNoticeDetailView.as_view(), name="admin_business_notice_detail"),
    path("admin/business-license/notices/<int:pk>/update/", AdminBusinessNoticeUpdateView.as_view(), name="admin_business_notice_update"),
    
]
