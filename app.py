# app.py - Complete Hosting Panel Application
import os
import sys
import subprocess
import signal
import zipfile
import threading
import time
import json
import shutil
from functools import wraps
from pathlib import Path
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_socketio import SocketIO, emit
import bcrypt

# Configuration
BASE_DIR = Path(__file__).resolve().parent
PROJECTS_DIR = BASE_DIR / "projects"
UPLOAD_FOLDER = BASE_DIR / "uploads"
ALLOWED_EXTENSIONS = {'zip'}

# Ensure directories exist
PROJECTS_DIR.mkdir(exist_ok=True)
UPLOAD_FOLDER.mkdir(exist_ok=True)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-in-production-2024'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size
socketio = SocketIO(app, cors_allowed_origins="*")

# User database (in production, use a real database)
users = {}

# Process management
processes = {}
process_logs = {}
main_files = ['app.py', 'main.py', 'server.py', 'application.py', 'wsgi.py', 'manage.py']

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated_function

def find_main_file(project_path):
    """Find the main project file to run"""
    for main_file in main_files:
        if (project_path / main_file).exists():
            return main_file
    # Look for any .py file as fallback
    py_files = list(project_path.glob("*.py"))
    if py_files:
        return py_files[0].name
    return None

def get_project_info(project_id):
    """Get detailed information about a project"""
    project_path = PROJECTS_DIR / project_id
    if not project_path.exists():
        return None
    
    main_file = find_main_file(project_path)
    is_running = project_id in processes and processes[project_id]['process'].poll() is None
    
    return {
        'id': project_id,
        'name': project_id,
        'path': str(project_path),
        'main_file': main_file,
        'status': 'running' if is_running else 'stopped',
        'created': datetime.fromtimestamp(project_path.stat().st_ctime).isoformat(),
        'pid': processes[project_id]['process'].pid if is_running and project_id in processes else None
    }

def read_log_lines(project_id, lines=50):
    """Read last N lines of the project's log"""
    log_file = PROJECTS_DIR / project_id / "output.log"
    if not log_file.exists():
        return []
    
    try:
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read().splitlines()[-lines:]
    except:
        return []

# ==================== AUTHENTICATION ROUTES ====================

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    
    if username in users:
        return jsonify({'error': 'User already exists'}), 400
    
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    users[username] = hashed
    return jsonify({'message': 'User created successfully'}), 201

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    if username not in users:
        return jsonify({'error': 'Invalid credentials'}), 401
    
    if bcrypt.checkpw(password.encode('utf-8'), users[username]):
        session['user_id'] = username
        return jsonify({'message': 'Login successful', 'username': username}), 200
    
    return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/api/logout', methods=['POST'])
@login_required
def logout():
    session.pop('user_id', None)
    return jsonify({'message': 'Logged out successfully'}), 200

@app.route('/api/check-auth')
def check_auth():
    if 'user_id' in session:
        return jsonify({'authenticated': True, 'username': session['user_id']})
    return jsonify({'authenticated': False})

# ==================== PROJECT MANAGEMENT ROUTES ====================

@app.route('/api/projects', methods=['GET'])
@login_required
def list_projects():
    projects = []
    for project_dir in PROJECTS_DIR.iterdir():
        if project_dir.is_dir():
            info = get_project_info(project_dir.name)
            if info:
                projects.append(info)
    return jsonify(projects)

@app.route('/api/projects', methods=['POST'])
@login_required
def create_project():
    data = request.json
    project_name = data.get('name', '').strip()
    
    if not project_name:
        return jsonify({'error': 'Project name required'}), 400
    
    project_name = secure_filename(project_name)
    project_path = PROJECTS_DIR / project_name
    
    if project_path.exists():
        return jsonify({'error': 'Project already exists'}), 400
    
    project_path.mkdir()
    return jsonify(get_project_info(project_name)), 201

