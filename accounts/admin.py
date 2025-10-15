from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Profile

class CustomUserAdmin(UserAdmin):
    model = User

    list_display = ('username', 'email', 'role', 'is_staff', 'is_active', 'email_verified')
    list_filter = ('role', 'is_staff', 'is_active', 'email_verified')

    fieldsets = UserAdmin.fieldsets + (
        (None, {'fields': ('role', 'email_verified', 'verification_code', 'is_oauth_user', 'username_set')}),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        (None, {'fields': ('role', 'email_verified', 'is_oauth_user', 'username_set')}),
    )

    search_fields = ('email', 'username')
    ordering = ('email',)

admin.site.register(User, CustomUserAdmin)
admin.site.register(Profile)
