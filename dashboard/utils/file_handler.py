import os
from ..models import UserFile

class FileHandler:
    
    @classmethod
    def get_category(cls, filename):
        ext = os.path.splitext(filename)[1].lower()
        if ext == '.py': return 'python'
        if ext in ['.zip', '.tar', '.gz']: return 'archive'
        if ext in ['.pdf', '.txt', '.md']: return 'document'
        if ext in ['.jpg', '.png', '.gif']: return 'image'
        if ext in ['.html', '.css', '.js']: return 'code'
        return 'other'
    
    @classmethod
    def save_file(cls, uploaded_file, user):
        category = cls.get_category(uploaded_file.name)
        return UserFile.objects.create(
            user=user,
            file=uploaded_file,
            original_filename=uploaded_file.name,
            file_size=uploaded_file.size,
            category=category
        )
    
    @classmethod
    def set_main_file(cls, user, file_id):
        UserFile.objects.filter(user=user, is_main_file=True).update(is_main_file=False)
        UserFile.objects.filter(id=file_id, user=user).update(is_main_file=True)
