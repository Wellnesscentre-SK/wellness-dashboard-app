"""API views."""

import io
import json
import uuid
from datetime import date, timedelta

from django.conf import settings
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.http import FileResponse
from rest_framework import status as http_status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from wellness.models import ActionPlan, ImportEvent, Period
from wellness.permissions import IsAdmin
from wellness.serializers import (
    ActionPlanSerializer,
    ImportEventSerializer,
    PeriodSerializer,
    UserSerializer,
    build_preview_payload,
)
from wellness.services import parsing as P
from wellness.services.persistence import (
    DuplicatePeriodError,
    active_period_for,
    save_import,
)

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def weekly_comparison_state(current, previous):
    """Describe coverage without pretending calendar weeks are always seven days."""
    if previous is None:
        return "unavailable"
    if previous.period_end >= current.period_start:
        return "overlap"
    current_days = (current.period_end - current.period_start).days + 1
    previous_days = (previous.period_end - previous.period_start).days + 1
    if previous.period_end + timedelta(days=1) != current.period_start:
        return "gap"
    if current_days != 7 or previous_days != 7:
        return "partial"
    return "adjacent"


def immediately_previous_weekly(period):
    return (
        Period.objects.filter(
            report_type=Period.ReportType.WEEKLY,
            period_end__lt=period.period_start,
            superseded_by__isnull=True,
        )
        .order_by("-period_end", "-period_start")
        .first()
    )


def _error(code, message, extra=None, http_status_code=http_status.HTTP_400_BAD_REQUEST):
    payload = {"error": code, "message": message}
    if extra:
        payload.update(extra)
    return Response(payload, status=http_status_code)


class MeView(APIView):
    def get(self, request):
        return Response(UserSerializer(request.user).data)


class ImportPreviewView(APIView):
    permission_classes = (IsAdmin,)

    def post(self, request):
        file = request.FILES.get("file")
        if not file:
            return _error("MISSING_FILE", "No file was uploaded.")
        if not file.name.lower().endswith((".xlsx", ".xls")):
            return _error("INVALID_FILE_TYPE", "Only .xlsx / .xls files are supported.")
        if file.size > MAX_UPLOAD_BYTES:
            return _error("FILE_TOO_LARGE", "File exceeds the 10 MB limit.")

        data = file.read()
        try:
            report = P.parse_excel(data)
        except P.SheetStructureError as exc:
            return _error(exc.code, exc.message)

        dup = active_period_for(report.report_type, report.period_start, report.period_end)
        preview_id = str(uuid.uuid4())
        cache.set(
            f"import_preview:{preview_id}",
            {"report": report, "filename": file.name, "raw": data},
            settings.IMPORT_PREVIEW_TTL,
        )

        payload = build_preview_payload(report, duplicate_period=dup)
        payload["preview_id"] = preview_id
        return Response(payload)


class ImportConfirmView(APIView):
    permission_classes = (IsAdmin,)

    def post(self, request):
        preview_id = request.data.get("preview_id")
        replace = request.data.get("replace", False)
        if isinstance(replace, str):
            replace = replace.strip().lower() in ("1", "true", "yes", "on")
        else:
            replace = bool(replace)
        if not preview_id:
            return _error("MISSING_PREVIEW_ID", "preview_id is required.")

        key = f"import_preview:{preview_id}"
        cached = cache.get(key)
        if cached is None:
            return _error("PREVIEW_EXPIRED", "This preview has expired. Re-upload the file.", http_status_code=http_status.HTTP_409_CONFLICT)

        # A duplicate must not consume the preview: the caller may retry the
        # same upload with replace=true without re-uploading the file.
        report = cached["report"]
        dup = active_period_for(report.report_type, report.period_start, report.period_end)
        if dup and not replace:
            return _error(
                P.ERR_DUPLICATE_PERIOD,
                "A report for this exact period already exists. Replace it, or pick a different file.",
                extra={"existing_period_id": dup.id},
                http_status_code=http_status.HTTP_409_CONFLICT,
            )

        # Consume the preview so it cannot be confirmed twice.
        cache.delete(key)

        try:
            with transaction.atomic():
                imp = save_import(
                    report=report,
                    user=request.user,
                    filename=cached["filename"],
                    raw_bytes=cached["raw"],
                    replace=replace,
                )
        except DuplicatePeriodError as exc:
            # Rare race: an active period appeared after our pre-check above.
            return _error(
                P.ERR_DUPLICATE_PERIOD,
                "A report for this exact period already exists. Replace it, or pick a different file.",
                extra={"existing_period_id": exc.existing.id},
                http_status_code=http_status.HTTP_409_CONFLICT,
            )

        period = Period.objects.get(pk=imp.period_id)
        return Response({
            "period_id": period.id,
            "status": period.status,
            "import_id": imp.id,
            "rows_imported": imp.rows_imported,
            "rows_warned": imp.rows_warned,
            "rows_rejected": imp.rows_rejected,
            "report_type": period.report_type,
            "period_start": period.period_start.isoformat(),
            "period_end": period.period_end.isoformat(),
        })


