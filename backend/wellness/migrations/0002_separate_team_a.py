from django.db import migrations


def split_existing_team_a(apps, schema_editor):
    Period = apps.get_model("wellness", "Period")
    CaseRow = apps.get_model("wellness", "CaseRow")
    fields = [
        "total_cases", "gender_male", "gender_female", "gender_other",
        "mode_online", "mode_in_person", "mode_phone",
        "referral_self", "referral_director", "referral_dean", "referral_friend", "referral_mitr",
        "concern_anxiety", "concern_stress", "concern_career", "concern_interpersonal",
        "concern_self_dev", "concern_clinical", "concern_addiction", "concern_medical", "concern_suicidal",
        "stake_ug", "stake_pg", "stake_phd", "stake_dual", "stake_faculty",
        "stake_employee_family", "stake_postdoc", "stake_unidentified",
    ]
    team_map = {"WLN Ctr": "WC", "Team A": "TA", "Your Dost": "YD", "Myndwell": "MW"}
    for period in Period.objects.all().iterator():
        raw_rows = period.raw_rows.all()
        for case_type in ("new", "followup"):
            for source_team, vertical in team_map.items():
                raw = raw_rows.filter(case_type=case_type, sub_team=source_team).order_by("-created_at", "-id").first()
                if raw is None:
                    continue
                payload = raw.raw_payload or {}
                CaseRow.objects.update_or_create(
                    period_id=period.id,
                    case_type=case_type,
                    vertical=vertical,
                    defaults={
                        field: int(payload.get(field, 0) or 0)
                        for field in fields
                    } | {
                        "needs_review": raw.needs_review,
                        "review_reason": raw.reason,
                    },
                )


class Migration(migrations.Migration):
    dependencies = [("wellness", "0001_initial")]
    operations = [migrations.RunPython(split_existing_team_a, migrations.RunPython.noop)]
