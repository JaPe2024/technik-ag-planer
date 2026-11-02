from django import forms
from django.forms import inlineformset_factory

from apps.organizations.models import Membership
from apps.scheduling.forms import PeriodTimesMixin, SegmentedRadio

from .models import (
    Category,
    CrewAssignment,
    Job,
    Production,
    ProductionLink,
    ProductionStatus,
    Skill,
    Todo,
)
from .palette import Color


class DateInput(forms.DateInput):
    input_type = "date"

    def __init__(self, **kwargs):
        super().__init__(format="%Y-%m-%d", **kwargs)


class TimeInput(forms.TimeInput):
    input_type = "time"

    def __init__(self, **kwargs):
        super().__init__(format="%H:%M", **kwargs)


class ChipSelect(forms.RadioSelect):
    """Auswahl als Chips (Kategorie, Farbe)."""

    template_name = "productions/widgets/chips.html"
    option_template_name = "productions/widgets/chip_option.html"

    def __init__(self, *args, color_of=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.color_of = color_of or {}

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        key = getattr(value, "value", value)
        option["color"] = self.color_of.get(str(key), "")
        return option


def palette_widget():
    return ChipSelect(color_of={c.value: c.value for c in Color})


class ProductionForm(forms.ModelForm):
    class Meta:
        model = Production
        fields = [
            "name",
            "category",
            "start_date",
            "end_date",
            "status",
            "location_name",
            "address",
            "notes",
            "chat_enabled",
        ]
        widgets = {
            "start_date": DateInput(),
            "end_date": DateInput(),
            "notes": forms.Textarea(attrs={"rows": 3}),
            "name": forms.TextInput(attrs={"autofocus": True}),
        }

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        categories = Category.objects.for_org(organization)
        self.fields["category"].queryset = categories
        self.fields["category"].empty_label = "Keine"
        self.fields["category"].widget = ChipSelect(
            choices=self.fields["category"].choices,
            color_of={str(c.pk): c.color for c in categories},
        )
        self.fields["status"].queryset = ProductionStatus.objects.for_org(organization)
        self.fields["status"].empty_label = None
        if not self.instance.pk:
            self.fields["status"].initial = ProductionStatus.planning_for(organization).pk
        self.fields["chat_enabled"].help_text = "Alle Mitglieder können ihn lesen und schreiben."

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("start_date"), cleaned.get("end_date")
        if start and end and end < start:
            self.add_error("end_date", "„Bis“ darf nicht vor „Von“ liegen.")
        return cleaned


class JobForm(PeriodTimesMixin, forms.ModelForm):
    class Meta:
        model = Job
        fields = ["name", "date", "start_time", "end_time", "meeting_point", "crew_needed"]
        widgets = {"date": DateInput(), "start_time": TimeInput(), "end_time": TimeInput()}

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.setup_periods(organization)


JobFormSet = inlineformset_factory(
    Production, Job, form=JobForm, extra=1, can_delete=True, min_num=0
)


class StatusChangeForm(forms.Form):
    status = forms.ModelChoiceField(queryset=None, label="Status", empty_label=None)

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["status"].queryset = ProductionStatus.objects.for_org(organization)


class CrewForm(forms.Form):
    membership = forms.ModelChoiceField(
        queryset=None, label="Mitglied", empty_label="Mitglied wählen"
    )
    role_label = forms.CharField(
        label="Position",
        max_length=40,
        required=False,
        help_text="z. B. FOH, Bühne, Monitor",
    )
    status = forms.ChoiceField(
        label="Art",
        choices=[
            (CrewAssignment.Status.REQUESTED, "Anfragen"),
            (CrewAssignment.Status.CONFIRMED, "Direkt einteilen"),
        ],
        initial=CrewAssignment.Status.REQUESTED,
        widget=SegmentedRadio,
    )
    ignore_conflicts = forms.BooleanField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, job, skill=None, **kwargs):
        super().__init__(*args, **kwargs)
        taken = job.crew.values_list("membership_id", flat=True)
        queryset = (
            Membership.objects.for_org(job.organization)
            .exclude(pk__in=taken)
            .select_related("user")
            .prefetch_related("skills")
            .order_by("user__display_name")
        )
        if skill is not None:
            queryset = queryset.filter(skills=skill)
        self.fields["membership"].queryset = queryset
        self.fields["membership"].label_from_instance = _member_label


def _member_label(m):
    """„Emma (Q1) – Licht, Ton“"""
    label = f"{m.user}" + (f" ({m.user.get_grade_display()})" if m.user.grade else "")
    skills = ", ".join(s.name for s in m.skills.all())
    return f"{label} – {skills}" if skills else label


class TodoForm(forms.ModelForm):
    class Meta:
        model = Todo
        fields = ["text"]
        labels = {"text": "Neues To-do"}


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "color"]
        widgets = {"color": palette_widget()}


class ProductionLinkForm(forms.ModelForm):
    url = forms.URLField(
        label="Link",
        max_length=500,
        assume_scheme="https",
        widget=forms.URLInput(attrs={"placeholder": "https://…"}),
    )

    class Meta:
        model = ProductionLink
        fields = ["title", "url"]


class SkillForm(forms.ModelForm):
    class Meta:
        model = Skill
        fields = ["name"]
        help_texts = {"name": "z. B. Licht, Ton, Bühne, Kamera"}


class MySkillsForm(forms.Form):
    skills = forms.ModelMultipleChoiceField(
        queryset=None,
        label="Meine Fähigkeiten",
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["skills"].queryset = Skill.objects.for_org(organization)


class HoursForm(forms.Form):
    corrected_hours = forms.DecimalField(
        label="Tatsächliche Stunden",
        required=False,
        min_value=0,
        max_value=99,
        decimal_places=2,
        help_text="Leer lassen, um die Stunden aus den Zeiten zu berechnen.",
        widget=forms.NumberInput(attrs={"step": "0.25", "inputmode": "decimal"}),
    )


class StatusForm(forms.ModelForm):
    class Meta:
        model = ProductionStatus
        fields = ["name", "color"]
        widgets = {"color": palette_widget()}
