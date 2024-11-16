from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory, abort
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Email, EqualTo, Length
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import LARGE_BINARY
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import IntegrityError
from psycopg2 import ProgrammingError
import os
from dotenv import load_dotenv
import bcrypt
import requests
import mimetypes
import uuid
import re
from bleach import clean, linkify
from markdown import markdown
from flask_socketio import SocketIO, emit, join_room, leave_room
from datetime import datetime
import json
import pytz  # For timezone handling
import requests


load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY", "your-secret-key")
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL")
app.config['UPLOAD_FOLDER'] = 'uploads'  # Temporary folder (not used for database storage)
# Allowed file types and size limits (in bytes)
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'docx', 'xlsx', 'pptx', 'csv', 'py', 'js', 'html', 'css'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

socketio = SocketIO(app, manage_session=False, cors_allowed_origins="*")  # Initialize Socket.IO

# Configure Gemini API Key
GEMINI_API_KEY = os.environ.get("AIzaSyAj9jIkgyvWxEAmXOT4NtwtbvEgexNfyzQ")
gemini_api_url = "https://api.generativeai.google.com/v1beta2"



# Database Models (same as before)
# ... (User, Folder, File models)

# Forms
class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=2, max=20)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Sign Up')


class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')


class FileForm(FlaskForm):
    name = StringField("Filename", validators=[DataRequired()])
    content = TextAreaField("File Content")  # Use TextAreaField for larger text content
    submit = SubmitField("Save")


# User Loader
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
# Allowed file types and size limits (in bytes) - Moved to global scope
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'docx', 'xlsx', 'pptx', 'csv', 'py', 'js', 'html', 'css'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


#Utility Functions
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def sanitize_filename(filename):
     # Sanitize filename to prevent path traversal and other attacks.
    sanitized = re.sub(r'[\\/*?:"<>|]', "", filename)
    return sanitized or "sanitized_file"


def render_markdown(content):
    """Renders markdown content to safe HTML."""
    allowed_tags = [  # Reduced list of allowed HTML tags
        'a', 'abbr', 'acronym', 'b', 'blockquote', 'code',
        'em', 'i', 'li', 'ol', 'pre', 'strong', 'ul', 'h1', 'h2', 'h3', 'p', 'br'
    ]
    cleaned_content = clean(content, tags=allowed_tags, attributes={'a': ['href', 'rel']})  # Use bleach.clean
    html_content = markdown(cleaned_content, extensions=['codehilite']) # Use markdown.markdown
    # Linkify URLs (optional)
    linkified_content = linkify(html_content)  # Use bleach.linkify (if needed)
    return linkified_content



# Routes
@app.route('/')
@login_required  # Removed unnecessary redirect, protected route directly
def index():
    files = File.query.filter_by(user_id=current_user.id, folder_id=None).all()  # Get user's files in root
    folders = Folder.query.filter_by(user_id=current_user.id, parent_folder_id=None).all() # Get folders in root
    return render_template('index.html', files=files, folders=folders)



@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = RegistrationForm()
    if form.validate_on_submit():

        # Sanitize username before database operations
        sanitized_username = form.username.data.strip()
        sanitized_email = form.email.data.strip()

        user = User(username=sanitized_username, email=sanitized_email)  # Sanitize input
        user.set_password(form.password.data)
        try:
            db.session.add(user)
            db.session.commit()
            flash('Your account has been created! You are now able to log in', 'success')
            return redirect(url_for('login'))
        except IntegrityError:  # Handle unique constraint violations
            db.session.rollback()
            flash("Username or email already exists. Please choose a different one.", "danger")

    return render_template('register.html', title='Register', form=form)


# Routes (Continued)
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            next_page = request.args.get('next')  # Handle "next" parameter for redirects
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else:
            flash('Login Unsuccessful. Please check username and password', 'danger')
    return render_template('login.html', title='Login', form=form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))  # Redirect to login after logout


