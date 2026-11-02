"""Regel aus CLAUDE.md: Farben ausschließlich über die Design-Tokens aus tokens.css."""

import hashlib
import re
from pathlib import Path

from apps.core.design import THEME_COLOR

APP_DIR = Path(__file__).resolve().parent.parent
TOKENS = APP_DIR / "static" / "css" / "tokens.css"
SCANNED_DIRS = [APP_DIR / "static", APP_DIR / "templates", APP_DIR / "apps"]
# Unveränderte Fremdbibliothek: eigene Scanneroberfläche bleibt tokengeprüft.
QR_VENDOR = APP_DIR / "static" / "vendor" / "html5-qrcode.min.js"
QR_VENDOR_SHA256 = "660b12437b1d747e3e68b8be0685c08cb728140110ad213f167b14b66f8b1d8e"
SCANNED_SUFFIXES = {".css", ".js", ".html"}

COLOR_LITERAL = re.compile(r"#[0-9a-fA-F]{3,8}\b|\b(?:rgba?|hsla?|oklch|oklab)\(")

# Farben aus Abschnitt 1 der Feature-Liste
SPEC_COLORS = {
    "--color-bg": "#0F1115",
    "--color-surface": "#171A21",
    "--color-surface-raised": "#1F232C",
    "--color-line": "#2A2F3A",
    "--color-primary": "#003397",
    "--color-accent": "#8787FF",
    "--color-text": "#F2F3F5",
    "--color-text-muted": "#9AA0AC",
}


def _token_values():
    return dict(re.findall(r"(--[\w-]+):\s*([^;]+);", TOKENS.read_text()))


def test_no_color_literals_outside_tokens():
    offenders = []
    for directory in SCANNED_DIRS:
        for path in directory.rglob("*"):
            if path in (TOKENS, QR_VENDOR) or path.suffix not in SCANNED_SUFFIXES:
                continue
            for number, line in enumerate(path.read_text().splitlines(), start=1):
                if COLOR_LITERAL.search(line):
                    offenders.append(f"{path.relative_to(APP_DIR)}:{number}: {line.strip()}")

    assert not offenders, "Farbwerte außerhalb von tokens.css:\n" + "\n".join(offenders)


def test_tokens_match_feature_list():
    values = _token_values()
    for name, value in SPEC_COLORS.items():
        assert values[name].split()[0].upper() == value


def test_theme_color_matches_background_token():
    assert _token_values()["--color-bg"].split()[0].upper() == THEME_COLOR.upper()


def test_qr_vendor_is_pinned_and_licensed():
    assert hashlib.sha256(QR_VENDOR.read_bytes()).hexdigest() == QR_VENDOR_SHA256
    license_text = QR_VENDOR.with_name("html5-qrcode.LICENSE").read_text()
    assert "Apache License" in license_text and "Version 2.0" in license_text
