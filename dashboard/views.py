from django.shortcuts import render, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse, HttpResponse
from .models import UserFile, ServerLog
from .utils.file_handler import FileHandler

@staff_member_required
def dashboard(request):
    files = UserFile.objects.filter(user=request.user)
    return render(request, 'dashboard/dashboard.html', {
        'files': files,
        'total_files': files.count(),
        'total_size': sum(f.file_size for f in files),
        'current_main': files.filter(is_main_file=True).first()
    })

@staff_member_required
def api_files(request):
    files = UserFile.objects.filter(user=request.user)
    return JsonResponse({
        'success': True,
        'files': [{
            'id': f.id,
            'original_filename': f.original_filename,
            'size_mb': f.get_file_size_mb(),
            'size_bytes': f.file_size,
            'category': f.category,
            'category_display': f.get_category_display(),
            'is_main_file': f.is_main_file,
            'uploaded_at': f.uploaded_at.isoformat(),
            'icon': f.get_icon(),
            'color': f.get_color()
        } for f in files]
    })

@staff_member_required
def api_upload(request):
    if request.method == 'POST' and request.FILES.get('file'):
        try:
            file = FileHandler.save_file(request.FILES['file'], request.user)
            return JsonResponse({'success': True, 'file_id': file.id})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    return JsonResponse({'success': False, 'error': 'No file'}, status=400)

@staff_member_required
def api_set_main_file(request):
    if request.method == 'POST':
        file_id = request.POST.get('file_id')
        FileHandler.set_main_file(request.user, int(file_id))
        return JsonResponse({'success': True, 'message': 'Main file set successfully'})
    return JsonResponse({'success': False}, status=400)

@staff_member_required
def download_file(request, file_id):
    user_file = get_object_or_404(UserFile, id=file_id, user=request.user)
    if os.path.exists(user_file.file.path):
        with open(user_file.file.path, 'rb') as f:
            response = HttpResponse(f.read(), content_type='application/octet-stream')
            response['Content-Disposition'] = f'attachment; filename="{user_file.original_filename}"'
            return response
    return JsonResponse({'error': 'File not found'}, status=404)

@staff_member_required
def api_delete_file(request, file_id):
    user_file = get_object_or_404(UserFile, id=file_id, user=request.user)
    user_file.delete()
    return JsonResponse({'success': True})