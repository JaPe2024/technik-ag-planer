"""Einzelauswahl sieht überall gleich aus: Schalter statt einfacher Radio-Punkte."""

from pathlib import Path

from django.conf import settings

from apps.notifications.forms import SettingsForm
from apps.scheduling.forms import EventEditScopeForm, SegmentedRadio

APP_DIR = Path(settings.BASE_DIR)
ALLOWED = {"segmented_option.html", "chip_option.html"}


def test_templates_use_radios_only_inside_switches():
    for template in (APP_DIR / "templates").rglob("*.html"):
        content = template.read_text()
        if template.name in ALLOWED or 'type="radio"' not in content:
            continue
        assert "segmented--choice" in content, f"Einfache Radio-Punkte in {template}"


def test_forms_use_segmented_switch():
    assert isinstance(SettingsForm().fields["reminder_mode"].widget, SegmentedRadio)
    assert isinstance(EventEditScopeForm().fields["scope"].widget, SegmentedRadio)
