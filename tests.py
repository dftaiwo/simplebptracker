## python -m unittest tests.py
import unittest
from app import app, db
from models import User, BloodPressureReading
from datetime import datetime, timedelta

class BloodPressureTrackerTests(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app = app.test_client()
        with app.app_context():
            db.create_all()

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def test_index_page(self):
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Welcome to Simple BP Tracker', response.data)

    def test_signup(self):
        response = self.app.post('/signup', data=dict(
            email='test@example.com',
            name='Test User'
        ), follow_redirects=True)
        self.assertIn(b'Registration successful', response.data)

    def test_signin(self):
        # First, create a user
        user = User(email='test@example.com', name='Test User')
        with app.app_context():
            db.session.add(user)
            db.session.commit()

        # Now try to sign in
        response = self.app.post('/signin', data=dict(
            email='test@example.com'
        ), follow_redirects=True)
        self.assertIn(b'Please use the following link to sign in', response.data)

    def test_new_reading(self):
        # First, create and log in a user
        with app.app_context():
            user = User(email='test@example.com', name='Test User')
            db.session.add(user)
            db.session.commit()
            with self.app.session_transaction() as sess:
                sess['user_id'] = user.id

        # Now try to add a new reading
        response = self.app.post('/new_reading', data=dict(
            entry_method='manual',
            reading_datetime=datetime.now().strftime('%Y-%m-%dT%H:%M'),
            systolic=120,
            diastolic=80,
            pulse=70
        ), follow_redirects=True)
        self.assertIn(b'New reading added successfully', response.data)

    def test_my_readings(self):
        # First, create and log in a user, and add a reading
        with app.app_context():
            user = User(email='test@example.com', name='Test User')
            db.session.add(user)
            db.session.commit()
            reading = BloodPressureReading(
                user_id=user.id,
                systolic=120,
                diastolic=80,
                pulse=70,
                timestamp=datetime.now(),
                reading_type_id=1
            )
            db.session.add(reading)
            db.session.commit()
            with self.app.session_transaction() as sess:
                sess['user_id'] = user.id

        # Now check the my_readings page
        response = self.app.get('/my_readings')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'120', response.data)
        self.assertIn(b'80', response.data)

if __name__ == '__main__':
    unittest.main()