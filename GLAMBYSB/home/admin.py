from django.contrib import admin
from django.utils.html import format_html
from .models import *
import logging

logger = logging.getLogger(__name__)
# Register your models here.
@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ('brand_id', 'brand_name', 'image_preview')  # Adjust as per your model fields
    search_fields = ['brand_id', 'brand_name']
    actions = ['download_csv_template']

    def image_preview(self, obj):
        if obj.image:  # Make sure to use the correct field name here
            return format_html('<img src="{}" style="width: 150px; height: auto;" />', obj.image.url)
        return "No Image Uploaded"
    image_preview.short_description = 'Image Preview'