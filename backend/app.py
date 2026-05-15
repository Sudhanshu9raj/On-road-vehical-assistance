import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__, 
            template_folder='../frontend/templates', 
            static_folder='../frontend/static')
app.config['SECRET_KEY'] = 'road-assistance-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*")
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False) # 'user' or 'mechanic'
    lat = db.Column(db.Float, nullable=True)
    lng = db.Column(db.Float, nullable=True)

class AssistanceRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    mechanic_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    issue_type = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default='pending') # pending, accepted, on_way, reached, completed, rejected
    user_lat = db.Column(db.Float, nullable=False)
    user_lng = db.Column(db.Float, nullable=False)
    mechanic_lat = db.Column(db.Float, nullable=True)
    mechanic_lng = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', foreign_keys=[user_id], backref='requests')
    mechanic = db.relationship('User', foreign_keys=[mechanic_id], backref='tasks')

class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey('assistance_request.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.is_json:
            data = request.get_json()
            username = data.get('username')
            password = data.get('password')
        else:
            username = request.form.get('username')
            password = request.form.get('password')
            
        print(f"[DEBUG] Login attempt - Username: {username}")
        user = User.query.filter_by(username=username).first()
        
        if user:
            print(f"[DEBUG] User found in database")
            is_valid = check_password_hash(user.password, password)
            print(f"[DEBUG] Password valid: {is_valid}")
            
            if is_valid:
                login_user(user)
                if request.is_json:
                    return jsonify({'status': 'success', 'redirect': url_for('dashboard')})
                return redirect(url_for('dashboard'))
        else:
            print(f"[DEBUG] User NOT found")

        if request.is_json:
            return jsonify({'status': 'error', 'message': 'Invalid username or password'}), 401
        flash('Invalid username or password', 'error')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'error')
            return redirect(url_for('register'))
        
        hashed_pw = generate_password_hash(password)
        new_user = User(username=username, password=hashed_pw, role=role)
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful!', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'user':
        return render_template('user_dashboard.html')
    else:
        return render_template('mechanic_dashboard.html')

# API Endpoints
@app.route('/api/requests', methods=['POST'])
@login_required
def create_request():
    data = request.get_json()
    new_req = AssistanceRequest(
        user_id=current_user.id,
        issue_type=data['issue_type'],
        user_lat=data['lat'],
        user_lng=data['lng'],
        status='pending'
    )
    db.session.add(new_req)
    db.session.commit()
    
    # Notify nearby mechanics via socket
    socketio.emit('new_request', {
        'id': new_req.id,
        'user_id': current_user.id,
        'username': current_user.username,
        'issue_type': new_req.issue_type,
        'lat': new_req.user_lat,
        'lng': new_req.user_lng
    }, namespace='/')
    
    return jsonify({'status': 'success', 'request_id': new_req.id})

@app.route('/api/requests/history')
@login_required
def get_history():
    if current_user.role == 'user':
        reqs = AssistanceRequest.query.filter_by(user_id=current_user.id).order_by(AssistanceRequest.created_at.desc()).all()
    else:
        reqs = AssistanceRequest.query.filter_by(mechanic_id=current_user.id).order_by(AssistanceRequest.created_at.desc()).all()
    
    return jsonify([{
        'id': r.id,
        'issue_type': r.issue_type,
        'status': r.status,
        'created_at': r.created_at.strftime('%Y-%m-%d %H:%M'),
        'mechanic': r.mechanic.username if r.mechanic else 'Pending',
        'user': r.user.username
    } for r in reqs])

@app.route('/api/chat/<int:request_id>')
@login_required
def get_chat(request_id):
    messages = ChatMessage.query.filter_by(request_id=request_id).order_by(ChatMessage.timestamp.asc()).all()
    return jsonify([{
        'sender_id': m.sender_id,
        'sender_name': User.query.get(m.sender_id).username,
        'message': m.message,
        'timestamp': m.timestamp.strftime('%H:%M')
    } for m in messages])

@app.route('/api/requests/<int:request_id>/delete', methods=['POST'])
@login_required
def delete_request(request_id):
    req = AssistanceRequest.query.get(request_id)
    if req and req.user_id == current_user.id and req.status == 'pending':
        db.session.delete(req)
        db.session.commit()
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error', 'message': 'Cannot delete request'}), 400

# SocketIO Events
@socketio.on('join')
def on_join(data):
    room = data['room']
    join_room(room)
    print(f"User {current_user.username} joined room {room}")

@socketio.on('update_location')
def handle_location(data):
    current_user.lat = data['lat']
    current_user.lng = data['lng']
    db.session.commit()
    
    # Broadcast to relevant rooms
    # If user has active request, notify mechanic
    # If mechanic has active request, notify user
    active_req = AssistanceRequest.query.filter(
        ((AssistanceRequest.user_id == current_user.id) | (AssistanceRequest.mechanic_id == current_user.id)),
        AssistanceRequest.status.in_(['accepted', 'on_way', 'reached'])
    ).first()
    
    if active_req:
        room = f"request_{active_req.id}"
        emit('location_update', {
            'user_id': current_user.id,
            'role': current_user.role,
            'lat': data['lat'],
            'lng': data['lng']
        }, room=room)

@socketio.on('accept_request')
def handle_accept(data):
    request_id = data['request_id']
    req = AssistanceRequest.query.get(request_id)
    
    # Check if mechanic already has an active task
    active_task = AssistanceRequest.query.filter_by(mechanic_id=current_user.id).filter(
        AssistanceRequest.status.in_(['accepted', 'on_way', 'reached'])
    ).first()
    
    if active_task:
        emit('error', {'message': 'You already have an active task'})
        return

    if req and req.status == 'pending':
        req.mechanic_id = current_user.id
        req.status = 'accepted'
        req.mechanic_lat = current_user.lat
        req.mechanic_lng = current_user.lng
        db.session.commit()
        
        room = f"request_{req.id}"
        join_room(room)
        
        # Notify user
        emit('request_accepted', {
            'request_id': req.id,
            'mechanic_id': current_user.id,
            'mechanic_name': current_user.username,
            'mechanic_lat': current_user.lat,
            'mechanic_lng': current_user.lng
        }, room=f"user_{req.user_id}")
        
        # Broadcast to all mechanics that this request is no longer available
        emit('request_taken', {'request_id': req.id}, broadcast=True)

@socketio.on('update_status')
def handle_status(data):
    request_id = data['request_id']
    new_status = data['status']
    req = AssistanceRequest.query.get(request_id)
    
    if req and req.mechanic_id == current_user.id:
        req.status = new_status
        db.session.commit()
        
        room = f"request_{req.id}"
        emit('status_updated', {
            'request_id': req.id,
            'status': new_status
        }, room=room)

@socketio.on('send_message')
def handle_message(data):
    request_id = data['request_id']
    message_text = data['message']
    
    new_msg = ChatMessage(
        request_id=request_id,
        sender_id=current_user.id,
        message=message_text
    )
    db.session.add(new_msg)
    db.session.commit()
    
    room = f"request_{request_id}"
    emit('receive_message', {
        'sender_id': current_user.id,
        'sender_name': current_user.username,
        'message': message_text,
        'timestamp': new_msg.timestamp.strftime('%H:%M')
    }, room=room)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()

    port = int(os.environ.get("PORT", 5000))

    socketio.run(
        app,
        host="0.0.0.0",
        port=port
    )
