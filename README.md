# Blood Pressure Tracker

## Overview

Blood Pressure Tracker is an experiemental web application that allows users to monitor and track their blood pressure readings over time. It provides a user-friendly interface for logging readings, viewing trends, and gaining insights into cardiovascular health. It's not intended for clinical use, but rather as a personal project to explore and begin to showcase Gemini's capabilities.

## Demo Application

You can access a live demo of the application at https://mybp.d4devs.com/

## Features

- User authentication system
- Dashboard with recent readings and statistics
- Ability to add new blood pressure readings 
- Ability to upload an image of your BP reading 
- View all historical readings and export to CSV
- Graphical representation of blood pressure trends
- 30-day average calculations

## Technologies Used

- Python (3.9+)
- Flask (Web Framework)
- SQLAlchemy (ORM)
- HTML/CSS
- Bootstrap 5
- Chart.js (for data visualization)
- jQuery

## Setup Instructions

1. Clone the repository:
   ```
   git clone https://github.com/dftaiwo/blood-pressure-tracker.git
   cd blood-pressure-tracker
   ```

2. Set up a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   Create a `.env` file in the root directory and add the following:
   ```
   # Database URL. Change this to your database URL. It can be mysql, postgres, etc. This currently uses sqlite 
   DATABASE_URL=sqlite:///blood_pressure.db
   APP_NAME=Simple BP Tracker
   
   # For sending emails with the magic link to log in. Not required for running a demo locally
   MAIL_SERVER=
   MAIL_PORT=465
   MAIL_USERNAME=
   MAIL_EMAIL=
   MAIL_PASSWORD=

    # Secret key for the app. Set this to a different random string. You can visit https://randomkeygen.com/ to generate a random secret key.
    SECRET_KEY=TKYleJNGWn1mfSo9yCc3

    # Google API Key for Gemini . Visit https://makersuite.google.com/app/apikey to get one
    GEMINI_API_KEY=

   ```

5. Initialize the database:
   ```
   flask db init
   flask db migrate
   flask db upgrade
   ```

6. Run the application:
   ```
   flask run
   ```

7. Open a web browser and navigate to `http://localhost:5000`


## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License.

