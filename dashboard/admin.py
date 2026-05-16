from django.contrib import admin
from .models import UserFile, ServerLog

@admin.register(UserFile)
class UserFileAdmin(admin.ModelAdmin):
    list_display = ['original_filename', 'user', 'category', 'is_main_file', 'uploaded_at']
    list_filter = ['category', 'is_main_file']
    search_fields = ['original_filename', 'user__username']

@admin.register(ServerLog)
class ServerLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'action', 'timestamp']
    list_filter = ['action']