class PeriodListView(APIView):
    permission_classes = (IsAdmin,)

    def get(self, request):
        qs = (
            Period.objects.filter(superseded_by__isnull=True)
            .select_related("created_by")
            .order_by("-period_start", "-id")
        )
        report_type = request.query_params.get("report_type")
        if report_type:
            qs = qs.filter(report_type=report_type)
        status = request.query_params.get("status")
        if status:
            qs = qs.filter(status=status)
        qs = qs.prefetch_related("case_rows", "raw_rows", "secondary_metrics").select_related("enquiry_modes")
        return Response(PeriodSerializer(qs, many=True).data)

    def post(self, request):
        from wellness.services.persistence import log_audit

        data = request.data
        report_type = str(data.get("report_type") or "").lower()
        period_start = data.get("period_start")
        period_end = data.get("period_end")
        status = str(data.get("status") or Period.Status.COMPLETE).lower()
        source = str(data.get("source") or Period.Source.MANUAL).lower()

        if report_type not in (Period.ReportType.WEEKLY, Period.ReportType.MONTHLY):
            return _error("INVALID_REPORT_TYPE", "report_type must be 'weekly' or 'monthly'.")
        if not period_start or not period_end:
            return _error("INVALID_DATES", "period_start and period_end are required.")
        try:
            start = date.fromisoformat(str(period_start))
            end = date.fromisoformat(str(period_end))
        except ValueError:
            return _error("INVALID_DATES", "Dates must be in YYYY-MM-DD format.")
        if start > end:
            return _error("INVALID_DATES", "period_start must be on or before period_end.")
        if status not in (s.value for s in Period.Status):
            return _error("INVALID_STATUS", "status must be complete, incomplete, or needs_review.")
        if source not in (s.value for s in Period.Source):
            return _error("INVALID_SOURCE", "source must be upload or manual.")

        try:
            with transaction.atomic():
                period = Period.objects.create(
                    report_type=report_type,
                    period_start=start,
                    period_end=end,
                    status=status,
                    source=source,
                    title=str(data.get("title") or "").strip(),
                    created_by=request.user,
                )
        except IntegrityError:
            return _error(
                "PERIOD_EXISTS",
                "A period for this exact range and type already exists.",
                http_status_code=http_status.HTTP_409_CONFLICT,
            )

        log_audit(request.user, "period_created", "period", period.id, {
            "report_type": report_type,
            "period_start": str(start),
            "period_end": str(end),
            "status": status,
            "source": source,
        })

        qs = (
            Period.objects.filter(pk=period.pk)
            .prefetch_related("case_rows", "raw_rows", "secondary_metrics")
            .select_related("enquiry_modes")
        )
        return Response(PeriodSerializer(qs.first()).data, status=http_status.HTTP_201_CREATED)


class PeriodDetailView(APIView):
    permission_classes = (IsAdmin,)

    def _get_period(self, period_id):
        return Period.objects.filter(pk=period_id, superseded_by__isnull=True).first()

    def _full_response(self, period):
        qs = (
            Period.objects.filter(pk=period.pk)
            .prefetch_related("case_rows", "raw_rows", "secondary_metrics")
            .select_related("enquiry_modes")
        )
        return Response(PeriodSerializer(qs.first()).data)

    def get(self, request, period_id):
        period = self._get_period(period_id)
        if period is None:
            return _error("PERIOD_NOT_FOUND", "Period not found or already replaced.")
        return self._full_response(period)

    def patch(self, request, period_id):
        from wellness.services.persistence import log_audit

        period = self._get_period(period_id)
        if period is None:
            return _error("PERIOD_NOT_FOUND", "Period not found or already replaced.")

        data = request.data
        report_type = str(data.get("report_type") or period.report_type).lower()
        status = str(data.get("status") or period.status).lower()
        source = str(data.get("source") or period.source).lower()
        try:
            new_start = date.fromisoformat(str(data.get("period_start") or period.period_start.isoformat()))
            new_end = date.fromisoformat(str(data.get("period_end") or period.period_end.isoformat()))
        except ValueError:
            return _error("INVALID_DATES", "Dates must be in YYYY-MM-DD format.")

        if report_type not in (Period.ReportType.WEEKLY, Period.ReportType.MONTHLY):
            return _error("INVALID_REPORT_TYPE", "report_type must be 'weekly' or 'monthly'.")
        if new_start > new_end:
            return _error("INVALID_DATES", "period_start must be on or before period_end.")
        if status not in (s.value for s in Period.Status):
            return _error("INVALID_STATUS", "status must be complete, incomplete, or needs_review.")
        if source not in (s.value for s in Period.Source):
            return _error("INVALID_SOURCE", "source must be upload or manual.")

        try:
            with transaction.atomic():
                period.report_type = report_type
                period.period_start = new_start
                period.period_end = new_end
                period.status = status
                period.source = source
                if "title" in data:
                    period.title = str(data.get("title") or "").strip()
                period.save()
        except IntegrityError:
            return _error(
                "PERIOD_EXISTS",
                "Another active period already covers this exact range and type.",
                http_status_code=http_status.HTTP_409_CONFLICT,
            )

        log_audit(request.user, "period_updated", "period", period.id, {
            "report_type": report_type,
            "period_start": new_start.isoformat(),
            "period_end": new_end.isoformat(),
            "status": status,
            "source": source,
        })
        return self._full_response(period)

    def delete(self, request, period_id):
        from django.db import transaction
        from django.db.models import F

        from wellness.services.persistence import log_audit

        period = self._get_period(period_id)
        if period is None:
            return _error("PERIOD_NOT_FOUND", "Period not found or already replaced.")

        log_audit(request.user, "period_deleted", "period", period.id, {
            "report_type": period.report_type,
            "period_start": period.period_start.isoformat(),
            "period_end": period.period_end.isoformat(),
        })
        with transaction.atomic():
            dep_pks = list(
                Period.objects.filter(superseded_by_id=period.pk)
                .values_list("pk", flat=True)
            )
            if dep_pks:
                # Park dependents on themselves so they stay inactive while the
                # row is deleted; otherwise SET_NULL re-activates a hidden twin
                # with the identical (type, start, end) and trips uniq_active_period.
                Period.objects.filter(pk__in=dep_pks).update(superseded_by=F("id"))
                period.delete()
                Period.objects.filter(pk__in=dep_pks).update(superseded_by=None)
            else:
                period.delete()
        return Response(status=http_status.HTTP_204_NO_CONTENT)


