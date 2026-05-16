# Iftekhar Hosting Dashboard

A modern file management and server control dashboard for Django.

## Features
- File upload with drag & drop
- Automatic file categorization
- Set main file for execution
- Modern UI with dark theme
- Responsive design

## Deployment on Railway

1. Fork this repository to GitHub
2. Create account on [Railway.app](https://railway.app)
3. Click "New Project" → "Deploy from GitHub repo"
4. Select your repository
5. Add environment variables:
   - `SECRET_KEY` = your-secret-key
   - `DEBUG` = False

## Local Development

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver