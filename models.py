from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import Column, Integer

db = SQLAlchemy()

class BloodPressureReading(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    systolic = db.Column(db.Integer, nullable=False)
    diastolic = db.Column(db.Integer, nullable=False)
    pulse = db.Column(db.Integer, nullable=True)
    timestamp = db.Column(db.DateTime, nullable=False)
    image_filename = db.Column(db.String(120), nullable=True)
    reading_type_id = db.Column(db.Integer, nullable=False, default=1)  # 1 for manual, 2 for image
    analysis_status_id = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=True, onupdate=datetime.utcnow)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    gender = db.Column(db.String(10))
    year_of_birth = db.Column(db.Integer)  # Changed from age to year_of_birth
    height = db.Column(db.Float)
    weight = db.Column(db.Float)
    occupation = db.Column(db.String(120))
    activity_level = db.Column(db.String(20))
    profile_completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=True, onupdate=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)

    def is_profile_complete(self):
        return all([self.gender, self.year_of_birth, self.height, self.weight, self.profile_completed])

    def update_last_login(self):
        self.last_login = datetime.utcnow()
        db.session.commit()

    def get_age(self):
        if self.year_of_birth:
            return datetime.now().year - self.year_of_birth
        return None

def __repr__(self):
        return f'<BloodPressureReading {self.systolic}/{self.diastolic}>'

class BloodPressureAnalysis(db.Model):
    __tablename__ = 'blood_pressure_analysis'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, db.ForeignKey('user.id'), nullable=False)
    analysis_text = Column(db.Text, nullable=False)
    created_at = Column(db.DateTime, default=datetime.utcnow, nullable=False)
    readings_count = Column(Integer, nullable=False, default=0)  # New column to store the count of readings

    user = db.relationship('User', backref=db.backref('analyses', lazy=True))

    def __repr__(self):
        return f'<BloodPressureAnalysis {self.id} for user {self.user_id}>'
