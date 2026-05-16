from django import forms
from .models import UserFile

class FileUploadForm(forms.Form):
    file = forms.FileField(
        widget=forms.FileInput(attrs={'class': 'form-control', 'multiple': True})
    )