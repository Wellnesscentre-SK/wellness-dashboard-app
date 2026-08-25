"""Serializers for the wellness API."""

from rest_framework import serializers

from wellness.models import CaseRow, ImportEvent, Period, RawSubteamRow, SecondaryMetrics, User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "email", "first_name", "last_name", "role", "is_active")


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ("id", "username", "email", "first_name", "last_name", "role", "password")

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class CaseRowSerializer(serializers.ModelSerializer):
    class Meta:
        model = CaseRow
        exclude = ("created_at",)


class RawSubteamRowSerializer(serializers.ModelSerializer):
    """The provider-level source values used by the reconciliation view."""

    class Meta:
        model = RawSubteamRow
        fields = ("case_type", "sub_team", "raw_payload", "needs_review", "reason")


class PeriodSerializer(serializers.ModelSerializer):
    case_rows = CaseRowSerializer(many=True, read_only=True)
    raw_rows = serializers.SerializerMethodField()
    secondary_metrics = serializers.SerializerMethodField()
    enquiry_modes = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    def get_raw_rows(self, obj):
        """Expose only the newest RawSubteamRow version per (case_type, sub_team).

        Raw rows are an append-only version log; older versions must never
        reach API consumers or stale values would shadow manual edits.
        """
        latest = {}
        for r in obj.raw_rows.order_by("created_at", "id"):
            latest[(r.case_type, r.sub_team)] = r
        ordered = sorted(latest.values(), key=lambda r: (r.case_type, r.sub_team))
        return RawSubteamRowSerializer(ordered, many=True).data

    def get_enquiry_modes(self, obj):
        modes = getattr(obj, "enquiry_modes", None)
        return {"mail": getattr(modes, "mail", 0), "calls_recd": getattr(modes, "calls_recd", 0), "calls_out": getattr(modes, "calls_out", 0)}

    def get_secondary_metrics(self, obj):
        return [
            {
                "vertical": row.vertical,
                "total_sessions": row.total_sessions,
                "early_prevention_warning": row.early_prevention_warning,
                "no_show_turn_up": row.no_show_turn_up,
                "active_cases": row.active_cases,
                "clients_over_4_sessions": row.clients_over_4_sessions,
            }
            for row in obj.secondary_metrics.all()
        ]

    class Meta:
        model = Period
        fields = "__all__"


class ImportEventSerializer(serializers.ModelSerializer):
    period_label = serializers.SerializerMethodField()
    imported_by_name = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = ImportEvent
        fields = (
            "id", "period", "period_label", "source", "original_filename",
            "file_hash", "rows_imported", "rows_warned", "rows_rejected",
            "imported_by", "imported_by_name", "imported_at", "status",
        )

    def get_period_label(self, obj):
        return f"{obj.period.report_type} {obj.period.period_start} to {obj.period.period_end}"

    def get_imported_by_name(self, obj):
        return obj.imported_by.get_full_name() or obj.imported_by.username if obj.imported_by else None

    def get_status(self, obj):
        return obj.period.status


class SecondaryMetricsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SecondaryMetrics
        fields = "__all__"


def build_preview_payload(report, duplicate_period=None) -> dict:
    merged = report.merged_rows()
    vertical_totals = {
        ct: {
            v: merged[(ct, v)]["total_cases"]
            for v in ("WC", "TA", "YD", "MW")
        }
        for ct in ("new", "followup")
    }

    rows = [
        {
            "case_type": r.case_type,
            "sub_team": r.sub_team,
            "sheet_row": r.sheet_row,
            "status": r.status,
            "checks": [
                {"name": c.name, "passed": c.passed, "expected": c.expected,
                 "actual": c.actual, "off_by": c.off_by}
                for c in r.checks
            ],
            "reason": r.reason,
        }
        for r in report.rows
    ]

    ready = sum(1 for r in rows if r["status"] == "ready")
    warned = sum(1 for r in rows if r["status"] == "warning")
    rejected = sum(1 for r in rows if r["status"] == "rejected")

    return {
        "meta": {
            "report_type": report.report_type,
            "period_start": report.period_start.isoformat(),
            "period_end": report.period_end.isoformat(),
            "title": report.title,
            "file_sha256": report.file_sha256,
            "title_range_mismatch": report.title_range_mismatch,
        },
        "duplicate": None
        if duplicate_period is None
        else {
            "period_id": duplicate_period.id,
            "label": f"{duplicate_period.report_type} "
                     f"{duplicate_period.period_start} to {duplicate_period.period_end}",
            "status": duplicate_period.status,
            "source": duplicate_period.source,
            "created_at": duplicate_period.created_at.isoformat(),
        },
        "counts": {"ready": ready, "warned": warned, "rejected": rejected},
        "incomplete": rejected > 0,
        "rows": rows,
        "vertical_totals": vertical_totals,
        "secondary": {
            "total_sessions": report.secondary.total_sessions,
            "early_prevention_warning": report.secondary.early_prevention_warning,
            "no_show_turn_up": report.secondary.no_show_turn_up,
            "active_cases": report.secondary.active_cases,
            "clients_over_4_sessions": report.secondary.clients_over_4_sessions,
            "enquiry_modes": report.secondary.enquiry_modes,
            "stray_cells": report.secondary.stray_cells,
        },
        "warnings": report.warnings,
    }