@app.route('/api/projects/<project_id>', methods=['DELETE'])
@login_required
def delete_project(project_id):
    project_path = PROJECTS_DIR / project_id
    
    if not project_path.exists():
        return jsonify({'error': 'Project not found'}), 404
    
    # Stop process if running
    if project_id in processes:
        stop_process(project_id)
    
    shutil.rmtree(project_path)
    return jsonify({'message': 'Project deleted'}), 200

# ==================== FILE MANAGEMENT ROUTES ====================

@app.route('/api/projects/<project_id>/upload', methods=['POST'])
@login_required
def upload_file(project_id):
    project_path = PROJECTS_DIR / project_id
    
    if not project_path.exists():
        return jsonify({'error': 'Project not found'}), 404
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    filename = secure_filename(file.filename)
    filepath = project_path / filename
    file.save(filepath)
    
    # Check if it's a zip file
    if filename.endswith('.zip'):
        try:
            # Extract zip file
            with zipfile.ZipFile(filepath, 'r') as zip_ref:
                zip_ref.extractall(project_path)
            
            # Remove zip file after extraction
            filepath.unlink()
            
            main_file = find_main_file(project_path)
            return jsonify({
                'message': 'ZIP file uploaded and extracted successfully!',
                'extracted': True,
                'main_file': main_file
            }), 200
        except Exception as e:
            return jsonify({
                'error': f'Extraction failed: {str(e)}',
                'extracted': False
            }), 500
    else:
        # Regular file upload
        return jsonify({
            'message': 'File uploaded successfully',
            'extracted': False
        }), 200

@app.route('/api/projects/<project_id>/extract-zip', methods=['POST'])
@login_required
def extract_zip_file(project_id):
    """Manually extract a zip file in the project directory"""
    data = request.json
    zip_path = data.get('zip_path', '')
    
    project_path = PROJECTS_DIR / project_id
    full_zip_path = project_path / zip_path
    
    if not full_zip_path.exists():
        return jsonify({'error': 'ZIP file not found'}), 404
    
    if not full_zip_path.suffix.lower() == '.zip':
        return jsonify({'error': 'File is not a ZIP archive'}), 400
    
    try:
        # Extract to the same directory as the zip file
        extract_to = full_zip_path.parent
        
        with zipfile.ZipFile(full_zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)
        
        main_file = find_main_file(project_path)
        
        return jsonify({
            'message': f'Successfully extracted {zip_path}',
            'extracted': True,
            'main_file': main_file
        }), 200
    except Exception as e:
        return jsonify({
            'error': f'Extraction failed: {str(e)}',
            'extracted': False
        }), 500

@app.route('/api/projects/<project_id>/files', methods=['GET'])
@login_required
def list_files(project_id):
    project_path = PROJECTS_DIR / project_id
    
    if not project_path.exists():
        return jsonify({'error': 'Project not found'}), 404
    
    path = request.args.get('path', '')
    current_path = project_path / path if path else project_path
    
    if not current_path.exists():
        return jsonify({'error': 'Path not found'}), 404
    
    items = []
    for item in current_path.iterdir():
        if item.name.startswith('.'):
            continue
        items.append({
            'name': item.name,
            'path': str(item.relative_to(project_path)),
            'type': 'directory' if item.is_dir() else 'file',
            'size': item.stat().st_size if item.is_file() else None,
            'modified': datetime.fromtimestamp(item.stat().st_mtime).isoformat()
        })
    
    return jsonify({
        'current_path': path,
        'items': sorted(items, key=lambda x: (x['type'] != 'directory', x['name'].lower()))
    })

@app.route('/api/projects/<project_id>/file', methods=['GET'])
@login_required
def get_file_content(project_id):
    file_path = request.args.get('path', '')
    project_path = PROJECTS_DIR / project_id
    full_path = project_path / file_path
    
    if not full_path.exists() or full_path.is_dir():
        return jsonify({'error': 'File not found'}), 404
    
    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return jsonify({'content': content, 'path': file_path})
    except UnicodeDecodeError:
        return jsonify({'error': 'Cannot display binary file'}), 400
    except Exception as e:
        return jsonify({'error': f'Could not read file: {str(e)}'}), 500

