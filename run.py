from dotenv import load_dotenv
from app import create_app, db

load_dotenv()
app = create_app('development')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print("Database tables created/verified.")
    app.run(debug=True, host='0.0.0.0', port=1000)
