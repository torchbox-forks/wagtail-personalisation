from django.contrib import admin

from personalisation import models


class TimeRuleAdminInline(admin.TabularInline):
    model = models.TimeRule

class ReferralRuleAdminInline(admin.TabularInline):
    model = models.ReferralRule

class VisitCountRuleAdminInline(admin.TabularInline):
    model = models.VisitCountRule

class SegmentAdmin(admin.ModelAdmin):
    inlines = (TimeRuleAdminInline, ReferralRuleAdminInline, VisitCountRuleAdminInline)


admin.site.register(models.Segment, SegmentAdmin)