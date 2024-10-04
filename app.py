from flask import Flask, render_template, request, redirect, url_for, session, flash, abort, send_file, request
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from urllib.parse import quote
from flask_migrate import Migrate
from werkzeug.utils import secure_filename
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.message import EmailMessage
import random
from datetime import datetime, timedelta


import os
from datetime import datetime, timedelta
from models import User, BloodPressureReading, db, BloodPressureAnalysis
from dotenv import load_dotenv
from werkzeug.exceptions import RequestEntityTooLarge
import re
from functools import wraps
import uuid
from PIL import Image
import google.generativeai as genai
from sqlalchemy import func
import json
from io import BytesIO, StringIO
import csv
from sqlalchemy.engine import Engine
from sqlalchemy import event
import random
from markupsafe import  escape


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA date_string_format = '%Y-%m-%d'")
    cursor.close()

# Load environment variables
load_dotenv()

# Set up Gemini API
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-1.5-flash')

app = Flask(__name__)

# Add this line to set the app name
app.config['APP_NAME'] = os.getenv('APP_NAME', 'Simple BP Tracker')

# Configuration for SQLite database
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URI', 'sqlite:///bp_tracker.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configuration for SMTP (Mail) service
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
app.config['MAIL_PORT'] = os.getenv('MAIL_PORT', 587)
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_EMAIL'] = os.getenv('MAIL_EMAIL')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['GEMINI_API_KEY'] = os.getenv('GEMINI_API_KEY')


# Upload folder configuration
app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER','static/uploads')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}


# Setup Flask app, MySQL, and SMTP


db.init_app(app)
migrate = Migrate(app, db)
# Setting up Flask-Mail (as done in step 1)
mail = Mail(app)

# Serializer for generating and verifying magic links
serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])

# Email validation regex
EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')



def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('index'))
        user = User.query.get(session['user_id'])
        if user is None:
            session.clear()
            flash('User not found. Please log in again.', 'warning')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# Route for home page
@app.route('/')
def index():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user:
            return redirect(url_for('dashboard'))
    return render_template('index.html')

