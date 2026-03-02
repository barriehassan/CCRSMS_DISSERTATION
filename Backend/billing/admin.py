from django.contrib import admin
from .models import *

# Register your models here.

admin.site.register(Bill)
admin.site.register(Payment)
admin.site.register(WastePlan)
admin.site.register(WasteCoverage)
admin.site.register(WasteServiceProvider)
admin.site.register(WasteBlockProvider)
admin.site.register(WasteBlock)
admin.site.register(WasteWardMeta)
admin.site.register(Business)
admin.site.register(BusinessLicenseDemandNotice)

