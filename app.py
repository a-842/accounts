from flask import Flask, render_template, redirect, url_for, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import markdown

# Initialize the Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Models (imported from models.py)
from models import User, Note, Todo, Person

# User Loader
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('notes'))
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/notes')
@login_required
def notes():
    notes = Note.query.filter_by(user_id=current_user.id).all()
    return render_template('notes.html', notes=notes)

@app.route('/todo')
@login_required
def todo():
    todos = Todo.query.filter_by(user_id=current_user.id, parent_id=None).all()
    return render_template('todo.html', todos=todos)

@app.route('/people')
@login_required
def people():
    people = Person.query.filter_by(user_id=current_user.id).all()
    return render_template('people.html', people=people)

@app.route('/add_note', methods=['POST'])
@login_required
def add_note():
    title = request.form.get('title')
    content = request.form.get('content')
    folder = request.form.get('folder')
    note = Note(title=title, content=content, folder=folder, user_id=current_user.id)
    db.session.add(note)
    db.session.commit()
    return redirect(url_for('notes'))

@app.route('/add_todo', methods=['POST'])
@login_required
def add_todo():
    task = request.form.get('task')
    todo = Todo(task=task, user_id=current_user.id)
    db.session.add(todo)
    db.session.commit()
    return redirect(url_for('todo'))

@app.route('/add_person', methods=['POST'])
@login_required
def add_person():
    name = request.form.get('name')
    dob = request.form.get('dob')
    relationship = request.form.get('relationship')
    person = Person(name=name, dob=dob, relationship=relationship, user_id=current_user.id)
    db.session.add(person)
    db.session.commit()
    return redirect(url_for('people'))

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port="5003")
