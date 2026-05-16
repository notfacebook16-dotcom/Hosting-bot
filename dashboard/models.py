from django.db import models
from django.contrib.auth.models import User
import os

class UserFile(models.Model):
    FILE_CATEGORIES = [
        ('python', 'Python Script'),
        ('archive', 'Archive File'),
        ('document', 'Document'),
        ('image', 'Image'),
        ('code', 'Code File'),
        ('other', 'Other'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='files')
    file = models.FileField(upload_to='uploads/%Y/%m/%d/')
    original_filename = models.CharField(max_length=255)
    file_size = models.BigIntegerField()
    category = models.CharField(max_length=20, choices=FILE_CATEGORIES, default='other')
    is_main_file = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-uploaded_at']
    
    def get_file_size_mb(self):
        return round(self.file_size / (1024 * 1024), 2)
    
    def get_icon(self):
        icons = {'python': 'fab fa-python', 'archive': 'fas fa-file-archive', 
                 'document': 'fas fa-file-alt', 'image': 'fas fa-file-image',
                 'code': 'fas fa-code', 'other': 'fas fa-file'}
        return icons.get(self.category, 'fas fa-file')
    
    def get_color(self):
        colors = {'python': '#3776AB', 'archive': '#FF9800', 'document': '#2196F3',
                  'image': '#9C27B0', 'code': '#4CAF50', 'other': '#94a3b8'}
        return colors.get(self.category, '#94a3b8')
    
    def delete(self, *args, **kwargs):
        if self.file and os.path.isfile(self.file.path):
            os.remove(self.file.path)
        super().delete(*args, **kwargs)

class ServerLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='logs')
    action = models.CharField(max_length=50)
    details = models.JSONField(default=dict)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']