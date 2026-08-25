"""Data model for the Wellness Centre Analytics Dashboard.

Schema follows spec section 8.1 (adapted for Django):

- periods           — one weekly/monthly reporting window, immutable once saved.
- case_rows         — merged verticals (WC/YD/MW) only; the ONLY table the
                      dashboard/calculation/report pipeline reads from.
- raw_subteam_rows  — audit-only record of the original WLN Ctr / Team A /
                      Your Dost / Myndwell rows; never read by the live app.
- secondary_metrics — sessions, early-prevention warning, no-show, active
                      cases and >4-sessions, per vertical + Total.
- enquiry_modes     — period-level totals (mail / calls received / outgoing).
- imports           — import/entry event metadata incl. the original file.
- audit_log         — append-only history of every mutating action.
"""

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        SUPER_ADMIN = "super_admin", "Super Admin"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.ADMIN)

    class Meta:
        ordering = ("-id",)

    @property
    def is_super_admin(self) -> bool:
        return self.role == self.Role.SUPER_ADMIN


class Period(models.Model):
    class ReportType(models.TextChoices):
        WEEKLY = "weekly", "Weekly"
        MONTHLY = "monthly", "Monthly"

    class Status(models.TextChoices):
        COMPLETE = "complete", "Complete"
        INCOMPLETE = "incomplete", "Incomplete"
        NEEDS_REVIEW = "needs_review", "Needs Review"

    class Source(models.TextChoices):
        UPLOAD = "upload", "Upload"
        MANUAL = "manual", "Manual"

    report_type = models.CharField(max_length=10, choices=ReportType.choices)
    period_start = models.DateField()
    period_end = models.DateField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.COMPLETE)
    source = models.CharField(max_length=10, choices=Source.choices)
    title = models.TextField(blank=True, default="")
    created_by = models.ForeignKey("User", null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    superseded_by = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="supersedes"
    )

    class Meta:
        ordering = ("-period_start",)
        constraints = [
            models.UniqueConstraint(
                fields=["report_type", "period_start", "period_end"],
                condition=models.Q(superseded_by__isnull=True),
                name="uniq_active_period",
            )
        ]

    def __str__(self):
        return f"{self.report_type} {self.period_start}..{self.period_end}"


