from django.contrib import admin

from wellness.models import (
    AuditLog,
    CaseRow,
    EnquiryModes,
    ImportEvent,
    Period,
    RawSubteamRow,
    SecondaryMetrics,
    User,
)


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("username", "email", "role", "is_active")
    list_filter = ("role", "is_active")
    search_fields = ("username", "email")


@admin.register(Period)
class PeriodAdmin(admin.ModelAdmin):
    list_display = ("id", "report_type", "period_start", "period_end", "status", "source", "created_at")
    list_filter = ("report_type", "status", "source")
    ordering = ("-period_start",)


@admin.register(CaseRow)
class CaseRowAdmin(admin.ModelAdmin):
    list_display = ("id", "period", "case_type", "vertical", "total_cases", "needs_review")
    list_filter = ("case_type", "vertical", "needs_review")


@admin.register(RawSubteamRow)
class RawSubteamRowAdmin(admin.ModelAdmin):
    list_display = ("id", "period", "case_type", "sub_team", "entry_no", "needs_review")
    list_filter = ("case_type", "sub_team", "needs_review")


@admin.register(SecondaryMetrics)
class SecondaryMetricsAdmin(admin.ModelAdmin):
    list_display = ("id", "period", "vertical", "total_sessions", "active_cases")


@admin.register(EnquiryModes)
class EnquiryModesAdmin(admin.ModelAdmin):
    list_display = ("id", "period", "mail", "calls_recd", "calls_out")


@admin.register(ImportEvent)
class ImportEventAdmin(admin.ModelAdmin):
    list_display = ("id", "period", "source", "original_filename", "rows_imported", "rows_warned", "rows_rejected", "imported_at")
    list_filter = ("source",)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at", "actor", "action", "target_type", "target_id")
    list_filter = ("action", "target_type")
    readonly_fields = ("actor", "action", "target_type", "target_id", "details", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
