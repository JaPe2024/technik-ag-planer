"""Legt Beispieldaten zum lokalen Durchklicken an: zwei AGs mit Konten in allen Rollen.

    make beispieldaten   (bzw. python manage.py beispieldaten)

Anmeldung mit <name>@example.org, Passwort = Name (z. B. owner@example.org / owner) –
bewusst kurz, damit das Durchklicken schnell geht. Nur in der Entwicklung (DEBUG) erlaubt.
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import User
from apps.organizations.models import Membership, Organization
from apps.organizations.permissions import Role

DOMAIN = "@example.org"


def _members(org):
    """Mitgliedschaften nach Kurzname („owner“, „schueler“ …)."""
    return {
        m.user.email.split("@")[0]: m
        for m in Membership.objects.for_org(org).select_related("user")
    }


ORGS = {
    "Technik-AG Nord": [
        ("owner", "Olivia Owner", "Q1", Role.OWNER),
        ("admin", "Ali Admin", "EF", Role.ADMIN),
        ("lehrer", "Frau Lehmann", "", Role.TEACHER),
        ("schueler", "Emma", "8", Role.STUDENT),
        ("ben", "Ben", "10", Role.STUDENT),
    ],
    "Technik-AG Süd": [
        ("sued", "Sam Süd", "Q2", Role.OWNER),
        ("schueler", "Emma", "8", Role.STUDENT),  # Mitglied in zwei AGs
    ],
}


class Command(BaseCommand):
    help = "Legt Beispieldaten für die lokale Entwicklung an."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Auch ohne DEBUG ausführen.")

    @transaction.atomic
    def handle(self, *args, force=False, **options):
        if not settings.DEBUG and not force:
            raise CommandError("Nur in der Entwicklung (DEBUG) – oder mit --force.")

        for org_name, people in ORGS.items():
            org, _ = Organization.objects.get_or_create(name=org_name)
            for login, name, grade, role in people:
                user, created = User.objects.get_or_create(
                    email=f"{login}{DOMAIN}", defaults={"display_name": name, "grade": grade}
                )
                if created:
                    user.set_password(login)  # Passwort = Name vor dem @
                    user.save()
                Membership.objects.get_or_create(
                    organization=org, user=user, defaults={"role": role}
                )

        self._productions(Organization.objects.get(name="Technik-AG Nord"))
        self._scheduling(Organization.objects.get(name="Technik-AG Nord"))
        self._board(Organization.objects.get(name="Technik-AG Nord"))
        self._inventory(Organization.objects.get(name="Technik-AG Nord"))
        link = self._inquiries(Organization.objects.get(name="Technik-AG Nord"))
        self._team(Organization.objects.get(name="Technik-AG Nord"))

        self.stdout.write(self.style.SUCCESS("Beispieldaten angelegt."))
        self.stdout.write(
            f"Anmeldung: <name>{DOMAIN}, Passwort = Name, z. B. owner{DOMAIN} / owner"
        )
        self.stdout.write(
            f"Technik anfragen (AG Nord): http://localhost:8000/anfrage/{link.token}/"
        )
        for org_name, people in ORGS.items():
            self.stdout.write(f"\n{org_name}:")
            for login, _name, _grade, role in people:
                self.stdout.write(f"  {Role(role).label:<11} {login}{DOMAIN}")

    def _productions(self, org):
        from datetime import time, timedelta

        from django.utils import timezone

        from apps.productions.models import Category, Job, Production, ProductionStatus, Todo
        from apps.productions.services import assign

        if Production.all_objects.for_org(org).exists():
            return
        today = timezone.localdate()
        categories = {c.name: c for c in Category.objects.for_org(org)}
        planning = ProductionStatus.planning_for(org)
        confirmed = ProductionStatus.objects.for_org(org).get(system_key="confirmed")
        members = _members(org)

        plans = [
            (
                "Schulkonzert",
                "Konzert",
                2,
                2,
                confirmed,
                "Aula",
                "Schulstraße 1, 50667 Köln",
                [
                    ("Aufbau", 0, time(14), time(17), "Bühneneingang"),
                    ("Show", 1, time(18), time(21), "Technikpult"),
                    ("Abbau", 1, time(21), time(22, 30), "Aula"),
                ],
            ),
            (
                "Theater-Premiere",
                "Theater",
                9,
                1,
                planning,
                "Aula",
                "",
                [
                    ("Aufbau", 0, time(13), time(16), "Bühneneingang"),
                    ("Show", 0, time(19), time(21, 30), "Technikpult"),
                ],
            ),
            (
                "Herbstkonzert",
                "Konzert",
                -10,
                1,
                confirmed,
                "Aula",
                "",
                [
                    ("Aufbau", 0, time(13), time(16), "Bühneneingang"),
                    ("Show", 0, time(18), time(21), "Technikpult"),
                ],
            ),
            (
                "Sommerfest 2025",
                "Schulfest",
                -120,
                1,
                confirmed,
                "Schulhof",
                "",
                [("Aufbau", 0, time(9), time(11), "Hausmeisterei")],
            ),
        ]
        for name, cat, ahead, length, status, location, address, jobs in plans:
            start = today + timedelta(days=ahead)
            production = Production.objects.create(
                organization=org,
                name=name,
                category=categories[cat],
                start_date=start,
                end_date=start + timedelta(days=length - 1),
                status=status,
                location_name=location,
                address=address,
            )
            if name == "Schulkonzert":
                production.chat_enabled = True
                production.save(update_fields=["chat_enabled"])
            for i, (job_name, offset, begin, end, meeting) in enumerate(jobs):
                Job.objects.create(
                    organization=org,
                    production=production,
                    name=job_name,
                    date=start + timedelta(days=offset),
                    start_time=begin,
                    end_time=end,
                    meeting_point=meeting,
                    crew_needed=3 if job_name == "Aufbau" else None,
                    position=i,
                )
        concert = Production.objects.for_org(org).get(name="Schulkonzert")
        setup, show = concert.jobs.get(name="Aufbau"), concert.jobs.get(name="Show")
        assign(setup, members["schueler"], status="requested", role_label="Bühne")
        assign(setup, members["ben"], status="confirmed", role_label="Licht")
        assign(show, members["admin"], status="confirmed", role_label="FOH")
        assign(show, members["schueler"], status="confirmed", role_label="Monitor")
        autumn = Production.objects.for_org(org).get(name="Herbstkonzert")
        for job in autumn.jobs.all():
            assign(job, members["schueler"], status="confirmed", role_label="Licht")
            assign(job, members["ben"], status="confirmed", role_label="Ton")
        assign(autumn.jobs.get(name="Show"), members["admin"], status="confirmed", role_label="FOH")
        for text in ["Funkmikros laden", "Bühnenplan drucken"]:
            Todo.objects.create(organization=org, production=concert, text=text)

    def _board(self, org):
        from apps.board.models import Message
        from apps.board.services import post
        from apps.productions.models import Production

        if Message.objects.for_org(org).filter(kind=Message.Kind.USER).exists():
            return
        users = {name: m.user for name, m in _members(org).items()}
        concert = Production.objects.for_org(org).get(name="Schulkonzert")
        for name, text, production in [
            ("owner", "Willkommen im Board! Hier sprechen wir uns ab.", None),
            ("ben", "Wer hat den Schlüssel für den Technikraum?", None),
            ("lehrer", "Liegt im Sekretariat.", None),
            ("admin", "Treffen zum Aufbau am Bühneneingang.", concert),
            ("schueler", "Ich bringe die Funkmikros mit.", concert),
        ]:
            post(org, users[name], text, production)

    def _inventory(self, org):
        from datetime import timedelta

        from apps.inventory import services
        from apps.inventory.models import Kit, KitItem, Material, MaterialCategory, MaterialLink
        from apps.productions.models import Production

        if Material.objects.for_org(org).exists():
            return
        categories = {c.name: c for c in MaterialCategory.objects.for_org(org)}
        owner = Membership.objects.for_org(org).get(role=Role.OWNER).user
        items = [
            ("Lichtpult", "Licht", 1, "Technikraum, Regal 1. Netzteil liegt in der Kiste."),
            ("Moving Head", "Licht", 8, "Flightcase im Lager unter der Bühne"),
            ("LED-Par", "Licht", 12, ""),
            ("Mischpult", "Audio", 1, "Digitalpult, Tablet zur Fernsteuerung im Schrank"),
            ("Funkmikrofon", "Audio", 6, "Akkus vor jeder Show laden"),
            ("Aktivbox", "Audio", 4, ""),
            ("Monitorbox", "Audio", 4, ""),
            ("Beamer", "Video", 1, "Fernbedienung im Lehrerzimmer"),
            ("Podest 2 × 1 m", "Bühne", 6, ""),
            ("Kabeltrommel", "Strom & Kabel", 6, ""),
            ("XLR-Kabel 10 m", "Strom & Kabel", 20, ""),
            ("Gaffa-Tape", "Sonstiges", None, "Verbrauchsmaterial"),
        ]
        materials = {}
        for name, cat, quantity, notes in items:
            materials[name] = Material.objects.create(
                organization=org,
                name=name,
                category=categories[cat],
                quantity=quantity,
                notes=notes,
                created_by=owner,
            )
        MaterialLink.objects.create(
            organization=org,
            material=materials["Mischpult"],
            title="Handbuch",
            url="https://example.org/handbuch-mischpult.pdf",
        )
        kits = {
            "Große Audioanlage": [
                ("Mischpult", 1),
                ("Funkmikrofon", 4),
                ("Aktivbox", 4),
                ("Monitorbox", 2),
                ("XLR-Kabel 10 m", 12),
            ],
            "Bühnenlicht Aula": [("Lichtpult", 1), ("Moving Head", 6), ("LED-Par", 8)],
        }
        for kit_name, positions in kits.items():
            kit = Kit.objects.create(organization=org, name=kit_name)
            for name, quantity in positions:
                KitItem.objects.create(
                    organization=org, kit=kit, material=materials[name], quantity=quantity
                )
        concert = Production.objects.for_org(org).get(name="Schulkonzert")
        for kit in Kit.objects.for_org(org):
            services.apply_kit(concert, kit)
        services.plan(concert, materials["Gaffa-Tape"], 2)
        # Überbuchung: Ein zweiter Termin am selben Tag braucht ebenfalls Funkmikrofone
        rehearsal = Production.objects.create(
            organization=org,
            name="Chorprobe Aula",
            category=concert.category,
            start_date=concert.start_date + timedelta(days=1),
            end_date=concert.start_date + timedelta(days=1),
            status=concert.status,
            location_name="Musikraum",
        )
        services.plan(rehearsal, materials["Funkmikrofon"], 2)
        # Ein offener Defekt: damit fehlen beim Schulkonzert Funkmikrofone
        services.report_defect(materials["Funkmikrofon"], 1, "Kapsel knackt", owner)

    def _inquiries(self, org):
        from datetime import time, timedelta

        from django.utils import timezone

        from apps.inquiries.models import Inquiry
        from apps.inquiries.services import link_for, mark_done
        from apps.productions.models import Category

        link = link_for(org)
        if not link.is_active:
            link.is_active = True
            link.save(update_fields=["is_active"])
        if Inquiry.objects.for_org(org).exists():
            return link
        today = timezone.localdate()
        categories = {c.name: c for c in Category.objects.for_org(org)}
        Inquiry.objects.create(
            organization=org,
            requester_name="Frau Muster",
            requester_email="muster@schule.example",
            requester_role="Klassenleitung 5b",
            event_name="Elternabend",
            category=categories["Sonstiges"],
            date=today + timedelta(days=19),
            start_time=time(19),
            end_time=time(21, 30),
            setup_from=time(17),
            teardown_until=time(22),
            location="Aula",
            tech_needs=["Mikrofone", "Beamer und Leinwand", "Laptop anschließen"],
            tech_notes="Präsentation vom eigenen Laptop (HDMI?), zwei Redner",
            schedule="19:00 Begrüßung\n19:15 Vortrag Schulleitung\n20:00 Fragen",
            contact_name="Herr Beispiel (Hausmeister)",
            contact_phone="0221 123456",
        )
        Inquiry.objects.create(
            organization=org,
            requester_name="SV Schülervertretung",
            requester_email="sv@schule.example",
            requester_role="SV",
            event_name="Abiball",
            date=today + timedelta(days=60),
            tech_notes="Musik und Licht für ca. 300 Gäste",
        )
        done = Inquiry.objects.create(
            organization=org,
            requester_name="Herr Altmann",
            requester_email="altmann@schule.example",
            event_name="Vorlesewettbewerb",
            date=today - timedelta(days=10),
            location="Bibliothek",
            tech_needs=["Mikrofone"],
        )
        mark_done(done, Membership.objects.for_org(org).get(role=Role.TEACHER).user)
        return link

    def _scheduling(self, org):
        from datetime import date, time, timedelta

        from django.utils import timezone

        from apps.scheduling.models import Event, SchoolPeriod, Unavailability
        from apps.scheduling.periods import DEFAULT_PERIODS
        from apps.scheduling.services import create_event

        if SchoolPeriod.objects.for_org(org).exists():
            return
        for number, start, end in DEFAULT_PERIODS:
            SchoolPeriod.objects.create(
                organization=org, number=number, start_time=start, end_time=end
            )
        today = timezone.localdate()
        # Nächster Donnerstag, wöchentlich bis Schuljahresende (30. Juni)
        first = today + timedelta(days=(3 - today.weekday()) % 7 or 7)
        until = date(first.year + (first.month >= 7), 6, 30)
        if not Event.objects.for_org(org).exists():
            create_event(
                org,
                {
                    "title": "AG-Treffen",
                    "date": first,
                    "start_time": time(14),
                    "end_time": time(15, 30),
                    "location": "Technikraum",
                    "notes": "",
                },
                frequency="weekly",
                until=until,
            )
        members = _members(org)
        # Emma schreibt eine Klausur (1.–4. Stunde), Ben ist zwei Tage auf Klassenfahrt
        klausur = today + timedelta(days=2)
        Unavailability.objects.create(
            organization=org,
            membership=members["schueler"],
            start_date=klausur,
            end_date=klausur,
            start_time=time(8),
            end_time=time(11, 20),
            note="Klausur",
        )
        trip = today + timedelta(days=5)
        Unavailability.objects.create(
            organization=org,
            membership=members["ben"],
            start_date=trip,
            end_date=trip + timedelta(days=1),
            note="Klassenfahrt",
        )

    def _team(self, org):
        from datetime import time, timedelta

        from django.utils import timezone

        from apps.productions.models import Skill
        from apps.scheduling.models import Event, EventAttendee

        if Skill.objects.for_org(org).exists():
            return
        members = _members(org)
        skills = {
            "Licht": ["schueler", "owner"],
            "Ton": ["ben", "admin"],
            "Bühne": ["schueler", "ben"],
            "Kamera": ["admin"],
        }
        for i, (name, people) in enumerate(skills.items()):
            skill = Skill.objects.create(organization=org, name=name, position=i)
            skill.members.set(members[p] for p in people)

        # Ein vergangenes AG-Treffen für die Einsatzübersicht
        meeting = Event.objects.create(
            organization=org,
            title="AG-Treffen: Lichtpult-Schulung",
            date=timezone.localdate() - timedelta(days=7),
            start_time=time(14),
            end_time=time(15, 30),
            location="Technikraum",
        )
        for person in ["schueler", "ben", "owner"]:
            EventAttendee.objects.create(
                organization=org,
                event=meeting,
                membership=members[person],
                status=EventAttendee.Status.CONFIRMED,
            )