@app.route('/api/projects/<project_id>/file', methods=['PUT'])
@login_required
def save_file_content(project_id):
    data = request.json
    file_path = data.get('path', '')
    content = data.get('content', '')
    
    project_path = PROJECTS_DIR / project_id
    full_path = project_path / file_path
    
    if not full_path.exists():
        return jsonify({'error': 'File not found'}), 404
    
    try:
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return jsonify({'message': 'File saved successfully'})
    except Exception as e:
        return jsonify({'error': f'Could not save file: {str(e)}'}), 500

@app.route('/api/projects/<project_id>/file', methods=['DELETE'])
@login_required
def delete_file(project_id):
    data = request.json
    file_path = data.get('path', '')
    
    project_path = PROJECTS_DIR / project_id
    full_path = project_path / file_path
    
    if not full_path.exists():
        return jsonify({'error': 'File not found'}), 404
    
    try:
        if full_path.is_dir():
            shutil.rmtree(full_path)
        else:
            full_path.unlink()
        return jsonify({'message': 'Deleted successfully'})
    except Exception as e:
        return jsonify({'error': f'Could not delete: {str(e)}'}), 500

@app.route('/api/projects/<project_id>/file/rename', methods=['POST'])
@login_required
def rename_file(project_id):
    data = request.json
    old_path = data.get('old_path', '')
    new_name = data.get('new_name', '')
    
    project_path = PROJECTS_DIR / project_id
    old_full_path = project_path / old_path
    new_full_path = old_full_path.parent / new_name
    
    if not old_full_path.exists():
        return jsonify({'error': 'File not found'}), 404
    
    try:
        old_full_path.rename(new_full_path)
        return jsonify({'message': 'Renamed successfully', 'new_path': str(new_full_path.relative_to(project_path))})
    except Exception as e:
        return jsonify({'error': f'Could not rename: {str(e)}'}), 500

@app.route('/api/projects/<project_id>/folder', methods=['POST'])
@login_required
def create_folder(project_id):
    data = request.json
    folder_path = data.get('path', '')
    
    project_path = PROJECTS_DIR / project_id
    full_path = project_path / folder_path
    
    try:
        full_path.mkdir(parents=True, exist_ok=True)
        return jsonify({'message': 'Folder created successfully'})
    except Exception as e:
        return jsonify({'error': f'Could not create folder: {str(e)}'}), 500

# ==================== PROCESS MANAGEMENT ROUTES ====================

