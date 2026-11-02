from datetime import time, timedelta

import pytest
from django.utils import timezone

from apps.inquiries.models import Inquiry
from apps.inquiries.services import link_for


@pytest.fixture
def active_link(org):
    link = link_for(org)
    link.is_active = True
    link.save()
    return link


@pytest.fixture
def make_inquiry():
    def factory(organization, event_name="Elternabend", **extra):
        extra.setdefault("requester_name", "Frau Muster")
        extra.setdefault("requester_email", "muster@schule.example")
        extra.setdefault("date", timezone.localdate() + timedelta(days=14))
        return Inquiry.objects.create(organization=organization, event_name=event_name, **extra)

    return factory


@pytest.fixture
def evening(org, make_inquiry):
    return make_inquiry(
        org,
        start_time=time(19),
        end_time=time(21, 30),
        setup_from=time(17),
        teardown_until=time(22),
        location="Aula",
        tech_needs=["Mikrofone", "Beamer und Leinwand"],
        contact_phone="0221 123456",
    )
