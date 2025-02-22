from itsdangerous import URLSafeTimedSerializer
from flask import Flask, render_template, redirect, url_for, request, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_wtf.csrf import CSRFProtect
import random, os, datetime
from dotenv import load_dotenv

DOMAIN = "https://dashboard.acoult.art"

app = Flask(__name__)
load_dotenv()

# Configurations
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('SQLALCHEMY_DATABASE_URI')
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT'))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS') == 'True'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['WTF_CSRF_SECRET_KEY'] = os.getenv('CSRF_SECRET_KEY')

# Initialize extensions
db = SQLAlchemy(app)
mail = Mail(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
s = URLSafeTimedSerializer(app.config['SECRET_KEY'])
csrf = CSRFProtect(app)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    verified = db.Column(db.Boolean, default=False)
    verification_code_hash = db.Column(db.String(256), nullable=True)
    verification_code_expiry = db.Column(db.DateTime, nullable=True)
    reset_token = db.Column(db.String(256), nullable=True)
    reset_token_expiry = db.Column(db.DateTime, nullable=True)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def home():
    return redirect(url_for('dashboard')) if current_user.is_authenticated else render_template('home.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        name = request.form['name']
        password = generate_password_hash(request.form['password'], method='pbkdf2:sha256')

        if User.query.filter_by(email=email).first():
            flash('Email already exists', 'danger')
            return redirect(url_for('register'))

        verification_code = str(random.randint(100000, 999999))
        hashed_code = generate_password_hash(verification_code, method='pbkdf2:sha256')
        expiry_time = datetime.datetime.utcnow() + datetime.timedelta(minutes=10)

        user = User(email=email, name=name, password=password, verification_code_hash=hashed_code, verification_code_expiry=expiry_time)
        db.session.add(user)
        db.session.commit()

        msg = Message('Verify Your Account', sender=app.config['MAIL_USERNAME'], recipients=[email])
        msg.body = f'Your verification code is {verification_code}. It expires in 10 minutes.'
        mail.send(msg)

        session['email'] = email
        return redirect(url_for('verify'))
    return render_template('register.html')

@app.route('/verify', methods=['GET', 'POST'])
def verify():
    if 'email' not in session:
        return redirect(url_for('register'))

    user = User.query.filter_by(email=session['email']).first()
    if not user or not user.verification_code_hash:
        return redirect(url_for('register'))

    if datetime.datetime.utcnow() > user.verification_code_expiry:
        flash('Verification code expired. Please register again.', 'danger')
        db.session.delete(user)
        db.session.commit()
        return redirect(url_for('register'))

    if request.method == 'POST':
        if check_password_hash(user.verification_code_hash, request.form['code']):
            user.verified = True
            user.verification_code_hash = None
            user.verification_code_expiry = None
            db.session.commit()
            flash('Account verified!', 'success')
            return redirect(url_for('login'))
        flash('Invalid code', 'danger')
    return render_template('verify.html')

@app.route('/forgot', methods=['POST'])
def forgot_password():
    email = request.form['email']
    user = User.query.filter_by(email=email, verified=True).first()
    if user:
        token = generate_password_hash(email + str(datetime.datetime.utcnow()), method='pbkdf2:sha256')
        user.reset_token = token
        user.reset_token_expiry = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
        db.session.commit()
        reset_link = f"{DOMAIN}{url_for('reset_password', token=token)}"
        msg = Message('Password Reset', sender=app.config['MAIL_USERNAME'], recipients=[email])
        msg.body = f'Click here to reset your password: {reset_link}'
        mail.send(msg)
        flash('A password reset link has been sent.', 'info')
    return redirect(url_for('forgot_password'))

@app.route('/reset/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user = User.query.filter_by(reset_token=token).first()
    if not user or user.reset_token_expiry < datetime.datetime.utcnow():
        flash('Invalid or expired token.', 'danger')
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        user.password = generate_password_hash(request.form['password'], method='pbkdf2:sha256')
        user.reset_token = None
        user.reset_token_expiry = None
        db.session.commit()
        flash('Password reset successful!', 'success')
        return redirect(url_for('login'))
    return render_template('reset.html')

@app.route('/delete_account', methods=['POST'])
@login_required
@csrf.exempt
def delete_account():
    if not check_password_hash(current_user.password, request.form['password']):
        flash('Incorrect password.', 'danger')
        return redirect(url_for('dashboard'))
    db.session.delete(current_user)
    db.session.commit()
    logout_user()
    flash('Account deleted.', 'success')
    return redirect(url_for('home'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    from waitress import serve
    serve(app, port=5003, host="0.0.0.0")
