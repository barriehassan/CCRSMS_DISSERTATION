from django.urls import path
from .views import  LocalTaxViewSet, PaymentDataViewSet, CityRateViewSet
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register("local-tax", LocalTaxViewSet, basename="local-tax")
router.register("city-rate", CityRateViewSet, basename="city-rate")
router.register("payments", PaymentDataViewSet, basename="payment-data")


urlpatterns = router.urls