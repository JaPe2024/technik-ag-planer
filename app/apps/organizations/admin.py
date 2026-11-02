from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count
from django.http import HttpResponse
from django.utils import timezone
from django.utils.text import slugify

from . import services
from .export import export_organization
from .models import Invitation, Membership, Organization
from .permissions import Role


class OrganizationAdminForm(forms.ModelForm):
    owner_email = forms.EmailField(
        label="E-Mail des Owners",
        required=False,
        help_text=(
            "Neue Adresse: Der Owner bekommt automatisch eine Einladung. "
            "Ist die Person schon Mitglied, wird sie sofort Owner (der bisherige Owner wird Admin)."
        ),
    )

    class Meta:
        model = Organization
        fields = ["name", "is_active", "require_2fa"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        owner = self.instance.owner_membership if self.instance.pk else None
        if owner is not None:
            self.fields["owner_email"].initial = owner.user.email
        if not self.instance.pk:
            self.fields["owner_email"].required = True

    def clean_owner_email(self):
        email = (self.cleaned_data.get("owner_email") or "").strip().lower()
        owner = self.instance.owner_membership if self.instance.pk else None
        unchanged = owner is not None and owner.user.email.lower() == email
        if email and not unchanged and services.is_operator_email(email):
            raise ValidationError(services.OPERATOR_NOT_ALLOWED)
        return email


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0
    fields = ["user", "role", "joined_at"]
    readonly_fields = ["user", "joined_at"]
    can_delete = True
    show_change_link = False

    def has_add_permission(self, request, obj=None):
        return False


class InvitationInline(admin.TabularInline):
    model = Invitation
    extra = 0
    fields = ["email", "role", "status", "created_at", "expires_at"]
    readonly_fields = fields

    @admin.display(description="Status")
    def status(self, obj):
        return obj.status_label

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    form = OrganizationAdminForm
    list_display = ["name", "owner", "member_count", "is_active", "require_2fa", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["name"]
    inlines = [MembershipInline, InvitationInline]
    actions = ["export_data", "resend_owner_invitation", "deactivate", "activate"]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_member_count=Count("memberships"))

    @admin.display(description="Owner")
    def owner(self, obj):
        owner = obj.owner_membership
        if owner:
            return f"{owner.user} <{owner.user.email}>"
        pending = Invitation.objects.for_org(obj).open().filter(role=Role.OWNER).first()
        return f"eingeladen: {pending.email}" if pending else "–"

    @admin.display(description="Mitglieder", ordering="_member_count")
    def member_count(self, obj):
        return obj._member_count

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        email = (form.cleaned_data.get("owner_email") or "").strip().lower()
        if not email:
            return
        current = obj.owner_membership
        if current is not None and current.user.email == email:
            return
        membership = Membership.objects.for_org(obj).filter(user__email__iexact=email).first()
        if membership is not None:
            services.make_owner(membership)
            self.message_user(request, f"{membership.user} ist jetzt Owner der {obj}.")
            return
        try:
            with transaction.atomic():
                services.invite(obj, email, Role.OWNER, invited_by=None)
        except ValidationError as error:
            self.message_user(request, "; ".join(error.messages), messages.ERROR)
        else:
            self.message_user(request, f"Owner-Einladung an {email} verschickt.")

    @admin.action(description="Daten exportieren (ZIP)")
    def export_data(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "Bitte genau eine AG auswählen.", messages.WARNING)
            return None
        org = queryset.get()
        response = HttpResponse(export_organization(org), content_type="application/zip")
        filename = f"export-{slugify(org.name)}-{timezone.localdate():%Y-%m-%d}.zip"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    @admin.action(description="Owner-Einladung erneut senden")
    def resend_owner_invitation(self, request, queryset):
        for org in queryset:
            invitation = (
                Invitation.objects.for_org(org)
                .filter(role=Role.OWNER, accepted_at__isnull=True)
                .order_by("-created_at")
                .first()
            )
            if invitation is None:
                self.message_user(
                    request, f"{org}: keine offene Owner-Einladung.", messages.WARNING
                )
                continue
            services.resend(invitation)
            self.message_user(request, f"{org}: Owner-Einladung an {invitation.email} gesendet.")

    @admin.action(description="Deaktivieren")
    def deactivate(self, request, queryset):
        for org in queryset:
            org.is_active = False
            org.save(update_fields=["is_active"])

    @admin.action(description="Aktivieren")
    def activate(self, request, queryset):
        for org in queryset:
            org.is_active = True
            org.save(update_fields=["is_active"])


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ["email", "organization", "role", "status", "created_at", "expires_at"]
    list_filter = ["role", "organization"]
    search_fields = ["email"]
    fields = [
        "organization",
        "email",
        "role",
        "invited_by",
        "created_at",
        "expires_at",
        "accepted_at",
        "revoked_at",
    ]
    readonly_fields = fields

    @admin.display(description="Status")
    def status(self, obj):
        return obj.status_label

    def has_add_permission(self, request):
        return False