@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':

        if 'file' not in request.files:
            flash('No file part', 'danger')
            return redirect(request.url)
        file = request.files['file']

        if file.filename == '':
            flash('No selected file', 'danger')
            return redirect(request.url)

        if file and allowed_file(file.filename) and file.content_length <= MAX_FILE_SIZE:
            # Sanitize filename:
            filename = sanitize_filename(file.filename)

            try:
                # Read and store file content using PostgreSQL Large Object
                content = file.read()

                new_file = File(name=filename, content=content, user_id=current_user.id)
                db.session.add(new_file)
                db.session.commit()
                flash('File uploaded successfully!', 'success')
                return redirect(url_for('index'))
            except Exception as e:  # Handle database errors
                db.session.rollback()
                flash(f"Error uploading file: {e}", 'danger')

        else:
            if not allowed_file(file.filename):
                flash(f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}", 'danger')
            elif file.content_length > MAX_FILE_SIZE:
                flash('File too large. Maximum size is 10MB', 'danger')

    return render_template('upload.html')  # Provide the upload.html template


@app.route('/download/<int:file_id>')
@login_required
def download(file_id):
    file = File.query.filter_by(id=file_id, user_id=current_user.id).first_or_404()
    mimetype = mimetypes.guess_type(file.name)[0] or "application/octet-stream"  # Securely determine MIME type

    return Response(file.content, mimetype=mimetype, headers={
        'Content-Disposition': f'attachment; filename={file.name}',  # Secure filename handling
        'Content-Length': len(file.content)
    })
# ... (register, login, logout, upload, download routes)


@app.route('/edit/<int:file_id>', methods=['GET', 'POST'])
@login_required
def edit(file_id):
    file = File.query.filter_by(id=file_id, user_id=current_user.id).first_or_404()
    form = FileForm()


    if form.validate_on_submit():

        sanitized_content = form.content.data
        file.content = sanitized_content.encode('utf-8') # Store as bytes
        db.session.commit()
        flash('File saved!', 'success')
        return redirect(url_for('index'))

    elif request.method == 'GET':

        form.content.data = file.content.decode('utf-8') # Decode for display in form



    return render_template('edit.html', title='Edit File', form=form, file=file)


@app.route('/delete/<int:file_id>', methods=['POST'])  # Changed to POST for security
@login_required
def delete_file(file_id):
    file = File.query.filter_by(id=file_id, user_id=current_user.id).first_or_404()
    db.session.delete(file)
    db.session.commit()
    flash('File deleted!', 'success')
    return redirect(url_for('index'))





class FolderForm(FlaskForm):
    name = StringField('Folder Name', validators=[DataRequired()])
    submit = SubmitField('Create Folder')


@app.route('/create_folder', methods=['GET', 'POST'])
@login_required
def create_folder():
    form = FolderForm()
    if form.validate_on_submit():
        sanitized_name = form.name.data.strip()
        folder = Folder(name=sanitized_name, user_id=current_user.id)
        db.session.add(folder)
        db.session.commit()
        flash('Folder created!', 'success')
        return redirect(url_for('index'))
    return render_template('create_folder.html', form=form)




@app.route('/folder/<int:folder_id>')
@login_required
def folder(folder_id):
    folder = Folder.query.filter_by(id=folder_id, user_id=current_user.id).first_or_404()
    files = File.query.filter_by(folder_id=folder_id, user_id=current_user.id).all()
    subfolders = Folder.query.filter_by(parent_folder_id=folder_id, user_id=current_user.id).all()
    return render_template('folder.html', folder=folder, files=files, subfolders=subfolders)  # Pass subfolders


@app.route('/delete_folder/<int:folder_id>', methods=['POST'])
@login_required
def delete_folder(folder_id):
    folder = Folder.query.filter_by(id=folder_id, user_id=current_user.id).first_or_404()


    # Check if the folder is empty
    if folder.files or Folder.query.filter_by(parent_folder_id=folder.id).count() > 0:
        flash('Cannot delete a non-empty folder. Please delete the contents first.', 'danger')

    else:

        db.session.delete(folder)
        db.session.commit()
        flash('Folder deleted!', 'success')
    return redirect(url_for('index'))
@app.route('/gemini_api/<int:file_id>/sentiment', methods=['POST'])
@login_required
def gemini_sentiment(file_id):
    return gemini_api_call(file_id, 'sentiment')


@app.route('/gemini_api/<int:file_id>/grammar', methods=['POST'])
@login_required
def gemini_grammar(file_id):
    return gemini_api_call(file_id, 'grammar')



