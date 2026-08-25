"""Seed the database for dev/staging: create a Super Admin and import the
sample fixture files as periods."""

import getpass
import os
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from wellness.models import User
from wellness.services import parsing as P
from wellness.services.persistence import save_import

FIXTURES = Path(__file__).resolve().parent.parent.parent.parent / "fixtures"

SAMPLE_FILES = [
    "monthly_01jul_30jul_2026.xlsx",
    "weekly_29jul_04aug_2026.xlsx",
    "weekly_mislabeled_22jul_28jul_2026.xlsx",
]


class Command(BaseCommand):
    help = "Create a Super Admin and import the sample fixture periods."

    def handle(self, *args, **options):
        if not User.objects.filter(role=User.Role.SUPER_ADMIN).exists():
            username = os.environ.get("SEED_USERNAME", "superadmin")
            email = os.environ.get("SEED_EMAIL", "superadmin@wellness.local")
            password = os.environ.get("SEED_PASSWORD") or getpass.getpass("Password for superadmin: ")
            User.objects.create_superuser(
                username=username,
                email=email,
                password=password,
                role=User.Role.SUPER_ADMIN,
            )
            self.stdout.write(self.style.SUCCESS(f"Created Super Admin '{username}'."))
        else:
            self.stdout.write("Super Admin already exists; skipping account creation.")

        admin = User.objects.filter(role=User.Role.SUPER_ADMIN).first()

        with transaction.atomic():
            for name in SAMPLE_FILES:
                path = FIXTURES / name
                if not path.exists():
                    self.stdout.write(self.style.WARNING(f"Skipping missing fixture {path}"))
                    continue
                with open(path, "rb") as fh:
                    data = fh.read()
                report = P.parse_excel(data)
                try:
                    imp = save_import(report, admin, filename=name, raw_bytes=data)
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Imported {name} -> period {imp.period_id} "
                            f"({report.report_type} {report.period_start}..{report.period_end})"
                        )
                    )
                except Exception as exc:  # noqa: BLE001
                    self.stdout.write(self.style.ERROR(f"Failed to import {name}: {exc}"))
