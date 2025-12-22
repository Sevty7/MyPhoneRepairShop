from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app import db
from app.models import User, Client, WorkOrder, Part
from functools import wraps
from datetime import datetime
from decimal import Decimal
from app.decorators import login_required

main_bp = Blueprint('main_bp', __name__)

@main_bp.route('/', endpoint='index')
def index():
    
    if session.get('role') == 'admin':
        return redirect(url_for('admin_bp.admin_index'))
    
    if session.get('client_id'):
        client = Client.query.get(session['client_id'])
        orders = client.orders.order_by(WorkOrder.received_date.desc()).all()
        return render_template('client_index.html', client=client, orders=orders)
    return render_template('public_index.html')


@main_bp.route('/profile', methods=['GET', 'POST'], endpoint='profile')
@login_required
def profile():
    user = User.query.get(session['user_id'])

    if request.method == 'POST' and request.form.get('update_profile') and user.client_id:
        try:
            client = Client.query.get(user.client_id)
            client.last_name = request.form.get('last_name', '').strip()
            client.first_name = request.form.get('first_name', '').strip()
            client.middle_name = request.form.get('middle_name', '').strip()
            client.phone = request.form.get('phone', '').strip()
            db.session.commit()
            flash('Профиль обновлен.', 'success')
        except Exception:
            db.session.rollback()
            flash('Ошибка при сохранении профиля.', 'danger')
        return redirect(url_for('main_bp.profile'))

    if request.method == 'POST' and request.form.get('change_password'):
        old_password = request.form.get('old_password')
        new_password = request.form.get('new_password')

        if not user.check_password(old_password):
            flash('Неверный текущий пароль.', 'danger')
        else:
            user.set_password(new_password)
            db.session.commit()
            flash('Пароль успешно изменен.', 'success')
        return redirect(url_for('main_bp.profile'))

    client = Client.query.get(user.client_id) if user.client_id else None
    return render_template('profile.html', user=user, client=client)


@main_bp.route('/order/<int:id>', endpoint='order_details')
@login_required
def order_details(id):
    order = WorkOrder.query.get_or_404(id)
    if session.get('role') != 'admin' and order.client_id != session.get('client_id'):
        flash('Доступ к этому заказу запрещен.', 'danger')
        return redirect(url_for('main_bp.index'))
    return render_template('order_details.html', order=order)


@main_bp.route('/order', methods=['GET', 'POST'], endpoint='add_order')
@login_required
def add_order():
    if request.method == 'POST':
        phone_model = request.form.get('phone_model', '').strip()
        problem_description = request.form.get('problem_description', '').strip()
        if session.get('role') == 'client':
            client_id = session['client_id']
            work_cost = Decimal(request.form.get('work_cost', '0.00')) if request.form.get('work_cost') else Decimal('0.00')
            received_date = datetime.today().date()
            status = 'Принят'
        else:
            client_id = int(request.form.get('client_id', 0))
            work_cost = Decimal(request.form.get('work_cost', '0.00'))
            received_date = datetime.strptime(request.form.get('received_date'), '%Y-%m-%d').date()
            status = request.form.get('status', 'Принят')

        if not phone_model:
            flash('Модель телефона обязательна.', 'danger')
            clients = Client.query.order_by(Client.last_name).all() if session.get('role') == 'admin' else []
            available_parts = Part.query.filter(Part.work_order_id.is_(None)).all() if session.get('role') == 'admin' else []
            today = datetime.today().strftime('%Y-%m-%d')
            return render_template(
                'forms/order_form.html',
                order=None,
                clients=clients,
                available_parts=available_parts,
                statuses=['Принят', 'В ремонте', 'Ожидает запчасти', 'Готов к выдаче', 'Выдан', 'Отменен'],
                title="Новый заказ",
                submit_text="Сохранить",
                today=today
            )

        order = WorkOrder(phone_model=phone_model, problem_description=problem_description,
                          received_date=received_date, status=status, work_cost=work_cost,
                          client_id=client_id)
        try:
            db.session.add(order)
            db.session.commit()
            flash('Заказ создан.', 'success')
            if session.get('role') == 'client':
                return redirect(url_for('main_bp.order_details', id=order.work_order_id))
            return redirect(url_for('admin_bp.admin_orders'))
        except Exception:
            db.session.rollback()
            flash('Ошибка создания заказа.', 'danger')

    clients = Client.query.order_by(Client.last_name).all() if session.get('role') == 'admin' else []
    available_parts = Part.query.filter(Part.work_order_id.is_(None)).all() if session.get('role') == 'admin' else []
    today = datetime.today().strftime('%Y-%m-%d')
    return render_template(
        'forms/order_form.html',
        order=None,
        clients=clients,
        available_parts=available_parts,
        statuses=['Принят', 'В ремонте', 'Ожидает запчасти', 'Готов к выдаче', 'Выдан', 'Отменен'],
        title="Новый заказ",
        submit_text="Сохранить",
        today=today
    )


@main_bp.route('/order/<int:id>/cancel', methods=['POST'], endpoint='cancel_order')
@login_required
def cancel_order(id):
    order = WorkOrder.query.get_or_404(id)
    if order.client_id != session.get('client_id'):
        flash('Вы не являетесь владельцем этого заказа.', 'danger')
    elif order.status != 'Принят':
        flash('Отменить можно только заказ со статусом "Принят".', 'danger')
    else:
        try:
            order.status = 'Отменен'
            db.session.commit()
            flash(f'Заказ №{order.work_order_id} отменен.', 'info')
        except Exception:
            db.session.rollback()
            flash('Ошибка отмены заказа.', 'danger')
    return redirect(url_for('main_bp.order_details', id=order.work_order_id))