class CaseRow(models.Model):
    """One merged vertical row per (period, case_type, vertical)."""

    class CaseType(models.TextChoices):
        NEW = "new", "New"
        FOLLOWUP = "followup", "Follow-up"

    class Vertical(models.TextChoices):
        WC = "WC", "Wellness Centre"
        TA = "TA", "Team A"
        YD = "YD", "Your Dost"
        MW = "MW", "Myndwell"

    period = models.ForeignKey(Period, on_delete=models.CASCADE, related_name="case_rows")
    case_type = models.CharField(max_length=10, choices=CaseType.choices)
    vertical = models.CharField(max_length=5, choices=Vertical.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    total_cases = models.IntegerField(default=0)
    gender_male = models.IntegerField(default=0)
    gender_female = models.IntegerField(default=0)
    gender_other = models.IntegerField(default=0)
    mode_online = models.IntegerField(default=0)
    mode_in_person = models.IntegerField(default=0)
    mode_phone = models.IntegerField(default=0)
    referral_self = models.IntegerField(default=0)
    referral_director = models.IntegerField(default=0)
    referral_dean = models.IntegerField(default=0)
    referral_friend = models.IntegerField(default=0)
    referral_mitr = models.IntegerField(default=0)
    concern_anxiety = models.IntegerField(default=0)
    concern_stress = models.IntegerField(default=0)
    concern_career = models.IntegerField(default=0)
    concern_interpersonal = models.IntegerField(default=0)
    concern_self_dev = models.IntegerField(default=0)
    concern_clinical = models.IntegerField(default=0)
    concern_addiction = models.IntegerField(default=0)
    concern_medical = models.IntegerField(default=0)
    concern_suicidal = models.IntegerField(default=0)
    stake_ug = models.IntegerField(default=0)
    stake_pg = models.IntegerField(default=0)
    stake_phd = models.IntegerField(default=0)
    stake_dual = models.IntegerField(default=0)
    stake_faculty = models.IntegerField(default=0)
    stake_employee_family = models.IntegerField(default=0)
    stake_postdoc = models.IntegerField(default=0)
    stake_unidentified = models.IntegerField(default=0)

    needs_review = models.BooleanField(default=False)
    review_reason = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ("case_type", "vertical")
        constraints = [
            models.UniqueConstraint(
                fields=["period", "case_type", "vertical"], name="uniq_case_row"
            )
        ]

    def __str__(self):
        return f"{self.period_id} {self.case_type} {self.vertical}"


class RawSubteamRow(models.Model):
    """Audit-only original sub-team row. Never read by the live pipeline."""

    period = models.ForeignKey(Period, on_delete=models.CASCADE, related_name="raw_rows")
    case_type = models.CharField(max_length=10)
    sub_team = models.CharField(max_length=20)
    entry_no = models.CharField(max_length=10, blank=True, default="")
    source = models.CharField(max_length=10)  # upload | manual

    # The 29 numeric columns exactly as uploaded/entered.
    raw_payload = models.JSONField(default=dict)
    # Per-check results: {name: {"passed": bool, "expected": int, "actual": int}}
    check_results = models.JSONField(default=dict)
    needs_review = models.BooleanField(default=False)
    reason = models.TextField(null=True, blank=True)
    created_by = models.ForeignKey("User", null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("case_type", "sub_team")

    def __str__(self):
        return f"{self.entry_no or self.sub_team} {self.case_type}"


class SecondaryMetrics(models.Model):
    class Vertical(models.TextChoices):
        WC = "WC"
        TA = "TA"
        YD = "YD"
        MW = "MW"
        TOTAL = "Total"

    period = models.ForeignKey(Period, on_delete=models.CASCADE, related_name="secondary_metrics")
    vertical = models.CharField(max_length=10, choices=Vertical.choices)
    total_sessions = models.IntegerField(default=0)
    early_prevention_warning = models.IntegerField(default=0)
    no_show_turn_up = models.IntegerField(default=0)
    active_cases = models.IntegerField(default=0)
    clients_over_4_sessions = models.IntegerField(default=0)

    class Meta:
        ordering = ("vertical",)
        constraints = [
            models.UniqueConstraint(fields=["period", "vertical"], name="uniq_secondary_metric")
        ]


class EnquiryModes(models.Model):
    period = models.OneToOneField(Period, on_delete=models.CASCADE, related_name="enquiry_modes")
    mail = models.IntegerField(default=0)
    calls_recd = models.IntegerField(default=0)
    calls_out = models.IntegerField(default=0)


class ImportEvent(models.Model):
    period = models.ForeignKey(Period, on_delete=models.CASCADE, related_name="imports")
    source = models.CharField(max_length=10)  # upload | manual
    original_filename = models.CharField(max_length=255, null=True, blank=True)
    file_hash = models.CharField(max_length=64, null=True, blank=True)
    file = models.FileField(upload_to="uploads/", null=True, blank=True)
    rows_imported = models.IntegerField(default=0)
    rows_warned = models.IntegerField(default=0)
    rows_rejected = models.IntegerField(default=0)
    imported_by = models.ForeignKey("User", null=True, on_delete=models.SET_NULL, related_name="+")
    imported_at = models.DateTimeField(auto_now_add=True)


class AuditLog(models.Model):
    actor = models.ForeignKey("User", null=True, on_delete=models.SET_NULL, related_name="+")
    action = models.CharField(max_length=40)
    target_type = models.CharField(max_length=40)
    target_id = models.BigIntegerField(null=True)
    details = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