@app.route('/gemini_api/<int:file_id>/summarization', methods=['POST'])
@login_required
def gemini_summarization(file_id):
    return gemini_api_call(file_id, 'summarization')



@app.route('/gemini_api/<int:file_id>/ner', methods=['POST'])
@login_required
def gemini_ner(file_id):
    return gemini_api_call(file_id, 'ner')






def gemini_api_call(file_id, feature):  # Helper function for Gemini API calls

    file = File.query.filter_by(id=file_id, user_id=current_user.id).first_or_404()
    text_content = file.content.decode('utf-8')


    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {GEMINI_API_KEY}"
    }

    # Construct API request based on the feature
    if feature == "sentiment":

        data = {"text": text_content}
        api_endpoint = f"{gemini_api_url}/sentiment" # Replace with Gemini Sentiment Analysis endpoint
    elif feature == 'grammar':
        data = {"text": text_content}
        api_endpoint = f"{gemini_api_url}/grammar"  # Replace with Gemini Grammar Check endpoint
    # Add other features (summarization, NER, etc.) with appropriate endpoints and data
    elif feature == 'summarization':
        data = {"text": text_content}
        api_endpoint = f"{gemini_api_url}/summarization"
    elif feature == 'ner':
        data = {"text": text_content}
        api_endpoint = f"{gemini_api_url}/ner"
    else:

        return jsonify({'error': 'Invalid Gemini API feature'}), 400




    try:
        response = requests.post(api_endpoint, headers=headers, json=data)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        return jsonify(response.json())
    except requests.exceptions.RequestException as e:
        return jsonify({'error': str(e)}), 500




@socketio.on('join')
def on_join(data):
    file_id = data['file_id']
    join_room(file_id)  # Join the room for the specific file



@socketio.on('leave')
def on_leave(data):
    file_id = data['file_id']
    leave_room(file_id)



@socketio.on('edit')
def handle_file_edit(data):
    file_id = data['file_id']
    new_content = data['content']
    # ... (Update the file content in the database)
    file = File.query.get(file_id)
    if file:  # Update only if file exists
        file.content = new_content.encode('utf-8')
        db.session.commit()
        emit('update', {'content': new_content}, room=file_id)  # Broadcast update to clients in the room



# Example error handler
@app.errorhandler(404)
def page_not_found(error):
    return render_template('404.html'), 404


@app.route('/gemini_api/<int:file_id>/<string:feature>', methods=['POST'])
@login_required
def gemini_api_call(file_id, feature):
    file = File.query.filter_by(id=file_id, user_id=current_user.id).first_or_404()

    try:
        text_content = file.content.decode('utf-8')  # Decode file content
    except UnicodeDecodeError:
        return jsonify({'error': 'File content decoding error'}), 500

    if not GEMINI_API_KEY:  # Check if API key is set
        return jsonify({'error': 'Gemini API key not configured.'}), 500


    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {GEMINI_API_KEY}"
    }

    creative_type = request.json.get("type")

    prompt = {
        "text": text_content
    }


    data = {
        "model": "gemini-pro-1.5",  # Specify the model
        "prompt": prompt
    }



    if feature == "creative_generation":
        creative_types = {
            "poem": f"Write a poem based on this text:\n{text_content}",
            "code": f"Generate Python code that does the following:\n{text_content}",
            "script": f"Write a short movie script based on:\n{text_content}",
            "music": f"Compose a short musical piece based on this description:\n{text_content}",
            "email": f"Write a formal email about:\n{text_content}",
            "letter": f"Write a letter based on:\n{text_content}",
            "internet_search": f"Search the internet for information about: {text_content}",
            "current_temperature": f"What is the current temperature in {text_content}?",
            "current_datetime": f"What is the current date and time in UTC?",  # Example for current date/time
        }

        if creative_type not in creative_types:
            return jsonify({"error": "Invalid creative type"}), 400

        data["prompt"]["text"] = creative_types[creative_type]  # Set prompt based on type
        api_endpoint = f"{gemini_api_url}/text"  # Use /text for creative generation

    elif feature == "sentiment":
        api_endpoint = f"{gemini_api_url}/sentiment"
    # ... other API features (add more as needed) ...
    else:
        return jsonify({'error': 'Invalid Gemini API feature'}), 400


    try:
        response = requests.post(api_endpoint, headers=headers, json=data, timeout=60)  # Set a timeout
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        gemini_response = response.json()

        # Post-processing and enhancements (add more as needed)
        if feature == "creative_generation":
                if creative_type == "current_temperature":
                    temperature_info = extract_temperature(gemini_response)  # Call the function here

                    if "error" in temperature_info:  # Handle potential errors
                        gemini_response["temperature_error"] = temperature_info["error"]  # Add error to response
                    else:
                        gemini_response["temperature"] = temperature_info  # Add temperature to response


            elif creative_type == "current_datetime":
                gemini_response["current_datetime"] = datetime.now(pytz.utc).isoformat()

        return jsonify(gemini_response)

    except requests.exceptions.Timeout:
        return jsonify({'error': 'Request timed out'}), 504  # 504 Gateway Timeout for timeouts
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'API request failed: {e}'}), 500 # More informative error messages
def extract_temperature(gemini_response):
    """
    Extracts temperature information from Gemini's response.

    Args:
        gemini_response: The JSON response from the Gemini API.

    Returns:
        A dictionary containing the temperature value and unit, or an error message
        if the temperature cannot be extracted.
    """
    try:
        # 1. Attempt to parse as JSON:
        response_data = gemini_response  # Gemini's response is assumed to be JSON

        # 2. Use regular expressions for more flexible extraction
        temperature_match = re.search(r"(\d+\.?\d*) ?(°[CF]|degrees (Celsius|Fahrenheit))", response_data["text"])
        if temperature_match:
            temperature_value = float(temperature_match.group(1))
            temperature_unit = temperature_match.group(2)
            return {"value": temperature_value, "unit": temperature_unit}

        # 3. Provide a default or error message
        return {"error": "Could not extract temperature. Please try a different location or rephrase your query."}

    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError, AttributeError) as e:  # Handle various potential errors
        return {"error": f"Error processing temperature information: {e}"}
