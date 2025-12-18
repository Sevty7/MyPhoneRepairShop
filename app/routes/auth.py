from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app import db
from app.models import User, Client, Role
from functools import wraps
from app.decorators import login_required

auth_bp = Blueprint('auth_bp', __name__)


@auth_bp.route('/register', methods=['GET', 'POST'], endpoint='register')
def register():
    if session.get('user_id'):
        return redirect(url_for('main_bp.index'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        last_name = request.form.get('last_name', '').strip()
        first_name = request.form.get('first_name', '').strip()

        if not all([email, password, last_name, first_name]):
            flash('Заполните обязательные поля.', 'danger')
            return render_template('auth/register.html')
        if User.query.filter_by(email=email).first():
            flash('Пользователь с таким Email уже зарегистрирован.', 'danger')
            return render_template('auth/register.html')

        try:
            client = Client(last_name=last_name, first_name=first_name,
                            middle_name=request.form.get('middle_name', '').strip(),
                            phone=request.form.get('phone', '').strip())
            db.session.add(client)
            db.session.flush()
            
            client_role = Role.query.filter_by(role_name='client').first()
            user = User(email=email, role_id=client_role.role_id, client_id=client.client_id)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash('Регистрация успешна! Войдите в систему.', 'success')
            return redirect(url_for('auth_bp.login'))
        except Exception:
            db.session.rollback()
            flash('Ошибка при регистрации.', 'danger')

    return render_template('auth/register.html')


@auth_bp.route('/login', methods=['GET', 'POST'], endpoint='login')
def login():
    if session.get('user_id'):
        return redirect(url_for('main_bp.index'))
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            session['user_id'] = user.user_account_id 
            session['role'] = user.role
            session['client_id'] = user.client_id
            session['email'] = user.email

            flash(f'Добро пожаловать, {user.display_name}!', 'success')
            if user.role == 'admin':
                return redirect(url_for('admin_bp.admin_index'))
            return redirect(url_for('main_bp.index'))

        flash('Неверный Email или Пароль.', 'danger')

    return render_template('auth/login.html')


@auth_bp.route('/logout', endpoint='logout')
@login_required
def logout():
    session.clear()
    flash('Вы вышли из системы.', 'info')
    return redirect(url_for('main_bp.index'))