# Route for sign-up page
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        name = request.form.get('name', '').strip()

        if not email or not name:
            flash('Email and name are required.', 'danger')
            return redirect(url_for('signup'))

        if not EMAIL_REGEX.match(email):
            flash('Invalid email format.', 'danger')
            return redirect(url_for('signup'))

        try:
            user = User.query.filter_by(email=email).first()
            if user:
                flash('Email already registered. A magic link has been sent to sign you in.', 'info')
                send_magic_link(email)
            else:
                new_user = User(email=email, name=name, created_at=datetime.utcnow())
                db.session.add(new_user)
                db.session.commit()
                send_magic_link(email)
                flash('Registration successful. A magic link has been sent to your email.', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred: {str(e)}', 'danger')
            return redirect(url_for('signup'))

    return render_template('signup.html')

# Route for sending magic link to existing users
@app.route('/signin', methods=['POST'])
def signin():
    email = request.form.get('email', '').strip()

    if not email or not EMAIL_REGEX.match(email):
        flash('There was a problem with your submission. The email address you entered appears to be invalid. Please check and try again.', 'danger')
        return redirect(url_for('index'))

    try:
        user = User.query.filter_by(email=email).first()
        if user:
            send_magic_link(email)
        else:
            new_user = User(email=email, name="")
            db.session.add(new_user)
            db.session.commit()
            send_magic_link(email)
            flash('Registration successful. Please use the provided link to sign in.', 'success')
        
        # Only redirect if email settings are configured
        if app.config['MAIL_SERVER'] and app.config['MAIL_USERNAME'] and app.config['MAIL_PASSWORD']:
            return redirect(url_for('magic_link_sent', email=email))
        else:
            return redirect(url_for('index'))
    except Exception as e:
        db.session.rollback()
        flash(f'An error occurred: {str(e)}', 'danger')
        return redirect(url_for('index'))

@app.route('/magic_link_sent')
def magic_link_sent():
    email = request.args.get('email', '')
    email_domain = email.split('@')[-1] if '@' in email else ''
    
    email_providers = {
        'gmail.com': 'https://mail.google.com',
        'yahoo.com': 'https://mail.yahoo.com',
        'outlook.com': 'https://outlook.live.com',
        'hotmail.com': 'https://outlook.live.com',
        # Add more email providers as needed
    }
    
    email_provider_url = email_providers.get(email_domain, '#')
    
    return render_template('magic_link_sent.html', email=email, email_provider_url=email_provider_url)

def send_email(subject, body, email):
    try:
        sender = app.config['MAIL_USERNAME']
        password = app.config['MAIL_PASSWORD']
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"{app.config['APP_NAME']} <{app.config['MAIL_EMAIL']}>"
        msg['To'] = email

        # Plain text version of the email
        text_part = MIMEText(body, 'plain')
        msg.attach(text_part)

        # HTML version of the email
        html_part = MIMEText(body, 'html')
        msg.attach(html_part)

        with smtplib.SMTP_SSL(app.config['MAIL_SERVER'], app.config['MAIL_PORT']) as smtp_server:
            smtp_server.login(sender, password)
            smtp_server.sendmail(app.config['MAIL_EMAIL'], email, msg.as_string())
            print("Message sent!")
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        raise

def get_base_url():
    return request.url_root.rstrip('/')

def generate_magic_email_html(magic_link):
    base_url = get_base_url()
    return render_template('emails/magic_link.html', 
                           magic_link=magic_link, 
                           app_name=app.config['APP_NAME'],
                           base_url=base_url)

def send_magic_link(email):
    try:
        user = User.query.filter_by(email=email).first()
        if not user:
            raise ValueError("User not found")

        token = serializer.dumps(email, salt='email-confirm-salt')
        magic_link = url_for('verify_magic_link', token=token, _external=True)

        # Check if email settings are configured
        if app.config['MAIL_SERVER'] and app.config['MAIL_USERNAME'] and app.config['MAIL_PASSWORD']:
            subject = f'Your Magic Link to {app.config["APP_NAME"]}'
            html_body = generate_magic_email_html(magic_link)
            send_email(subject, html_body, email)
            flash('A magic link has been sent to your email. Please check your inbox to sign in.', 'success')
        else:
            # If email settings are not configured, display the magic link directly
            flash('Email settings are not configured. Please use the following link to sign in:', 'warning')
            flash(f'<a href="{magic_link}">Click here to complete the sign in</a>', 'info')
            flash('Note: In a production environment, this link would be sent via email for security reasons.', 'warning')

    except Exception as e:
        app.logger.error(f"Error sending magic link: {str(e)}")
        flash(f"Error: {str(e)}", 'danger')
        raise

# Route to verify magic link and log in the user
@app.route('/verify_magic_link/<token>')
def verify_magic_link(token):
    try:
        email = serializer.loads(token, salt='email-confirm-salt', max_age=3600)
    except SignatureExpired:
        flash('The magic link has expired.', 'danger')
        return redirect(url_for('index'))
    except BadSignature:
        flash('The magic link is invalid.', 'danger')
        return redirect(url_for('index'))

    user = User.query.filter_by(email=email).first()
    if user:
        session['user_id'] = user.id
        session['user_name'] = user.name
        user.update_last_login()
        flash('Logged in successfully!', 'success')
        return redirect(url_for('dashboard'))
    else:
        flash('User not found.', 'danger')
        return redirect(url_for('index'))

# Dashboard route
@app.route('/dashboard')
@login_required
def dashboard():
    user = User.query.get(session['user_id'])
    
    # Get the total number of readings
    total_readings = BloodPressureReading.query.filter_by(user_id=user.id).count()
    
    if total_readings == 0:
        # If there are no readings, return a simplified template
        return render_template('dashboard.html', 
                               name=user.name, 
                               total_readings=total_readings)
    
    # If there are readings, proceed with the existing logic
    # Get the 5 most recent readings
    recent_readings = BloodPressureReading.query.filter_by(user_id=user.id).order_by(BloodPressureReading.timestamp.desc()).limit(5).all()
    
    # Get average readings for the last 30 days
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    avg_readings = db.session.query(
        func.avg(BloodPressureReading.systolic).label('avg_systolic'),
        func.avg(BloodPressureReading.diastolic).label('avg_diastolic'),
        func.avg(BloodPressureReading.pulse).label('avg_pulse')
    ).filter(
        BloodPressureReading.user_id == user.id,
        BloodPressureReading.timestamp >= thirty_days_ago
    ).first()
    

    

    # Prepare data for the chart
    chart_data = db.session.query(
        func.date(BloodPressureReading.timestamp).label('date'),
        func.avg(BloodPressureReading.systolic).label('avg_systolic'),
        func.avg(BloodPressureReading.diastolic).label('avg_diastolic'),
        func.avg(BloodPressureReading.pulse).label('avg_pulse')
    ).filter(
        BloodPressureReading.user_id == user.id,
        BloodPressureReading.timestamp >= thirty_days_ago
    ).group_by(func.date(BloodPressureReading.timestamp)).order_by('date').all()

    dates = [entry.date if isinstance(entry.date, str) else entry.date.strftime('%Y-%m-%d') for entry in chart_data]
    systolic_data = [float(entry.avg_systolic) for entry in chart_data]
    diastolic_data = [float(entry.avg_diastolic) for entry in chart_data]
    pulse_data = [float(entry.avg_pulse) for entry in chart_data]

    chart_json = json.dumps({
        'dates': dates,
        'systolic': systolic_data,
        'diastolic': diastolic_data,
        'pulse': pulse_data
    })
    
    # Fetch the latest analysis summary if it exists
    recent_analysis = BloodPressureAnalysis.query.filter_by(user_id=user.id).order_by(BloodPressureAnalysis.created_at.desc()).first()
    analysis_summary = None
    if recent_analysis:
        analysis_json = json.loads(recent_analysis.analysis_text)
        analysis_summary = analysis_json.get('summary', None)
    
    return render_template('dashboard.html', 
                           name=user.name, 
                           recent_readings=recent_readings, 
                           avg_readings=avg_readings, 
                           total_readings=total_readings,
                           chart_data=chart_json,
                           analysis_summary=analysis_summary)

# Add this function for server-side validation
def validate_profile_data(form_data):
    errors = {}
    current_year = datetime.now().year

    if not form_data.get('name'):
        errors['name'] = 'Name is required.'

    if not form_data.get('gender'):
        errors['gender'] = 'Gender selection is required.'

    try:
        year_of_birth = int(form_data.get('year_of_birth', ''))
        if year_of_birth < 1900 or year_of_birth > current_year:
            errors['year_of_birth'] = 'Please enter a valid year of birth.'
    except ValueError:
        errors['year_of_birth'] = 'Year of birth must be a number.'

    try:
        height = float(form_data.get('height', ''))
        if height < 50 or height > 300:
            errors['height'] = 'Please enter a valid height in cm (between 50 and 300).'
    except ValueError:
        errors['height'] = 'Height must be a number.'

    try:
        weight = float(form_data.get('weight', ''))
        if weight < 20 or weight > 500:
            errors['weight'] = 'Please enter a valid weight in kg (between 20 and 500).'
    except ValueError:
        errors['weight'] = 'Weight must be a number.'

    if not form_data.get('activity_level'):
        errors['activity_level'] = 'Activity level selection is required.'

    return errors


@app.route('/complete_profile', methods=['GET', 'POST'])
@login_required
def complete_profile():
    user = User.query.get(session['user_id'])
    if request.method == 'POST':
        form_data = request.form
        errors = validate_profile_data(form_data)

        if not errors:
            user.name = form_data['name']
            user.gender = form_data['gender']
            user.year_of_birth = int(form_data['year_of_birth'])
            user.height = float(form_data['height'])
            user.weight = float(form_data['weight'])
            user.occupation = form_data['occupation']
            user.activity_level = form_data['activity_level']
            user.profile_completed = True
            user.updated_at = datetime.utcnow()
            db.session.commit()
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('dashboard'))
        else:
            for field, error in errors.items():
                flash(f"{error}", 'danger')

    return render_template('complete_profile.html', user=user)