@app.route('/api/projects/<project_id>/start', methods=['POST'])
@login_required
def start_project(project_id):
    project_path = PROJECTS_DIR / project_id
    
    if not project_path.exists():
        return jsonify({'error': 'Project not found'}), 404
    
    if project_id in processes and processes[project_id]['process'].poll() is None:
        return jsonify({'message': 'Project already running'}), 200
    
    main_file = find_main_file(project_path)
    if not main_file:
        return jsonify({'error': 'No main project file found (app.py, main.py, etc.)'}), 400
    
    log_file = project_path / "output.log"
    
    try:
        with open(log_file, 'a') as f:
            process = subprocess.Popen(
                [sys.executable, str(project_path / main_file)],
                cwd=str(project_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                text=True,
                bufsize=1
            )
        
        processes[project_id] = {
            'process': process,
            'log_file': log_file,
            'main_file': main_file
        }
        
        def read_log_output(pid):
            proc = processes[pid]['process']
            log_path = processes[pid]['log_file']
            
            with open(log_path, 'a') as log_f:
                for line in iter(proc.stdout.readline, ''):
                    if line:
                        timestamp = datetime.now().strftime('%H:%M:%S')
                        formatted_line = f'[{timestamp}] {line.rstrip()}'
                        log_f.write(formatted_line + '\n')
                        log_f.flush()
                        socketio.emit('console_output', {
                            'project_id': pid,
                            'line': formatted_line
                        })
                    if proc.poll() is not None:
                        break
        
        thread = threading.Thread(target=read_log_output, args=(project_id,), daemon=True)
        thread.start()
        
        return jsonify({'message': 'Project started', 'main_file': main_file, 'pid': process.pid}), 200
    except Exception as e:
        return jsonify({'error': f'Failed to start: {str(e)}'}), 500

def stop_process(project_id):
    if project_id not in processes:
        return False
    
    proc_info = processes[project_id]
    process = proc_info['process']
    
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
    
    del processes[project_id]
    return True

@app.route('/api/projects/<project_id>/stop', methods=['POST'])
@login_required
def stop_project(project_id):
    if project_id not in processes:
        return jsonify({'message': 'Project not running'}), 200
    
    stop_process(project_id)
    return jsonify({'message': 'Project stopped'}), 200

@app.route('/api/projects/<project_id>/restart', methods=['POST'])
@login_required
def restart_project(project_id):
    stop_process(project_id)
    time.sleep(0.5)
    return start_project(project_id)

@app.route('/api/projects/<project_id>/status')
@login_required
def project_status(project_id):
    if project_id not in processes:
        return jsonify({'status': 'stopped', 'running': False})
    
    process = processes[project_id]['process']
    is_running = process.poll() is None
    
    return jsonify({
        'status': 'running' if is_running else 'stopped',
        'running': is_running,
        'pid': process.pid if is_running else None
    })

@app.route('/api/projects/<project_id>/logs')
@login_required
def get_logs(project_id):
    project_path = PROJECTS_DIR / project_id
    log_file = project_path / "output.log"
    
    if not log_file.exists():
        return jsonify({'logs': []})
    
    lines = request.args.get('lines', 100, type=int)
    try:
        with open(log_file, 'r') as f:
            logs = f.read().splitlines()[-lines:]
        return jsonify({'logs': logs})
    except:
        return jsonify({'logs': []})

# ==================== SOCKET.IO EVENTS ====================

@socketio.on('connect')
def handle_connect():
    if 'user_id' in session:
        emit('connected', {'message': f'Connected as {session["user_id"]}'})

@socketio.on('subscribe_console')
def handle_subscribe_console(data):
    project_id = data.get('project_id')
    if project_id:
        logs = read_log_lines(project_id, 50)
        for log in logs:
            emit('console_output', {'project_id': project_id, 'line': log})

@socketio.on('execute_command')
def handle_execute_command(data):
    project_id = data.get('project_id')
    command = data.get('command', '').strip()
    
    if not command or project_id not in processes:
        return
    
    project_path = PROJECTS_DIR / project_id
    log_file = project_path / "output.log"
    
    timestamp = datetime.now().strftime('%H:%M:%S')
    input_line = f'[{timestamp}] > {command}'
    
    try:
        with open(log_file, 'a') as f:
            f.write(input_line + '\n')
        
        socketio.emit('console_output', {
            'project_id': project_id,
            'line': input_line
        })
    except:
        pass

# ==================== FRONTEND ROUTES ====================

@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/project/<project_id>')
@login_required
def project_detail(project_id):
    return render_template('project_detail.html', project_id=project_id)

# ==================== MAIN ENTRY POINT ====================

# Railway ডিপ্লয়মেন্টের জন্য
if __name__ == '__main__':
    # লোকাল রানিং এর জন্য
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV', 'development') == 'development'
    
    print("=" * 50)
    print("🚀 Nexus Hosting Panel")
    print("=" * 50)
    print(f"📁 Projects directory: {PROJECTS_DIR}")
    print(f"📤 Uploads directory: {UPLOAD_FOLDER}")
    print(f"🌐 Server running on port: {port}")
    print("=" * 50)
    
    if debug:
        socketio.run(app, host='0.0.0.0', port=port, debug=True, allow_unsafe_werkzeug=True)
    else:
        # প্রোডাকশনের জন্য (gunicorn ব্যবহার করবে)
        socketio.run(app, host='0.0.0.0', port=port, debug=False)