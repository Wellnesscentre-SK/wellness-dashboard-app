"""URL routing for the wellness API."""

from django.http import JsonResponse
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from wellness import views
from wellness.serializers import UserSerializer
from wellness.views import MeView


def api_health(request):
    return JsonResponse({"status": "ok", "service": "wellness-backend"})

urlpatterns = [
    path("health", api_health, name="api-health"),
    path("auth/login", views.TokenObtainPairView.as_view(), name="login"),
    path("auth/refresh", TokenRefreshView.as_view(), name="refresh"),
    path("auth/me", MeView.as_view(), name="me"),
    path("imports/preview", views.ImportPreviewView.as_view(), name="import-preview"),
    path("imports/confirm", views.ImportConfirmView.as_view(), name="import-confirm"),
    path("imports/history", views.ImportHistoryView.as_view(), name="import-history"),
    path("periods", views.PeriodListView.as_view(), name="period-list"),
    path("periods/<int:period_id>", views.PeriodDetailView.as_view(), name="period-detail"),
    path("periods/<int:period_id>/worksheet", views.PeriodWorksheetView.as_view(), name="period-worksheet"),
    path("insights", views.InsightsView.as_view(), name="insights"),
    path("insights/compare", views.ComparisonInsightsView.as_view(), name="insights-compare"),
    path("insights/<int:period_id>", views.PeriodInsightsView.as_view(), name="period-insights"),
    path("entries", views.ManualEntryView.as_view(), name="manual-entry"),
    path("audit-logs", views.AuditLogView.as_view(), name="audit-logs"),
    path("reports/generate", views.ReportGenerateView.as_view(), name="report-generate"),
    path("reports/build", views.ReportCenterView.as_view(), name="report-center"),
    path("assistant/chat", views.AssistantView.as_view(), name="assistant-chat"),
    path("assistant/upload", views.AssistantUploadView.as_view(), name="assistant-upload"),
    path("ai/suggestions", views.AISuggestionsView.as_view(), name="ai-suggestions"),
    path("ai/action-plan", views.ActionPlanView.as_view(), name="action-plan"),
    path("ai/action-plan/<int:pk>", views.ActionPlanView.as_view(), name="action-plan-detail"),
    path("ai/export", views.AIInsightsExportView.as_view(), name="ai-export"),
]