@app.route('/move_file/<int:file_id>/<int:folder_id>', methods=['POST'])
@login_required
def move_file(file_id, folder_id):
    file = File.query.get_or_404(file_id)
    if file.user_id != current_user.id:  # Check user ownership
        abort(403)  # Forbidden

    folder = Folder.query.get_or_404(folder_id)
    if folder.user_id != current_user.id:  # Check folder user_id
        abort(403)

    file.folder_id = folder_id
    db.session.commit()
    return jsonify({"message": "File moved successfully"}), 200


@app.route('/user_profile', methods=['GET'])
@login_required
def user_profile():
    return render_template('user_profile.html')
@socketio.on('join')
def on_join(data):
    file_id = data['fileId']
    join_room(file_id)

    # Notify other users (optional):
    emit('user_joined', {'username': current_user.username, 'fileId': file_id}, room=file_id)



@socketio.on('leave')
def on_leave(data):
    file_id = data['fileId']
    leave_room(file_id)

    # Notify other users (optional):
    emit('user_left', {'username': current_user.username, 'fileId': file_id}, room=file_id)




@socketio.on('edit')
def handle_file_edit(data):
    file_id = data['fileId']
    new_content = data['content']
    file = File.query.get(file_id)
    if file:
        file.content = new_content.encode('utf-8')
        db.session.commit()
        emit('update', {'content': new_content, 'fileId': file_id}, room=file_id)

{% for file in files %}
<tr>
    <td>{{ file.name }}</td>
    <td>{{ file.size }}</td>  {# Assuming you have a file.size attribute #}
    <td>{{ file.modified }}</td> {# Assuming you have a file.modified attribute #}
    <td>
        <button class="btn btn-primary sentiment-btn" data-file-id="{{ file.id }}">Sentiment</button>
        <button class="btn btn-secondary grammar-btn" data-file-id="{{ file.id }}">Grammar</button>

        <button class="btn btn-info summarization-btn" data-file-id="{{ file.id }}">Summarization</button>
        <button class="btn btn-warning ner-btn" data-file-id="{{ file.id }}">NER</button>

        <button class="btn btn-dark creative-generation-btn" data-file-id="{{ file.id }}" data-type="poem">Poem</button>
        <button class="btn btn-dark creative-generation-btn" data-file-id="{{ file.id }}" data-type="code">Code</button>

        </button>
    </td>
</tr>
{% endfor %}
