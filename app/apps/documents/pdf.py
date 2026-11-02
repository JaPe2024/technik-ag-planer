"""HTML-Vorlagen → PDF mit WeasyPrint (ADR 0010)."""

from functools import cache

from django.contrib.staticfiles import finders
from django.http import HttpResponse
from django.template.loader import render_to_string

STYLESHEETS = ["css/tokens.css", "css/documents.css"]


@cache
def _stylesheets():
    from weasyprint import CSS

    return [CSS(filename=finders.find(path)) for path in STYLESHEETS]


def render_pdf(request, template, context):
    """Rendert das Dokument-Template (dasselbe wie in der Vorschau) als PDF."""
    from weasyprint import HTML

    html = render_to_string(
        "documents/pdf.html", {**context, "body_template": template}, request=request
    )
    return HTML(string=html).write_pdf(stylesheets=_stylesheets())


def pdf_response(content, filename, *, download=False):
    response = HttpResponse(content, content_type="application/pdf")
    disposition = "attachment" if download else "inline"
    response["Content-Disposition"] = f'{disposition}; filename="{filename}"'
    response["Cache-Control"] = "private, no-store"
    return response
