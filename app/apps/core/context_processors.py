from apps.board.services import nav_unread_count
from apps.inquiries.models import Inquiry
from apps.organizations.permissions import Perm
from apps.organizations.settings_menu import CUSTOMIZE_URL_NAMES

from . import navigation as sections
from .design import THEME_COLOR


def _open_inquiry_count(membership):
    """Hinweis in der Navigation, nur für alle, die Technik-Anfragen sehen dürfen."""
    if membership is None or not membership.has_perm(Perm.HANDLE_INQUIRIES):
        return 0
    return Inquiry.objects.for_org(membership.organization).open().count()


def navigation(request):
    membership = getattr(request, "membership", None)
    new_items = [
        item
        for item in sections.NEW_ITEMS
        if membership is not None and membership.has_perm(item["perm"])
    ]
    return {
        # Formulare im Bottom-Sheet: nur den Inhalt ohne Seitenrahmen ausliefern
        "layout": "fragment.html" if request.headers.get("X-Sheet") else "base.html",
        "theme_color": THEME_COLOR,
        "nav_sidebar": sections.SIDEBAR,
        "nav_mobile_left": sections.MOBILE_LEFT,
        "nav_mobile_right": sections.MOBILE_RIGHT,
        "nav_mobile_more": sections.MOBILE_MORE,
        "nav_new_items": new_items,
        "nav_settings": sections.SETTINGS,
        "nav_unread_count": nav_unread_count(membership) if membership is not None else 0,
        "nav_open_inquiry_count": _open_inquiry_count(membership),
        "nav_in_customize": (
            request.resolver_match is not None
            and request.resolver_match.view_name in CUSTOMIZE_URL_NAMES
        ),
        "current_membership": membership,
        "current_organization": getattr(request, "organization", None),
        "user_memberships": getattr(request, "memberships", []),
        "org_perms": getattr(request, "org_perms", None),
    }