class ManualEntryView(APIView):
    permission_classes = (IsAdmin,)

    def post(self, request):
        from wellness.services.persistence import ValidationFailedError, save_manual_entry

        period = Period.objects.filter(
            pk=request.data.get("period_id"), superseded_by__isnull=True
        ).first()
        if period is None:
            return _error("PERIOD_NOT_FOUND", "Period not found or already replaced.")

        if period.status == Period.Status.INCOMPLETE:
            return _error("PERIOD_INCOMPLETE", "Complete the import before adding manual entries.")

        force = bool(request.data.get("force_save_with_warnings", False))
        try:
            raw, case_row, checks = save_manual_entry(
                period=period,
                case_type=request.data.get("case_type", "new"),
                sub_team=request.data.get("sub_team", ""),
                columns=request.data.get("columns", {}),
                user=request.user,
                force_save_with_warnings=force,
            )
        except ValidationFailedError as exc:
            return _error(
                P.ERR_ROW_VALIDATION,
                exc.message,
                extra={
                    "checks": [
                        {"name": c.name, "passed": c.passed, "expected": c.expected,
                         "actual": c.actual, "off_by": c.off_by}
                        for c in exc.checks
                    ],
                },
                http_status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        except PermissionError as exc:
            return _error("PERIOD_REPLACED", str(exc))

        return Response({
            "entry_no": raw.entry_no,
            "period_id": period.id,
            "case_type": raw.case_type,
            "sub_team": raw.sub_team,
            "case_row_id": case_row.id,
            "vertical": case_row.vertical,
            "needs_review": raw.needs_review,
            "checks": [
                {"name": c.name, "passed": c.passed, "expected": c.expected,
                 "actual": c.actual, "off_by": c.off_by}
                for c in checks
            ],
        })


class PeriodWorksheetView(APIView):
    permission_classes = (IsAdmin,)

    def get(self, request, period_id):
        from wellness.models import AuditLog
        period = Period.objects.filter(pk=period_id, superseded_by__isnull=True).first()
        if not period:
            return _error("PERIOD_NOT_FOUND", "Period not found.")

        # Raw rows are an append-only version log; serve only the newest
        # version per (case_type, sub_team) so stale values never surface.
        latest = {}
        for r in period.raw_rows.order_by("created_at", "id"):
            latest[(r.case_type, r.sub_team)] = r
        rows = sorted(latest.values(), key=lambda r: (r.case_type, r.sub_team))
        raw_rows_data = [
            {
                "case_type": r.case_type,
                "sub_team": r.sub_team,
                "raw_payload": r.raw_payload,
                "check_results": r.check_results,
                "needs_review": r.needs_review,
                "reason": r.reason,
            }
            for r in rows
        ]

        audits = AuditLog.objects.filter(
            details__period_id=period.id
        ).select_related("actor").order_by("-created_at")[:50]

        audit_data = [
            {
                "id": a.id,
                "actor": a.actor.username if a.actor else "System",
                "action": a.action,
                "target_type": a.target_type,
                "details": a.details,
                "created_at": a.created_at.isoformat(),
            }
            for a in audits
        ]

        return Response({
            "period": {
                "id": period.id,
                "report_type": period.report_type,
                "period_start": period.period_start.isoformat(),
                "period_end": period.period_end.isoformat(),
                "status": period.status,
            },
            "raw_rows": raw_rows_data,
            "audit_logs": audit_data,
        })

    def post(self, request, period_id):
        from wellness.services.persistence import ValidationFailedError, bulk_save_manual_entries

        period = Period.objects.filter(pk=period_id, superseded_by__isnull=True).first()
        if not period:
            return _error("PERIOD_NOT_FOUND", "Period not found.")

        rows_data = request.data.get("rows", [])
        force = bool(request.data.get("force_save_with_warnings", False))

        try:
            saved_raws, all_checks = bulk_save_manual_entries(
                period=period,
                rows_data=rows_data,
                user=request.user,
                force_save_with_warnings=force,
            )
        except ValidationFailedError as exc:
            return _error(
                P.ERR_ROW_VALIDATION,
                exc.message,
                http_status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        except PermissionError as exc:
            return _error("PERIOD_REPLACED", str(exc))

        return Response({
            "status": period.status,
            "saved_count": len(saved_raws),
            "checks": {
                key: [
                    {"name": c.name, "passed": c.passed, "expected": c.expected, "actual": c.actual, "off_by": c.off_by}
                    for c in check_list
                ]
                for key, check_list in all_checks.items()
            },
        })


class AuditLogView(APIView):
    permission_classes = (IsAdmin,)

    def get(self, request):
        from wellness.models import AuditLog
        period_id = request.query_params.get("period_id")
        qs = AuditLog.objects.select_related("actor").order_by("-created_at")
        if period_id:
            try:
                period_pk = int(period_id)
            except (TypeError, ValueError):
                return _error("INVALID_PERIOD_ID", "period_id must be an integer.")
            qs = qs.filter(details__period_id=period_pk)
        logs = [
            {
                "id": a.id,
                "actor": a.actor.username if a.actor else "System",
                "action": a.action,
                "target_type": a.target_type,
                "details": a.details,
                "created_at": a.created_at.isoformat(),
            }
            for a in qs[:100]
        ]
        return Response(logs)



class InsightsView(APIView):
    permission_classes = (IsAdmin,)

    def get(self, request):
        from wellness.services.insights import active_periods, analyze_all

        return Response(analyze_all(active_periods()))


class PeriodInsightsView(APIView):
    permission_classes = (IsAdmin,)

    def get(self, request, period_id):
        from wellness.services.insights import analyze_period

        period = Period.objects.filter(pk=period_id, superseded_by__isnull=True).first()
        if period is None:
            return _error("PERIOD_NOT_FOUND", "Period not found or already replaced.")

        previous = None
        if period.report_type == Period.ReportType.WEEKLY:
            previous = immediately_previous_weekly(period)
        return Response(analyze_period(period, previous))


class ComparisonInsightsView(APIView):
    permission_classes = (IsAdmin,)

    COMPARE_TYPES = ("week", "month", "year")

    def get(self, request):
        from wellness.services.insights import compare_periods

        ctype = str(request.query_params.get("type") or "week").lower()
        if ctype not in self.COMPARE_TYPES:
            return _error("INVALID_COMPARE_TYPE", "type must be 'week', 'month' or 'year'.")

        try:
            from_id = int(request.query_params.get("from_id") or 0)
            to_id = int(request.query_params.get("to_id") or 0)
        except (TypeError, ValueError):
            return _error("INVALID_PERIOD_ID", "from_id and to_id must be integers.")

        a = Period.objects.filter(pk=from_id, superseded_by__isnull=True).first()
        b = Period.objects.filter(pk=to_id, superseded_by__isnull=True).first()
        if a is None or b is None:
            return _error("PERIOD_NOT_FOUND", "One or both periods no longer exist.")

        if ctype == "week" and (a.report_type != Period.ReportType.WEEKLY or b.report_type != Period.ReportType.WEEKLY):
            return _error("INVALID_COMPARISON", "Week-over-week comparison needs two weekly periods.")
        if ctype == "month" and (a.report_type != Period.ReportType.MONTHLY or b.report_type != Period.ReportType.MONTHLY):
            return _error("INVALID_COMPARISON", "Month-over-month comparison needs two monthly periods.")
        if ctype == "year":
            if a.report_type != b.report_type:
                return _error("INVALID_COMPARISON", "Year-over-year comparison needs two periods of the same type.")
            if a.period_start.year == b.period_start.year:
                return _error("INVALID_COMPARISON", "Year-over-year comparison needs two periods from different years.")

        # Always compare baseline (earlier) vs current (later).
        if b.period_start < a.period_start:
            a, b = b, a
        return Response(compare_periods(a, b, ctype))


class ImportHistoryView(APIView):
    permission_classes = (IsAdmin,)

    def get(self, request):
        qs = ImportEvent.objects.select_related("period", "imported_by").order_by("-imported_at")
        query = request.query_params.get("q")
        if query:
            qs = qs.filter(
                Q_import_filter(query)
            )
        return Response(ImportEventSerializer(qs, many=True).data)


def Q_import_filter(query):
    from django.db.models import Q

    return (
        Q(period__report_type__icontains=query)
        | Q(original_filename__icontains=query)
        | Q(imported_by__username__icontains=query)
        | Q(imported_by__first_name__icontains=query)
    )


class ReportGenerateView(APIView):
    permission_classes = (IsAdmin,)

    COMPARE_FORMATS = ("comparison_ppt", "comparison_xlsx")

    def _comparison_pair(self, request):
        """Validate and return (baseline, current) periods + insights for a comparison export."""
        from wellness.services.insights import compare_periods

        ctype = str(request.data.get("compare_type") or "week").lower()
        if ctype not in ComparisonInsightsView.COMPARE_TYPES:
            return None, _error("INVALID_COMPARE_TYPE", "compare_type must be 'week', 'month' or 'year'.")

        a = Period.objects.filter(
            pk=request.data.get("from_id"), superseded_by__isnull=True
        ).first()
        b = Period.objects.filter(
            pk=request.data.get("to_id"), superseded_by__isnull=True
        ).first()
        if a is None or b is None:
            return None, _error("PERIOD_NOT_FOUND", "One or both periods no longer exist.")

        if ctype == "week" and (a.report_type != Period.ReportType.WEEKLY or b.report_type != Period.ReportType.WEEKLY):
            return None, _error("INVALID_COMPARISON", "Week-over-week comparison needs two weekly periods.")
        if ctype == "month" and (a.report_type != Period.ReportType.MONTHLY or b.report_type != Period.ReportType.MONTHLY):
            return None, _error("INVALID_COMPARISON", "Month-over-month comparison needs two monthly periods.")
        if ctype == "year":
            if a.report_type != b.report_type:
                return None, _error("INVALID_COMPARISON", "Year-over-year comparison needs two periods of the same type.")
            if a.period_start.year == b.period_start.year:
                return None, _error("INVALID_COMPARISON", "Year-over-year comparison needs two periods from different years.")

        if b.period_start < a.period_start:
            a, b = b, a
        return (a, b, compare_periods(a, b, ctype)), None

    def post(self, request):
        from wellness.services.reports import exports, ppt

        kind = request.data.get("format", "ppt")

        if kind in self.COMPARE_FORMATS:
            pair, err = self._comparison_pair(request)
            if err is not None:
                return err
            a, b, insights = pair
            ai_analysis = request.data.get("ai_analysis", True)
            if isinstance(ai_analysis, str):
                ai_analysis = ai_analysis.strip().lower() in ("1", "true", "yes", "on")
            else:
                ai_analysis = bool(ai_analysis)
            insert_into_ppt = request.data.get("insert_into_ppt", True)
            if isinstance(insert_into_ppt, str):
                insert_into_ppt = insert_into_ppt.strip().lower() in ("1", "true", "yes", "on")
            else:
                insert_into_ppt = bool(insert_into_ppt)
            if kind == "comparison_ppt":
                if a.report_type == Period.ReportType.MONTHLY:
                    bullets = insights.get("insights") if ai_analysis else None
                    data = ppt.build_monthly_comparison(
                        a, b, insights=bullets,
                        source_label=f"{a.title or a.period_start} & {b.title or b.period_start}",
                    )
                elif a.report_type == Period.ReportType.WEEKLY:
                    data = ppt.build_weekly_comparison(
                        a, b,
                        source_label=f"{a.title or a.period_start} & {b.title or b.period_start}",
                    )
                elif ai_analysis:
                    data = ppt.build_ai_comparison(a, b, insights, insert_into_ppt=insert_into_ppt)
                else:
                    data = ppt.build_weekly(a, b, insights=insights)
                filename = f"ai_analysis_{insights['comparison_type']}_{a.period_start}_{b.period_end}.pptx"
                content_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            else:
                data = exports.build_comparison_excel(a, b, insights)
                filename = f"ai_analysis_{insights['comparison_type']}_{a.period_start}_{b.period_end}.xlsx"
                content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

            from wellness.services.persistence import log_audit
            log_audit(request.user, "report_generated", "period", b.id,
                      {"format": kind, "compare_type": insights["comparison_type"],
                       "filename": filename, "from_id": a.id})
            return FileResponse(
                io.BytesIO(data), as_attachment=True, filename=filename, content_type=content_type
            )

        if kind == "annual_ppt":
            year_raw = request.data.get("year")
            year = None
            if year_raw not in (None, ""):
                try:
                    year = int(year_raw)
                except (TypeError, ValueError):
                    return _error("INVALID_YEAR", "year must be a calendar year, e.g. 2026.")
            else:
                ref_period = Period.objects.filter(
                    pk=request.data.get("period_id"), superseded_by__isnull=True
                ).first()
                if ref_period is None:
                    return _error("INVALID_YEAR", "Provide 'year' or a valid 'period_id'.")
                year = ref_period.period_start.year
            months = list(
                Period.objects.filter(
                    report_type=Period.ReportType.MONTHLY,
                    period_start__year=year,
                    superseded_by__isnull=True,
                ).prefetch_related("case_rows").order_by("period_start")
            )
            if not months:
                return _error(
                    "YEAR_DATA_UNAVAILABLE",
                    f"No monthly reports found for {year}; upload monthly data first.",
                    {"year": year},
                )
            data = ppt.build_annual(months)
            filename = f"annual_{year}_data_analysis.pptx"
            content_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            from wellness.services.persistence import log_audit
            log_audit(request.user, "report_generated", "period", months[-1].id,
                      {"format": kind, "filename": filename, "year": year,
                       "months_merged": len(months)})
            return FileResponse(
                io.BytesIO(data), as_attachment=True, filename=filename, content_type=content_type
            )

        if kind == "yearly_ppt":
            try:
                fy1_year = int(request.data.get("from_year"))
                fy2_year = int(request.data.get("to_year"))
            except (TypeError, ValueError):
                return _error("INVALID_YEAR", "from_year and to_year must be fiscal-year start years.")
            if fy1_year == fy2_year:
                return _error("INVALID_YEAR", "Choose two different fiscal years for the yearly comparison.")
            if fy1_year > fy2_year:
                fy1_year, fy2_year = fy2_year, fy1_year

            def fiscal_periods(start_year):
                return list(
                    Period.objects.filter(
                        report_type=Period.ReportType.MONTHLY,
                        period_start__gte=date(start_year, 4, 1),
                        period_start__lt=date(start_year + 1, 4, 1),
                        superseded_by__isnull=True,
                    ).prefetch_related("case_rows").order_by("period_start")
                )

            periods_a = fiscal_periods(fy1_year)
            periods_b = fiscal_periods(fy2_year)
            if not periods_a or not periods_b:
                return _error(
                    "YEAR_DATA_UNAVAILABLE",
                    "Both fiscal years need at least one monthly report before a yearly PPT can be generated.",
                    {"from_year": fy1_year, "to_year": fy2_year,
                     "from_periods": len(periods_a), "to_periods": len(periods_b)},
                )

            fy1_label = f"FY {fy1_year}-{str(fy1_year + 1)[-2:]}"
            fy2_label = f"FY {fy2_year}-{str(fy2_year + 1)[-2:]}"
            data = ppt.build_yearly(periods_a, periods_b, fy1_label, fy2_label)
            filename = f"yearly_{fy1_label.replace(' ', '_')}_vs_{fy2_label.replace(' ', '_')}.pptx"
            content_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            from wellness.services.persistence import log_audit
            log_audit(request.user, "report_generated", "period", periods_b[-1].id,
                      {"format": kind, "filename": filename,
                       "from_year": fy1_year, "to_year": fy2_year,
                       "from_periods": len(periods_a), "to_periods": len(periods_b)})
            return FileResponse(
                io.BytesIO(data), as_attachment=True, filename=filename, content_type=content_type
            )

        period = Period.objects.filter(
            pk=request.data.get("period_id"), superseded_by__isnull=True
        ).first()
        if period is None:
            return _error("PERIOD_NOT_FOUND", "Period not found or already replaced.")
        previous = None
        prev_id = request.data.get("previous_period_id")
        insights = None

        if kind == "ppt":
            from wellness.services.insights import analyze_period

            if period.report_type == Period.ReportType.WEEKLY:
                expected_previous = immediately_previous_weekly(period)
                if prev_id:
                    previous = Period.objects.filter(pk=prev_id, superseded_by__isnull=True).first()
                    if previous is None:
                        return _error("INVALID_PREVIOUS_PERIOD", "The selected previous period no longer exists.")
                    if previous.report_type != Period.ReportType.WEEKLY:
                        return _error("INVALID_PREVIOUS_PERIOD", "Weekly reports can only be compared with another weekly report.")
                    state = weekly_comparison_state(period, previous)
                    if state == "overlap":
                        return _error("INVALID_PREVIOUS_PERIOD", "The comparison period overlaps the selected reporting period.")
                    if expected_previous is None or previous.pk != expected_previous.pk:
                        return _error("INVALID_PREVIOUS_PERIOD", "Select the immediately previous weekly reporting period by date.")
                else:
                    previous = expected_previous
                prev_for_insights = None
                if previous is None:
                    previous = period
                else:
                    prev_for_insights = None if previous.pk == period.pk else previous
                insights = analyze_period(period, prev_for_insights)
                data = ppt.build_weekly_comparison(
                    previous, period,
                    source_label=f"{previous.title or previous.period_start} & {period.title or period.period_start}",
                )
                filename = f"weekly_{previous.period_start}_{period.period_end}.pptx"
            else:
                comparison_period = previous
                if comparison_period is None:
                    comparison_period = Period.objects.filter(
                        report_type=Period.ReportType.MONTHLY,
                        period_end__lt=period.period_start,
                        superseded_by__isnull=True,
                    ).order_by("-period_end").first()
                if comparison_period is not None and comparison_period.report_type == Period.ReportType.MONTHLY:
                    comparison_insights = analyze_period(period, comparison_period)
                    data = ppt.build_monthly_comparison(
                        comparison_period, period,
                        insights=comparison_insights.get("insights"),
                        source_label=f"{comparison_period.title or comparison_period.period_start} & {period.title or period.period_start}",
                    )
                    filename = f"monthly_comparison_{comparison_period.period_start}_{period.period_end}.pptx"
                else:
                    insights = analyze_period(period)
                    data = ppt.build_monthly(period, insights=insights)
                    filename = f"monthly_{period.period_start}_{period.period_end}.pptx"
            content_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        else:
            if prev_id:
                previous = Period.objects.filter(pk=prev_id).first()
            try:
                filename, data, content_type = exports.build(kind, period, previous)
            except ValueError:
                return _error("INVALID_FORMAT", f"Unsupported export format: {kind}")

        from wellness.services.persistence import log_audit

        log_audit(request.user, "report_generated", "period", period.id,
                  {"format": kind, "filename": filename})
        return FileResponse(
            io.BytesIO(data), as_attachment=True, filename=filename, content_type=content_type
        )


# ═══════════════════════════════════════════════════════════════════════════════
# AI ASSISTANT
# ═══════════════════════════════════════════════════════════════════════════════

class AssistantView(APIView):
    """Chat endpoint for the AI Assistant with tool-calling."""

    def post(self, request):
        from wellness.services.assistant import chat_completion, approve_action

        messages = request.data.get("messages", [])
        if not messages:
            return _error("EMPTY_MESSAGES", "Provide a 'messages' array with at least one user message.")

        result = chat_completion(messages)
        return Response(result)

    def put(self, request):
        """Approve a pending action (e.g. generate report)."""
        from wellness.services.assistant import approve_action as do_approve
        from wellness.services.reports import exports

        action = request.data.get("action")
        if not action:
            return _error("NO_ACTION", "Provide an 'action' object to approve.")

        approved = do_approve(action)
        if approved.get("status") == "approved":
            period_id = approved["period_id"]
            fmt = approved["format"]
            period = Period.objects.filter(id=period_id).first()
            if not period:
                return _error("PERIOD_NOT_FOUND", f"Period {period_id} not found.")
            try:
                filename, data, content_type = exports.build(fmt, period)
            except Exception as e:
                return _error("GENERATION_FAILED", str(e))

            from wellness.services.persistence import log_audit
            log_audit(request.user, "report_generated", "period", period_id,
                      {"format": fmt, "filename": filename, "source": "ai_assistant"})

            return FileResponse(
                io.BytesIO(data), as_attachment=True, filename=filename, content_type=content_type
            )

        return Response({"status": approved.get("status", "unknown")})


class AssistantUploadView(APIView):
    """Accept a file upload for the AI assistant context."""

    def post(self, request):
        file = request.FILES.get("file")
        if not file:
            return _error("MISSING_FILE", "No file was uploaded.")
        if not file.name.lower().endswith((".xlsx", ".xls", ".csv")):
            return _error("INVALID_FILE_TYPE", "Only Excel/CSV files are supported.")

        data = file.read()
        try:
            report = P.parse_excel(data)
            rows = sum(len(s.rows) for s in report.sheets)
        except Exception:
            rows = 0

        return Response({"rows": rows, "filename": file.name, "status": "processed"})


# ═══════════════════════════════════════════════════════════════════════════════
# AI SUGGESTIONS & IMPROVEMENT MODULE
# ═══════════════════════════════════════════════════════════════════════════════

class AISuggestionsView(APIView):
    """Generate AI-powered improvement suggestions for wellness centre data."""

    permission_classes = (IsAdmin,)

    def post(self, request):
        from wellness.services.ai_suggestions import (
            generate_weekly_suggestions,
            generate_monthly_suggestions,
            generate_yearly_suggestions,
            generate_comparison_suggestions,
            generate_roadmap,
        )
        from wellness.services.insights import snapshot, active_periods

        mode = str(request.data.get("mode") or "weekly").lower()

        if mode == "weekly":
            period_id = request.data.get("period_id")
            if not period_id:
                return _error("MISSING_PERIOD_ID", "period_id is required for weekly mode.")
            period = Period.objects.filter(pk=period_id, superseded_by__isnull=True).first()
            if not period:
                return _error("PERIOD_NOT_FOUND", "Period not found.")
            cur_snap = snapshot(period)
            prev = immediately_previous_weekly(period) if period.report_type == Period.ReportType.WEEKLY else None
            prev_snap = snapshot(prev) if prev else None
            result = generate_weekly_suggestions(cur_snap, prev_snap)
            result["period"] = {"id": period.id, "label": cur_snap["label"], "start": period.period_start.isoformat(), "end": period.period_end.isoformat()}
            result["previous_period"] = {"id": prev.id, "label": prev_snap["label"]} if prev else None
            result["mode"] = "weekly"

        elif mode == "monthly":
            year = request.data.get("year")
            month = request.data.get("month")
            if not year or not month:
                return _error("MISSING_PARAMS", "year and month are required for monthly mode.")
            try:
                year, month = int(year), int(month)
            except (TypeError, ValueError):
                return _error("INVALID_PARAMS", "year and month must be integers.")
            weekly_periods = list(
                Period.objects.filter(
                    report_type=Period.ReportType.WEEKLY,
                    period_start__year=year,
                    period_start__month=month,
                    superseded_by__isnull=True,
                ).order_by("period_start")
            )
            if not weekly_periods:
                return _error("NO_DATA", f"No weekly reports found for {year}-{month:02d}.")
            snaps = [snapshot(p) for p in weekly_periods]
            result = generate_monthly_suggestions(snaps)
            result["period"] = {"year": year, "month": month, "weeks_count": len(weekly_periods)}
            result["mode"] = "monthly"

        elif mode == "yearly":
            year = request.data.get("year")
            if not year:
                return _error("MISSING_PARAMS", "year is required for yearly mode.")
            try:
                year = int(year)
            except (TypeError, ValueError):
                return _error("INVALID_PARAMS", "year must be an integer.")
            monthly_periods = list(
                Period.objects.filter(
                    report_type=Period.ReportType.MONTHLY,
                    period_start__year=year,
                    superseded_by__isnull=True,
                ).order_by("period_start")
            )
            if not monthly_periods:
                return _error("NO_DATA", f"No monthly reports found for {year}.")
            snaps = [snapshot(p) for p in monthly_periods]
            result = generate_yearly_suggestions(snaps)
            result["period"] = {"year": year, "months_count": len(monthly_periods)}
            result["mode"] = "yearly"

        elif mode == "comparison":
            compare_type = str(request.data.get("compare_type") or "week").lower()
            from_id = request.data.get("from_id")
            to_id = request.data.get("to_id")
            if not from_id or not to_id:
                return _error("MISSING_PARAMS", "from_id and to_id are required for comparison mode.")
            a = Period.objects.filter(pk=from_id, superseded_by__isnull=True).first()
            b = Period.objects.filter(pk=to_id, superseded_by__isnull=True).first()
            if not a or not b:
                return _error("PERIOD_NOT_FOUND", "One or both periods not found.")
            if b.period_start < a.period_start:
                a, b = b, a
            snap_a = snapshot(a)
            snap_b = snapshot(b)
            result = generate_comparison_suggestions(snap_a, snap_b, compare_type)
            result["period"] = {
                "a": {"id": a.id, "label": snap_a["label"]},
                "b": {"id": b.id, "label": snap_b["label"]},
            }
            result["mode"] = "comparison"

        else:
            return _error("INVALID_MODE", "mode must be 'weekly', 'monthly', 'yearly', or 'comparison'.")

        result["roadmap"] = generate_roadmap(result.get("suggestions", []))
        return Response(result)


class ActionPlanView(APIView):
    """CRUD for AI Improvement Action Plans."""

    permission_classes = (IsAdmin,)

    def get(self, request):
        qs = ActionPlan.objects.filter(created_by=request.user).order_by("-created_at")
        source_type = request.query_params.get("source_type")
        if source_type:
            qs = qs.filter(source_type=source_type)
        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return Response(ActionPlanSerializer(qs, many=True).data)

    def post(self, request):
        serializer = ActionPlanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(created_by=request.user)
        return Response(serializer.data, status=http_status.HTTP_201_CREATED)

    def patch(self, request, pk):
        try:
            plan = ActionPlan.objects.get(pk=pk, created_by=request.user)
        except ActionPlan.DoesNotExist:
            return _error("NOT_FOUND", "Action plan not found.")
        serializer = ActionPlanSerializer(plan, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):
        try:
            plan = ActionPlan.objects.get(pk=pk, created_by=request.user)
        except ActionPlan.DoesNotExist:
            return _error("NOT_FOUND", "Action plan not found.")
        plan.delete()
        return Response(status=http_status.HTTP_204_NO_CONTENT)


class AIInsightsExportView(APIView):
    """Export AI suggestions as JSON for PPT integration."""

    permission_classes = (IsAdmin,)

    def post(self, request):
        from wellness.services.ai_suggestions import ppt_summary, generate_roadmap

        result = request.data.get("result")
        if not result:
            return _error("MISSING_RESULT", "Provide the AI suggestions result.")
        summary = ppt_summary(result)
        return Response(summary)


class ReportCenterView(APIView):
    """Separate Weekly / Monthly / Yearly report modules.

    GET  -> available years, weekly entries and per-month week counts
             (drives the Date / Week-Month-Year filters in the UI).
    POST -> generate PPT or Excel for a single report, or a comparison.
             Monthly combines every weekly report of the month (1st..last day);
             Yearly combines every monthly report of the year (Jan 1..Dec 31).
             Both are computed on demand, so they always reflect the latest
             weekly data — no duplicates, no stale copies.
    """

    permission_classes = (IsAdmin,)

    def get(self, request):
        from wellness.services.reports import report_center

        return Response(report_center.options())

    def _maybe_append_ai(self, data_bytes, report_type, periods_for_ai, fmt="ppt"):
        """Append AI slides to PPT if requested."""
        if fmt != "ppt":
            return data_bytes
        try:
            from wellness.services.ai_suggestions import (
                generate_weekly_suggestions, generate_monthly_suggestions,
                generate_yearly_suggestions, generate_roadmap,
            )
            from wellness.services.insights import snapshot
            from wellness.services.reports.ppt import append_ai_slides

            if report_type == "weekly" and periods_for_ai:
                cur = snapshot(periods_for_ai[-1])
                prev = snapshot(periods_for_ai[-2]) if len(periods_for_ai) >= 2 else None
                result = generate_weekly_suggestions(cur, prev)
                result["roadmap"] = generate_roadmap(result.get("suggestions", []))
                label = f"{periods_for_ai[-1].period_start} to {periods_for_ai[-1].period_end}"
                return append_ai_slides(data_bytes, result, label)
            elif report_type == "monthly" and periods_for_ai:
                snaps = [snapshot(p) for p in periods_for_ai]
                result = generate_monthly_suggestions(snaps)
                result["roadmap"] = generate_roadmap(result.get("suggestions", []))
                label = f"{periods_for_ai[0].period_start.strftime('%B %Y')}"
                return append_ai_slides(data_bytes, result, label)
            elif report_type == "yearly" and periods_for_ai:
                snaps = [snapshot(p) for p in periods_for_ai]
                result = generate_yearly_suggestions(snaps)
                result["roadmap"] = generate_roadmap(result.get("suggestions", []))
                label = f"Year {periods_for_ai[0].period_start.year}"
                return append_ai_slides(data_bytes, result, label)
        except Exception as e:
            import traceback, logging
            logging.error("AI slides append failed: %s", e)
            traceback.print_exc()
        return data_bytes

    def post(self, request):
        from wellness.services.reports import report_center
        from wellness.services.persistence import log_audit

        def file_response(data_bytes, filename, content_type):
            """Return a browser-readable Office download."""
            response = FileResponse(
                io.BytesIO(data_bytes), as_attachment=True,
                filename=filename, content_type=content_type,
            )
            response["Access-Control-Expose-Headers"] = (
                "Content-Disposition, Content-Type, Content-Length"
            )
            return response

        data = request.data or {}
        fmt = str(data.get("format") or "ppt").lower()
        if fmt not in ("ppt", "xlsx"):
            return _error("INVALID_FORMAT", "format must be 'ppt' or 'xlsx'.")

        compare = data.get("compare")
        if compare:
            ctype = str(compare.get("type") or "").lower()
            try:
                filename, data_bytes, content_type = report_center.build_compare(
                    ctype, "ppt",
                    from_id=compare.get("from_id"), to_id=compare.get("to_id"),
                    from_ym=compare.get("from_month"), to_ym=compare.get("to_month"),
                    from_year=compare.get("from_year"), to_year=compare.get("to_year"),
                )
            except ValueError as e:
                return _error("INVALID_COMPARISON", str(e))
            except Exception as e:
                return _error("GENERATION_FAILED", str(e))

            if fmt == "ppt":
                try:
                    from wellness.services.ai_suggestions import (
                        generate_comparison_suggestions, generate_roadmap,
                    )
                    from wellness.services.insights import snapshot
                    from wellness.services.reports.ppt import append_ai_slides

                    from_id_val = compare.get("from_id")
                    to_id_val = compare.get("to_id")
                    a = Period.objects.filter(pk=from_id_val, superseded_by__isnull=True).first()
                    b = Period.objects.filter(pk=to_id_val, superseded_by__isnull=True).first()
                    if a and b:
                        if b.period_start < a.period_start:
                            a, b = b, a
                        result = generate_comparison_suggestions(snapshot(a), snapshot(b), ctype)
                        result["roadmap"] = generate_roadmap(result.get("suggestions", []))
                        label = f"{a.period_start} vs {b.period_start}"
                        data_bytes = append_ai_slides(data_bytes, result, label)
                except Exception:
                    pass

            log_audit(request.user, "report_generated", "period", 0,
                      {"format": "comparison_ppt", "filename": filename,
                       "module": f"report-center-{ctype}"})
            return file_response(data_bytes, filename, content_type)

        report_type = str(data.get("report_type") or "").lower()
        if report_type not in ("weekly", "monthly", "yearly"):
            return _error("INVALID_REPORT_TYPE",
                          "report_type must be 'weekly', 'monthly' or 'yearly'.")
        try:
            filename, data_bytes, content_type, source_ids = report_center.build_single(
                report_type, fmt,
                period_id=data.get("period_id"),
                year=data.get("year"), month=data.get("month"),
            )
        except ValueError as e:
            return _error("DATA_UNAVAILABLE", str(e))
        except Exception as e:
            return _error("GENERATION_FAILED", str(e))

        if fmt == "ppt" and source_ids:
            try:
                periods_for_ai = list(Period.objects.filter(
                    pk__in=source_ids, superseded_by__isnull=True
                ).order_by("period_start"))
                data_bytes = self._maybe_append_ai(data_bytes, report_type, periods_for_ai, fmt)
            except Exception as e:
                import traceback, logging
                logging.error("AI slides outer append failed: %s", e)
                traceback.print_exc()

        log_audit(request.user, "report_generated", "period",
                  source_ids[-1] if source_ids else 0,
                  {"format": fmt, "filename": filename,
                   "module": f"report-center-{report_type}",
                   "sources_merged": len(source_ids)})
        return file_response(data_bytes, filename, content_type)
