# On-Road Vehicle Breakdown Assistance

A futuristic, full-stack web application designed to connect stranded motorists with nearby mechanics in real-time.

## Tech Stack
- **Frontend**: HTML5, CSS3 (Vanilla), JavaScript (ES6+)
- **Backend**: Flask (Python)
- **Database**: SQLite with SQLAlchemy ORM
- **Real-time**: Flask-SocketIO (WebSockets)
- **Maps**: Leaflet.js + OpenStreetMap
- **Authentication**: Flask-Login

## Key Features
- **Real-time Location Tracking**: Live updates of user and mechanic locations on an interactive map.
- **Breakdown Requests**: Users can request help for various issues (Tyre puncture, Engine, Fuel, etc.).
- **Smart Assignment**: Mechanics can only accept one task at a time.
- **Live Chat**: Real-time communication between users and mechanics with database persistence.
- **Modern UI**: Dark glassmorphism design with smooth animations and responsive layout.

## Setup Instructions
1. Navigate to the `backend` folder.
2. Install dependencies: `pip install -r requirements.txt`.
3. Run the application: `python app.py`.
4. Open your browser at `http://127.0.0.1:5000`.

## Folder Structure
```
on-road-assistance/
│
├── backend/
│   ├── app.py
│   ├── database.db
│   ├── requirements.txt
│
├── frontend/
│   ├── templates/
│   ├── static/
│   │   ├── css/
│   │   ├── js/
│   │   └── images/
│
└── README.md
```
