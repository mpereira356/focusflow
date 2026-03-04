from flask import render_template, redirect, url_for, request, Blueprint
from flask_login import login_user, logout_user, login_required, current_user
from app import db, bcrypt
from app.models import User

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        error = None
        if not username or len(username) < 3:
            error = 'Nome de usuario deve ter ao menos 3 caracteres.'
        elif not email or '@' not in email:
            error = 'E-mail invalido.'
        elif len(password) < 6:
            error = 'Senha deve ter ao menos 6 caracteres.'
        elif password != confirm:
            error = 'Senhas nao conferem.'
        elif User.query.filter_by(email=email).first():
            error = 'Este e-mail ja esta cadastrado.'
        elif User.query.filter_by(username=username).first():
            error = 'Este nome de usuario ja esta em uso.'

        if error:
            return render_template(
                'auth/register.html',
                error=error,
                username=username,
                email=email,
            )

        pw_hash = bcrypt.generate_password_hash(password).decode('utf-8')
        user = User(username=username, email=email, password_hash=pw_hash)
        db.session.add(user)
        db.session.commit()

        login_user(user, remember=True)
        return redirect(url_for('main.dashboard'))

    return render_template('auth/register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember') == 'on'

        user = User.query.filter_by(username=username).first()

        if not user or not bcrypt.check_password_hash(user.password_hash, password):
            return render_template(
                'auth/login.html',
                error='Usuario ou senha invalidos.',
                username=username,
            )

        login_user(user, remember=remember)
        next_page = request.args.get('next')
        return redirect(next_page or url_for('main.dashboard'))

    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))