# Log out route
@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('index'))

# Route for uploading a new blood pressure reading
# Route for uploading a new blood pressure reading
def validate_bp_reading(systolic, diastolic, pulse):
    errors = []
    if systolic < 60 or systolic > 300:
        errors.append("Systolic pressure should be between 60 and 300 mmHg.")
    if diastolic < 40 or diastolic > 200:
        errors.append("Diastolic pressure should be between 40 and 200 mmHg.")
    if pulse < 30 or pulse > 220:
        errors.append("Pulse should be between 30 and 220 bpm.")
    if systolic <= diastolic:
        errors.append("Systolic pressure should be higher than diastolic pressure.")
    return errors

@app.route('/new_reading', methods=['GET', 'POST'])
@login_required
def new_reading():
    user = User.query.get(session['user_id'])
    if not user.profile_completed:
        flash('Please complete your profile before adding a new reading.', 'info')
        return redirect(url_for('complete_profile'))

    if request.method == 'POST':
        try:
            entry_method = request.form['entry_method']
            reading_datetime = datetime.strptime(request.form['reading_datetime'], '%Y-%m-%dT%H:%M')

            # Set default values
            systolic = None
            diastolic = None
            pulse = None
            image_filename = None
            reading_type_id = None

            if entry_method == 'manual':
                systolic = int(request.form['systolic'])
                diastolic = int(request.form['diastolic'])
                pulse = int(request.form['pulse'])
                reading_type_id = 1  # Manual entry
                
                # Validate the readings
                errors = validate_bp_reading(systolic, diastolic, pulse)
                if errors:
                    for error in errors:
                        flash(error, 'danger')
                    return redirect(request.url)
                
            elif entry_method == 'image':
                if app.config['GEMINI_API_KEY'] is None or app.config['GEMINI_API_KEY'] == '':
                    flash('Gemini API key is not set. Please set the GEMINI_API_KEY environment variable to use this feature.', 'danger')
                    return redirect(request.url)
                
                if 'bp_image' not in request.files:
                    flash('No file part', 'danger')
                    return redirect(request.url)

                file = request.files['bp_image']
                if file.filename == '':
                    flash('No selected file', 'danger')
                    return redirect(request.url)

                if file and allowed_file(file.filename):
                    # Generate a unique filename
                    file_extension = os.path.splitext(file.filename)[1]
                    if not file_extension:
                        flash('Invalid file name', 'danger')
                        return redirect(request.url)
                    
                    unique_filename = f"{session['user_id']}_{uuid.uuid4().hex}{file_extension}"
                    
                    if not os.path.exists(app.config['UPLOAD_FOLDER']):
                            os.makedirs(app.config['UPLOAD_FOLDER'])
                    
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                    
                    # Save and resize the image if necessary
                    img = Image.open(file)
                    if img.width > 1200:
                        ratio = 1200 / img.width
                        new_size = (1200, int(img.height * ratio))
                        img = img.resize(new_size, Image.LANCZOS)
                    
                    img.save(file_path, optimize=True, quality=85)
                    
                    systolic, diastolic, pulse = extract_bp_from_image(file_path)
                    if systolic is None or diastolic is None or pulse is None:
                        flash('Failed to extract blood pressure values from the image. <br /><br />Please confirm that the image uploaded is clear and is actually of a digital blood pressure monitor after a reading has been taken.', 'danger')
                        return redirect(request.url)
                    
                    # Validate the extracted readings
                    errors = validate_bp_reading(systolic, diastolic, pulse)
                    if errors:
                        for error in errors:
                            flash(error, 'danger')
                        return redirect(request.url)
                    
                    image_filename = unique_filename
                    reading_type_id = 2  # Image upload
                else:
                    flash('Invalid file type. Please upload a PNG, JPG, or JPEG image.', 'danger')
                    return redirect(request.url)
            else:
                flash('Invalid entry method', 'danger')
                return redirect(request.url)

            # Ensure all required fields are present
            if systolic is None or diastolic is None or pulse is None or reading_type_id is None:
                flash('Missing required data for blood pressure reading', 'danger')
                return redirect(request.url)

            new_reading = BloodPressureReading(
                user_id=session['user_id'],
                systolic=systolic,
                diastolic=diastolic,
                pulse=pulse,
                timestamp=reading_datetime,
                image_filename=image_filename,
                reading_type_id=reading_type_id,
                analysis_status_id=1,  # Default value
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.session.add(new_reading)
            db.session.commit()

            flash('New reading added successfully.', 'success')
            return redirect(url_for('my_readings'))

        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error in new_reading: {str(e)}")
            flash(f'An error occurred: {str(e)}', 'danger')
            return redirect(request.url)

    return render_template('new_reading.html')

# Route for displaying the user's readings and trends
@app.route('/my_readings')
@login_required
def my_readings():
    try:
        user_id = session['user_id']
        total_readings = BloodPressureReading.query.filter_by(user_id=user_id).count()
        page = request.args.get('page', 1, type=int)
        per_page = 25  # Number of readings per page

        pagination = BloodPressureReading.query.filter_by(user_id=user_id).order_by(BloodPressureReading.timestamp.desc()).paginate(page=page, per_page=per_page, error_out=False)
        readings = pagination.items
        if not readings:
            flash('Please add your first reading to continue!', 'info')
            return redirect(url_for('new_reading'))
        
        timestamps = [reading.timestamp.strftime('%Y-%m-%d %H:%M') for reading in readings]
        systolic_values = [reading.systolic for reading in readings]
        diastolic_values = [reading.diastolic for reading in readings]

        return render_template('my_readings.html', readings=readings, timestamps=timestamps,
                               systolic_values=systolic_values, diastolic_values=diastolic_values,
                               total_readings=total_readings,
                               pagination=pagination)
    except Exception as e:
        app.logger.error(f"Error in my_readings: {str(e)}")
        flash(f'An error occurred: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))


# Function to check allowed file types
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Function to extract blood pressure values from an image using Gemini API
def extract_bp_from_image(image_path):
    try:
        # Open the image
        img = Image.open(image_path)

        # Prepare the prompt
        prompt = "Analyze the attached image of a digital blood pressure monitor. Extract the following three key values from the display:\
1. **Systolic**: The upper blood pressure reading (usually the larger number).\
2. **Diastolic**: The lower blood pressure reading (usually the smaller number).\
3. **Pulse**: The heart rate reading, typically labeled as Pulse or represented by a heart symbol.\
 Provide only the numeric values for each, separated by commas, in that order."

        # Generate content using Gemini
        response = model.generate_content([prompt, img])

        # Parse the response
        values = response.text.strip().split(',')
        if len(values) == 3:
            systolic = int(values[0])
            diastolic = int(values[1])
            pulse = int(values[2])
            return systolic, diastolic, pulse
        else:
            raise ValueError("Unexpected response format from Gemini API")

    except Exception as e:
        app.logger.error(f"Error extracting BP from image: {str(e)}")
        return None, None, None

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

@app.route('/privacy-policy')
def privacy_policy():
    return render_template('privacy_policy.html')

@app.route('/terms-and-conditions')
def terms_and_conditions():
    return render_template('terms_and_conditions.html')

@app.context_processor
def inject_current_year():
    return {'current_year': datetime.now().year, 'current_date': datetime.now().strftime('%B %d, %Y')}

@app.route('/export_readings')
@login_required
def export_readings():
    user_id = session['user_id']
    readings = BloodPressureReading.query.filter_by(user_id=user_id).order_by(BloodPressureReading.timestamp.desc()).all()
    
    # Create a StringIO object to write CSV data
    si = StringIO()
    cw = csv.writer(si)
    
    # Write header
    cw.writerow(['Date', 'Time', 'Systolic', 'Diastolic', 'Pulse'])
    
    # Write data
    for reading in readings:
        cw.writerow([
            reading.timestamp.strftime('%Y-%m-%d'),
            reading.timestamp.strftime('%H:%M:%S'),
            reading.systolic,
            reading.diastolic,
            reading.pulse
        ])
    
    # Create response
    output = si.getvalue().encode('utf-8')
    si.close()
    
    # Create a BytesIO object
    mem = BytesIO()
    mem.write(output)
    mem.seek(0)
    # i want to format the date to be like this: Jun 1 2024 12:00 AM
    # now = datetime.datetime.now()
    # current_date_time = now.strftime("%Y%m%d%H%M")
    current_date_time = datetime.now().strftime('%b %d %Y %I:%M %p')
    # current_date_time = ('%b %d %Y %I:%M %p')
    
    download_file_name = f"Blood_Pressure_Readings_{current_date_time}.csv"

    return send_file(
            mem,
            mimetype='text/csv',
            as_attachment=True,
            download_name=download_file_name
    )
    
    
def generate_random_readings():
    user_id = session['user_id']
    current_date = datetime.now().date()
    readings = []
    
    # Initial values
    last_systolic = random.randint(100, 122)
    last_diastolic = random.randint(70, 80)
    last_pulse = random.randint(60, 80)
    
    # Trend factors (slight upward or downward trend)
    systolic_trend = random.uniform(-0.1, 0.1)
    diastolic_trend = random.uniform(-0.05, 0.05)
    pulse_trend = random.uniform(-0.05, 0.05)

    for day in range(45):
        reading_date = current_date - timedelta(days=day)
        
        # Randomly choose morning or evening
        if random.choice([True, False]):
            # Morning reading (5:20 AM to 6:40 AM)
            hour = random.randint(5, 6)
            minute = random.randint(20, 59) if hour == 5 else random.randint(0, 40)
        else:
            # Evening reading (6:00 PM to 8:55 PM)
            hour = random.randint(18, 20)
            minute = random.randint(0, 55)
        
        reading_time = datetime.combine(reading_date, datetime.min.time().replace(hour=hour, minute=minute))
        
        # Generate new readings with small variations from the last reading
        systolic = max(90, min(150, int(last_systolic + random.gauss(0, 3) + systolic_trend)))
        diastolic = max(60, min(100, int(last_diastolic + random.gauss(0, 2) + diastolic_trend)))
        pulse = max(50, min(100, int(last_pulse + random.gauss(0, 2) + pulse_trend)))
        
        # Ensure diastolic is always lower than systolic
        diastolic = min(diastolic, systolic - 30)
        
        # Occasional spikes (about 5% chance)
        if random.random() < 0.05:
            systolic += random.randint(5, 15)
            diastolic += random.randint(3, 10)
            pulse += random.randint(5, 15)
        
        reading = BloodPressureReading(
            user_id=user_id,
            systolic=systolic,
            diastolic=diastolic,
            pulse=pulse,
            timestamp=reading_time,
            reading_type_id=1,  # Assuming 1 is for manual entry
            analysis_status_id=1,  # Default value
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        readings.append(reading)
        
        # Update last values for the next iteration
        last_systolic = systolic
        last_diastolic = diastolic
        last_pulse = pulse
    
    return readings

@app.route('/generate_random_readings')
@login_required
def generate_random_readings_route():
    try:
        readings = generate_random_readings()
        db.session.bulk_save_objects(readings)
        db.session.commit()
        flash('Sample data generated and saved successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error generating and saving sample data: {str(e)}', 'danger')
    
    return redirect(url_for('dashboard'))

@app.route('/clear_readings', methods=['POST','GET'])
@login_required
def clear_readings():
    user_id = session['user_id']
    try:
        # Delete all readings for the user
        BloodPressureReading.query.filter_by(user_id=user_id).delete()
        db.session.commit()
        #clear the analysis as well
        BloodPressureAnalysis.query.filter_by(user_id=user_id).delete()
        db.session.commit()
        flash('All your readings have been cleared successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'An error occurred while clearing your readings: {str(e)}', 'danger')
    return redirect(url_for('dashboard'))

@app.route('/analyze_readings')
@login_required
def analyze_readings():
    user = User.query.get(session['user_id'])
    if not user.profile_completed:
        flash('Please complete your profile before doing this.', 'info')
        return redirect(url_for('complete_profile'))

    readings = BloodPressureReading.query.filter_by(user_id=user.id).order_by(BloodPressureReading.timestamp.desc()).all()
    
    if not readings:
        flash('You need to have at least one reading to perform analysis.', 'warning')
        return redirect(url_for('dashboard'))

    # Get the current count of readings
    current_readings_count = len(readings)

    # Check if there's a recent analysis
    recent_analysis = BloodPressureAnalysis.query.filter_by(user_id=user.id).order_by(BloodPressureAnalysis.created_at.desc()).first()
    if recent_analysis and recent_analysis.readings_count == current_readings_count:
        return render_template('analysis_results.html', analysis=json.loads(recent_analysis.analysis_text))

    # Prepare user profile and readings data
    user_profile = f"""
    
## User Profile
Name: {user.name}
Gender {user.gender}
Age {datetime.now().year - user.year_of_birth}
Height {user.height} cm
Weight {user.weight} kg
Occupation {user.occupation}
Activity Level {user.activity_level}
    """

    readings_data = "## Blood Pressure Readings:\n"
    for reading in readings:
        readings_data += f"\nDate: {reading.timestamp}, Systolic: {reading.systolic}, Diastolic: {reading.diastolic}, Pulse: {reading.pulse}\n"
    readings_data += "\n"

    # Prepare the prompt for Gemini
    prompt = f"""
    ## Instructions for Analysis
    Analyze the following blood pressure readings and user profile. Provide a comprehensive analysis including:
    1. High level summary for a non-medical person, easy to understand in one sentence, followed by another sentence with a recommendation on what to do next, if any - json key is summary
    2. Overall blood pressure trends - json key is overall_blood_pressure_trends
    3. Overall pulse trends, including average pulse, minimum pulse, maximum pulse, pulse variability (standard deviation), and trend - json key is overall_pulse_trends
    4. Identification of any concerning patterns or readings - json key is concerning_patterns
    5. Recommendations for lifestyle changes or improvements - json key is lifestyle_changes
    6. Suggestions for follow-up actions (e.g., consult a doctor, increase monitoring frequency) - json key is follow_up_actions
    7. Any other relevant observations or insights - json key is other_insights

    {user_profile}

    {readings_data}

    Please provide your analysis in a json object and in the json object please include the json keys as the headers and the values as properly formatted  HTML format, using appropriate tags, paragraphs, and lists. Use <strong> tags to highlight important points. No headers for the sections.
    
    """

    try:
        # Generate content using Gemini
        response = model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                response_mime_type="application/json"
            ),
                                          )
        
        json_response = response.text;
        
        # Attempt to parse the response as JSON

        try:
            analysis_json = json.loads(json_response)
        except json.JSONDecodeError:
            flash('The analysis response is not in the expected format. Please try again later', 'danger')
            return redirect(url_for('dashboard'))
        
        # Store the analysis in the database
        new_analysis = BloodPressureAnalysis(user_id=user.id, analysis_text=json.dumps(analysis_json), readings_count=current_readings_count)
        db.session.add(new_analysis)
        db.session.commit()

        return render_template('analysis_results.html', analysis=analysis_json)
    except Exception as e:
        flash(f'An error occurred during analysis: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))

# Add this custom filter definition before the route definitions
@app.template_filter('nl2br')
def nl2br_filter(s):
    return s;
    return escape(s).replace('\n', '<br>\n')

# Initialize database
if __name__ == "__main__":
    # Before running the app, ensure the database file exists
    if not os.path.exists('bp_tracker.db'):
        with app.app_context():
            db.create_all()
        app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))






