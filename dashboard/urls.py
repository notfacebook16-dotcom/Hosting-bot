from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('api/files/', views.api_files, name='api_files'),
    path('api/upload/', views.api_upload, name='api_upload'),
    path('api/set-main-file/', views.api_set_main_file, name='api_set_main_file'),
    path('api/download/<int:file_id>/', views.download_file, name='download_file'),
    path('api/delete/<int:file_id>/', views.api_delete_file, name='api_delete_file'),
]