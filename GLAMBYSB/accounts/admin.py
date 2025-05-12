from django.contrib import admin

# Register your models here.
from .models import EmailVerification

class EmailVerificationAdmin(admin.ModelAdmin):
    # Customize the list display to show relevant fields
    list_display = ('user', 'token', 'is_verified', 'created_at')
    
    # Allow searching by user and token for quick lookup
    search_fields = ('user__username', 'token')

    # Add filters to easily filter by verification status
    list_filter = ('is_verified',)

# Register the model with the customized admin interface
admin.site.register(EmailVerification, EmailVerificationAdmin)