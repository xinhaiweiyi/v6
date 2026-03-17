from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from accounts.models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ["-created_at"]
    list_display = ["email", "username", "role", "is_active", "is_staff", "created_at"]
    search_fields = ["email", "username"]
    list_filter = ["role", "is_active", "is_staff"]
    fieldsets = (
        ("基础信息", {"fields": ("email", "username", "password", "role", "avatar")}),
        ("权限", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("时间", {"fields": ("last_login", "date_joined", "created_at", "updated_at")}),
    )
    readonly_fields = ["last_login", "date_joined", "created_at", "updated_at"]
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "username", "role", "password1", "password2", "is_staff", "is_superuser"),
            },
        ),
    )
