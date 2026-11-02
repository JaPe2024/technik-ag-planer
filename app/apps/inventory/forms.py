from django import forms
from django.db.models import Q
from django.forms import inlineformset_factory

from apps.productions.forms import ChipSelect, palette_widget

from . import services
from .models import DefectReport, Kit, KitItem, Material, MaterialCategory, MaterialLink


class MaterialForm(forms.ModelForm):
    class Meta:
        model = Material
        fields = ["name", "category", "quantity", "tracking", "notes"]
        widgets = {
            "name": forms.TextInput(attrs={"autofocus": True}),
            "quantity": forms.NumberInput(attrs={"min": 0, "placeholder": "beliebig"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        if not organization.inventory_qr_enabled:
            self.fields.pop("tracking")
        else:
            self.fields["tracking"].required = False
        categories = MaterialCategory.objects.for_org(organization)
        self.fields["category"].queryset = categories
        self.fields["category"].empty_label = "Keine"
        self.fields["category"].widget = ChipSelect(
            choices=self.fields["category"].choices,
            color_of={str(c.pk): c.color for c in categories},
        )

    def clean_tracking(self):
        value = (
            self.cleaned_data.get("tracking") or self.instance.tracking or Material.Tracking.BULK
        )
        if (
            self.instance.pk
            and value != self.instance.tracking
            and (
                self.instance.units.exists()
                or self.instance.plannings.filter(movements__isnull=False).exists()
            )
        ):
            raise forms.ValidationError(
                "Nach Geräteerfassung oder Ausgabe ist die Verwaltungsart festgelegt. "
                "Bitte eine neue Materialart anlegen."
            )
        return value


class MaterialLinkForm(forms.ModelForm):
    url = forms.URLField(
        label="Link",
        max_length=500,
        assume_scheme="https",
        widget=forms.URLInput(attrs={"placeholder": "https://…"}),
    )

    class Meta:
        model = MaterialLink
        fields = ["title", "url"]


MaterialLinkFormSet = inlineformset_factory(
    Material, MaterialLink, form=MaterialLinkForm, extra=0, can_delete=True
)


class DefectForm(forms.ModelForm):
    class Meta:
        model = DefectReport
        fields = ["quantity", "description"]
        widgets = {"quantity": forms.NumberInput(attrs={"min": 1})}

    photo = forms.FileField(
        label="Foto",
        required=False,
        help_text="Optional – wird im Google Drive der AG gespeichert.",
        widget=forms.ClearableFileInput(attrs={"accept": "image/*", "capture": "environment"}),
    )

    def __init__(self, *args, material, allow_photo=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.material = material
        self.fields["quantity"].min_value = 1
        self.fields["description"].widget.attrs["autofocus"] = True
        if not allow_photo:  # Fotos nur mit verbundenem Google-Konto
            del self.fields["photo"]

    def clean_photo(self):
        from apps.google_sync.forms import clean_image

        return clean_image(self.cleaned_data.get("photo"))

    def clean_quantity(self):
        quantity = self.cleaned_data["quantity"]
        if quantity < 1:
            raise forms.ValidationError("Mindestens 1.")
        stock = services.available(self.material)
        if stock is not None and quantity > stock:
            raise forms.ValidationError(f"Es sind nur noch {stock} Stück verfügbar (nicht defekt).")
        return quantity


class PlanForm(forms.Form):
    material = forms.ModelChoiceField(
        queryset=None, label="Material", empty_label="Material wählen"
    )
    quantity = forms.IntegerField(label="Menge", min_value=1, initial=1)
    ignore_conflicts = forms.BooleanField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["material"].queryset = (
            Material.objects.for_org(organization).active().select_related("category")
        )
        self.fields["material"].label_from_instance = lambda m: (
            f"{m.name}" + (f" ({m.category})" if m.category_id else "")
        )


class PlanKitForm(forms.Form):
    kit = forms.ModelChoiceField(queryset=None, label="Materialsatz", empty_label="Satz wählen")
    ignore_conflicts = forms.BooleanField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["kit"].queryset = Kit.objects.for_org(organization)


class PlannedQuantityForm(forms.Form):
    quantity = forms.IntegerField(label="Menge", min_value=1)
    ignore_conflicts = forms.BooleanField(required=False, widget=forms.HiddenInput)


class KitForm(forms.ModelForm):
    class Meta:
        model = Kit
        fields = ["name", "description"]
        widgets = {
            "name": forms.TextInput(attrs={"autofocus": True}),
            "description": forms.Textarea(attrs={"rows": 2}),
        }


class KitItemForm(forms.ModelForm):
    class Meta:
        model = KitItem
        fields = ["material", "quantity"]
        widgets = {"quantity": forms.NumberInput(attrs={"min": 1})}

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Archiviertes Material ist nicht wählbar – außer es steht schon im Satz
        current = Q(pk=self.instance.material_id) if self.instance.material_id else Q(pk=None)
        self.fields["material"].queryset = Material.objects.for_org(organization).filter(
            Q(archived_at__isnull=True) | current
        )
        self.fields["material"].empty_label = "Material wählen"
        self.fields["quantity"].min_value = 1


class BaseKitItemFormSet(forms.BaseInlineFormSet):
    def clean(self):
        # Vor super().clean(), damit diese Meldung statt der allgemeinen Duplikat-Meldung kommt
        seen = set()
        for form in self.forms:
            if not hasattr(form, "cleaned_data") or form.cleaned_data.get("DELETE"):
                continue
            material = form.cleaned_data.get("material")
            if material is None:
                continue
            if material.pk in seen:
                raise forms.ValidationError(
                    f"„{material}“ steht zweimal im Satz – bitte die Mengen zusammenfassen."
                )
            seen.add(material.pk)
        super().clean()


KitItemFormSet = inlineformset_factory(
    Kit, KitItem, form=KitItemForm, formset=BaseKitItemFormSet, extra=1, can_delete=True
)


class MaterialCategoryForm(forms.ModelForm):
    class Meta:
        model = MaterialCategory
        fields = ["name", "color"]
        widgets = {"color": palette_widget()}
