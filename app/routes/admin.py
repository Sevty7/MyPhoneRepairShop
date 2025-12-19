from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app import db
from app.models import User, Client, Part, Supplier, Supply, WorkOrder, Role
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import func, or_, desc
from app.decorators import admin_required

admin_bp = Blueprint('admin_bp', __name__, template_folder='templates', url_prefix='/admin')


@admin_bp.route('/', endpoint='admin_index')
@admin_required
def admin_index():
    
    work_revenue = db.session.query(func.sum(WorkOrder.work_cost))\
        .filter(WorkOrder.status == 'Выдан').scalar() or Decimal('0.00')
    
    parts_revenue = db.session.query(func.sum(Part.price))\
        .join(WorkOrder)\
        .filter(WorkOrder.status == 'Выдан').scalar() or Decimal('0.00')

    total_revenue = work_revenue + parts_revenue
    
    stats = {
        'total_clients': Client.query.count(),
        'active_orders': WorkOrder.query.filter(WorkOrder.status.in_(['Принят', 'В ремонте', 'Ожидает запчасти'])).count(),
        'completed_orders': WorkOrder.query.filter_by(status='Выдан').count(),
        'revenue': total_revenue,
    }
    recent_orders = WorkOrder.query.order_by(WorkOrder.work_order_id.desc()).limit(5).all()
    popular_parts = db.session.query(Part.name, func.count(Part.part_id)).group_by(Part.name).order_by(desc(func.count(Part.part_id))).limit(5).all()
    return render_template('admin/admin_index.html', **stats, recent_orders=recent_orders, popular_parts=popular_parts)


@admin_bp.route('/clients', methods=['GET'], endpoint='admin_clients')
@admin_required
def admin_clients():
    search_query = request.args.get('q', '').strip()
    date_filter = request.args.get('date', '').strip()
    clients_q = Client.query.order_by(Client.client_id.desc())
    if search_query:
        search = f'%{search_query}%'
        clients_q = clients_q.filter(or_(Client.last_name.ilike(search), Client.first_name.ilike(search)))
    if date_filter:
        try:
            date_obj = datetime.strptime(date_filter, '%Y-%m-%d').date()
            clients_q = clients_q.filter(User.created_at >= date_obj).filter(User.created_at < date_obj + datetime.timedelta(days=1)).outerjoin(User, Client.client_id == User.client_id)
        except ValueError:
            pass
    return render_template('admin/admin_clients.html', clients=clients_q.all(), search_query=search_query, date_filter=date_filter)


@admin_bp.route('/client/manage', methods=['GET', 'POST'], endpoint='add_client')
@admin_bp.route('/client/manage/<int:id>', methods=['GET', 'POST'], endpoint='edit_client')
@admin_required
def manage_client(id=None):
    client = Client.query.get_or_404(id) if id else Client()
    roles = Role.query.all() 
    
    if request.method == 'POST':
        try:
            if not request.form.get('last_name') or not request.form.get('first_name'):
                flash('Имя и Фамилия обязательны.', 'danger')
                return redirect(request.url)
            
            client.last_name = request.form['last_name']
            client.first_name = request.form['first_name']
            client.middle_name = request.form.get('middle_name', '').strip()
            client.phone = request.form.get('phone', '').strip()
            
            # Обработка привязки/создания пользователя по email
            email = request.form.get('email', '').strip()
            if email:
                existing_user = User.query.filter_by(email=email).first()
                
                selected_role_id = int(request.form.get('role_id'))
                
                if client.user:
                    if existing_user and existing_user.user_account_id != client.user.user_account_id:
                        flash('Этот Email уже привязан к другому пользователю.', 'danger')
                        return redirect(request.url)
                    client.user.email = email
                    client.user.role_id = selected_role_id
                else:
                    if existing_user:
                        client.user = existing_user
                        client.user.role_id = selected_role_id
                    else:
                        new_user = User(
                            email=email, 
                            role_id=selected_role_id,
                            client_id=client.client_id if id else None
                        )
                        # Устанавливаем временный пароль
                        new_user.set_password('password123')
                        client.user = new_user
                        db.session.add(new_user)
            
            if not id:
                db.session.add(client)
            db.session.commit()
            flash(f'Клиент "{client.full_name}" сохранен.', 'success')
            return redirect(url_for('admin_bp.admin_clients'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка сохранения клиента: {str(e)}', 'danger')
            return redirect(request.url)

    title = "Новый клиент" if not id else f"Редактировать клиента {client.full_name}"
    submit_text = "Сохранить"
    return render_template('forms/client_form.html', client=client, roles=roles, title=title, submit_text=submit_text)


@admin_bp.route('/client/<int:id>/delete', methods=['POST'], endpoint='delete_client')
@admin_required
def delete_client(id):
    client = Client.query.get_or_404(id)
    try:
        # Проверяем есть ли активные заказы
        active_orders = client.orders.filter(WorkOrder.status != 'Отменен').count()
        if active_orders > 0:
            flash(f'Невозможно удалить клиента. У него есть {active_orders} активный заказ(ов). Сначала завершите или отмените заказы.', 'danger')
            return redirect(url_for('admin_bp.admin_clients'))
        
        # Удаляем связанного пользователя если существует
        if client.user:
            db.session.delete(client.user)
        
        # Удаляем все заказы (отменённые)
        for order in client.orders:
            db.session.delete(order)
        
        # Удаляем клиента
        db.session.delete(client)
        db.session.commit()
        flash(f'Клиент "{client.full_name}" и все связанные данные удалены.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении клиента: {str(e)}', 'danger')
    return redirect(url_for('admin_bp.admin_clients'))


@admin_bp.route('/orders', methods=['GET'], endpoint='admin_orders')
@admin_required
def admin_orders():
    search_query = request.args.get('q', '').strip()
    status_filter = request.args.get('status', '').strip()
    date_filter = request.args.get('date', '').strip()
    
    orders_q = WorkOrder.query.order_by(WorkOrder.received_date.desc())
    
    if search_query:
        search = f'%{search_query}%'
        orders_q = orders_q.filter(or_(
            Client.last_name.ilike(search),
            Client.first_name.ilike(search),
            WorkOrder.phone_model.ilike(search)
        )).join(Client)
    
    if status_filter:
        orders_q = orders_q.filter(WorkOrder.status == status_filter)
    
    if date_filter:
        try:
            date_obj = datetime.strptime(date_filter, '%Y-%m-%d').date()
            orders_q = orders_q.filter(WorkOrder.received_date == date_obj)
        except ValueError:
            pass
    
    statuses = ['Принят', 'В ремонте', 'Ожидает запчасти', 'Готов к выдаче', 'Выдан', 'Отменен']
    return render_template('admin/admin_orders.html', orders=orders_q.all(), search_query=search_query, 
                         status_filter=status_filter, date_filter=date_filter, statuses=statuses)


@admin_bp.route('/order/manage', methods=['GET', 'POST'], endpoint='add_order_admin')
@admin_bp.route('/order/manage/<int:id>', methods=['GET', 'POST'], endpoint='edit_order')
@admin_required
def manage_order(id=None):
    order = WorkOrder.query.get_or_404(id) if id else WorkOrder(received_date=date.today())
    
    if request.method == 'POST':
        try:
            # Проверка обязательных полей
            if not request.form.get('phone_model'):
                flash('Модель телефона обязательна.', 'danger')
                return redirect(request.url)

            # Маппинг данных из формы в объект заказа
            order.client_id = int(request.form['client_id'])
            order.phone_model = request.form['phone_model']
            order.problem_description = request.form.get('problem_description', '')
            order.status = request.form.get('status', 'Принят')
            order.work_cost = Decimal(request.form.get('work_cost', '0.00'))
            order.received_date = datetime.strptime(request.form.get('received_date'), '%Y-%m-%d').date()
            
            # Обработка даты завершения (может быть пустой)
            completion_date_str = request.form.get('completion_date')
            order.completion_date = datetime.strptime(completion_date_str, '%Y-%m-%d').date() if completion_date_str else None

            # Добавление нового объекта в сессию БД
            if not id:
                db.session.add(order)
                
            # Генерация ID заказа без фиксации транзакции
            db.session.flush()
            
            # Если редактируем, временно возвращаем все запчасти заказа на склад
            if id: 
                current_parts = Part.query.filter_by(work_order_id=order.work_order_id).all()
                for part in current_parts:
                    part.work_order_id = None
                
            # Списки ID и цен запчастей из динамической формы
            part_ids = request.form.getlist('part_id[]')
            part_prices = request.form.getlist('part_price[]')

            # Привязка выбранных запчастей к заказу с обновлением цены
            for p_id, p_price in zip(part_ids, part_prices):
                if p_id and p_price:
                    part = Part.query.get(int(p_id))
                    if part:
                        part.work_order_id = order.work_order_id
                        part.price = Decimal(p_price)
            
            # Финальное сохранение всех изменений одним блоком
            db.session.commit()
            
            flash(f'Заказ №{order.work_order_id} сохранен.', 'success')
            return redirect(url_for('admin_bp.admin_orders'))
        
        except Exception:
            # Откат изменений при любой ошибке
            db.session.rollback()
            flash('Ошибка сохранения заказа. Проверьте форматы данных.', 'danger')

    # Загрузка клиентов и доступных запчастей (склад + текущие в заказе)
    clients = Client.query.order_by(Client.last_name).all()

    if id:
        available_parts = Part.query.filter(or_(Part.work_order_id.is_(None), Part.work_order_id == id)).all()
    else:
        available_parts = Part.query.filter(Part.work_order_id.is_(None)).all()
        
    # Константы для отображения формы
    statuses = ['Принят', 'В ремонте', 'Ожидает запчасти', 'Готов к выдаче', 'Выдан', 'Отменен']
    title = "Новый заказ" if not id else f"Редактировать заказ №{order.work_order_id}"
    today = date.today().strftime('%Y-%m-%d')
    return render_template('forms/order_form.html', order=order, clients=clients, available_parts=available_parts, statuses=statuses, title=title, submit_text="Сохранить", today=today)


@admin_bp.route('/order/<int:id>/delete', methods=['POST'], endpoint='delete_order')
@admin_required
def delete_order(id):
    order = WorkOrder.query.get_or_404(id)
    try:
        db.session.delete(order)
        db.session.commit()
        flash(f'Заказ №{order.work_order_id} удален.', 'warning')
    except Exception:
        db.session.rollback()
        flash('Ошибка удаления заказа. Убедитесь, что нет привязанных запчастей.', 'danger')
    return redirect(url_for('admin_bp.admin_orders'))


@admin_bp.route('/order/<int:id>/change_status', methods=['POST', 'GET'], endpoint='change_order_status')
@admin_required
def change_order_status(id):
    order = WorkOrder.query.get_or_404(id)
    statuses = ['Принят', 'В ремонте', 'Ожидает запчасти', 'Готов к выдаче', 'Выдан', 'Отменен']
    try:
        idx = statuses.index(order.status) if order.status in statuses else 0
        if idx < len(statuses) - 1:
            order.status = statuses[idx + 1]
            db.session.commit()
            flash(f'Статус заказа №{order.work_order_id} изменён на "{order.status}"', 'success')
        else:
            flash('Нельзя изменить статус дальше.', 'warning')
    except Exception:
        db.session.rollback()
        flash('Ошибка при изменении статуса.', 'danger')
    return redirect(url_for('admin_bp.admin_orders'))


@admin_bp.route('/parts', methods=['GET'], endpoint='admin_parts')
@admin_required
def admin_parts():
    search_query = request.args.get('q', '').strip()
    parts_q = Part.query.order_by(Part.part_id.desc())
    if search_query:
        search = f'%{search_query}%'
        parts_q = parts_q.filter(Part.name.ilike(search))
    return render_template('admin/admin_parts.html', parts=parts_q.all(), search_query=search_query)


@admin_bp.route('/part/manage', methods=['GET', 'POST'], endpoint='add_part')
@admin_bp.route('/part/manage/<int:id>', methods=['GET', 'POST'], endpoint='edit_part')
@admin_required
def manage_part(id=None):
    part = Part.query.get_or_404(id) if id else Part()
    if request.method == 'POST':
        try:
            part.name = request.form.get('name', '').strip()
            part.price = Decimal(request.form.get('price', part.price or '0.00')) if request.form.get('price') else part.price
            part.supply_id = int(request.form.get('supply_id', 0))
            if not id:
                db.session.add(part)
            db.session.commit()
            flash(f'Запчасть "{part.name}" сохранена.', 'success')
            return redirect(url_for('admin_bp.admin_parts'))
        except Exception:
            db.session.rollback()
            flash('Ошибка сохранения запчасти.', 'danger')
    
    supplies = Supply.query.all()
    title = "Добавить запчасть" if not id else f"Редактировать запчасть {part.name}"
    return render_template('forms/part_form.html', part=part, supplies=supplies, title=title, submit_text="Сохранить")


@admin_bp.route('/part/<int:id>/delete', methods=['POST'], endpoint='delete_part')
@admin_required
def delete_part(id):
    part = Part.query.get_or_404(id)
    try:
        db.session.delete(part)
        db.session.commit()
        flash(f'Запчасть "{part.name}" удалена.', 'warning')
    except Exception:
        db.session.rollback()
        flash('Ошибка удаления запчасти.', 'danger')
    return redirect(url_for('admin_bp.admin_parts'))


@admin_bp.route('/suppliers', methods=['GET'], endpoint='admin_suppliers')
@admin_required
def admin_suppliers():
    search_query = request.args.get('q', '').strip()
    suppliers_q = Supplier.query.order_by(Supplier.name)
    if search_query:
        search = f'%{search_query}%'
        suppliers_q = suppliers_q.filter(Supplier.name.ilike(search))
    return render_template('admin/admin_suppliers.html', suppliers=suppliers_q.all(), search_query=search_query)


@admin_bp.route('/supplier/manage', methods=['GET', 'POST'], endpoint='add_supplier')
@admin_bp.route('/supplier/manage/<int:id>', methods=['GET', 'POST'], endpoint='edit_supplier')
@admin_required
def manage_supplier(id=None):
    supplier = Supplier.query.get_or_404(id) if id else Supplier()
    if request.method == 'POST':
        try:
            name = request.form.get('name', '').strip()
            if not name:
                flash('Имя поставщика обязательно.', 'danger')
                return redirect(request.url)
            supplier.name = name
            supplier.contacts = request.form.get('contacts', '').strip()
            if not id:
                db.session.add(supplier)
            db.session.commit()
            flash(f'Поставщик "{supplier.name}" сохранен.', 'success')
            return redirect(url_for('admin_bp.admin_suppliers'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка сохранения поставщика: {str(e)}', 'danger')
    title = "Добавить поставщика" if not id else f"Редактировать поставщика {supplier.name}"
    return render_template('forms/supplier_form.html', supplier=supplier, title=title, submit_text="Сохранить")


@admin_bp.route('/supplier/<int:id>/delete', methods=['POST'], endpoint='delete_supplier')
@admin_required
def delete_supplier(id):
    supplier = Supplier.query.get_or_404(id)
    try:
        db.session.delete(supplier)
        db.session.commit()
        flash(f'Поставщик "{supplier.name}" удален.', 'warning')
    except Exception:
        db.session.rollback()
        flash('Ошибка удаления поставщика. Убедитесь, что нет связанных поставок.', 'danger')
    return redirect(url_for('admin_bp.admin_suppliers'))


@admin_bp.route('/supplies', methods=['GET'], endpoint='admin_supplies')
@admin_required
def admin_supplies():
    search_query = request.args.get('q', '').strip()
    date_filter = request.args.get('date', '').strip()
    
    supplies_q = Supply.query.join(Supplier).order_by(Supply.supply_date.desc())
    
    if search_query:
        search = f'%{search_query}%'
        supplies_q = supplies_q.filter(or_(
            Supplier.name.ilike(search),
            Part.name.ilike(search)
        )).outerjoin(Part, Supply.supply_id == Part.supply_id)
    
    if date_filter:
        try:
            date_obj = datetime.strptime(date_filter, '%Y-%m-%d').date()
            supplies_q = supplies_q.filter(Supply.supply_date == date_obj)
        except ValueError:
            pass
    
    return render_template('admin/admin_supplies.html', supplies=supplies_q.all(), search_query=search_query, 
                          date_filter=date_filter)


@admin_bp.route('/supply/manage', methods=['GET', 'POST'], endpoint='add_supply')
@admin_bp.route('/supply/manage/<int:id>', methods=['GET', 'POST'], endpoint='edit_supply')
@admin_required
def manage_supply(id=None):
    supply = Supply.query.get_or_404(id) if id else Supply(supply_date=date.today())
    
    if request.method == 'POST':
        try:
            date_str = request.form.get('supply_date')
            if not date_str:
                flash('Дата поставки обязательна.', 'danger')
                return redirect(request.url)
            
            supply.supplier_id = int(request.form['supplier_id'])
            supply.supply_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            supply.details = request.form.get('details', '').strip()
            
            # Если редактируем существующую поставку, удаляем старые запчасти
            if id:
                for part in supply.parts.all():
                    db.session.delete(part)
            
            # Сначала сохраняем саму поставку
            if not id:
                db.session.add(supply)
            
            # flush() отправляет данные в БД и получает ID для supply, 
            db.session.flush() 
            
            # Теперь добавляем новые запчасти
            part_names = request.form.getlist('part_name[]')
            part_prices = request.form.getlist('part_price[]')
            
            for part_name, part_price in zip(part_names, part_prices):
                if part_name.strip() and part_price:
                    try:
                        new_part = Part(
                            name=part_name.strip(),
                            price=Decimal(part_price),
                            supply_id=supply.supply_id,
                            work_order_id=None  # Новые запчасти на складе
                        )
                        db.session.add(new_part)
                    except (ValueError, TypeError):
                        pass
            
            db.session.commit()
            flash(f'Поставка №{supply.supply_id} сохранена.', 'success')
            return redirect(url_for('admin_bp.admin_supplies'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка сохранения поставки: {str(e)}', 'danger')
            return redirect(request.url)

    suppliers = Supplier.query.order_by(Supplier.name).all()
    today = date.today().strftime('%Y-%m-%d')
    title = "Новая поставка" if not id else f"Редактировать поставку №{supply.supply_id}"
    return render_template('forms/supply_form.html', supply=supply, suppliers=suppliers, today=today, title=title, submit_text="Сохранить")


@admin_bp.route('/supply/<int:id>/delete', methods=['POST'], endpoint='delete_supply')
@admin_required
def delete_supply(id):
    supply = Supply.query.get_or_404(id)
    try:
        db.session.delete(supply)
        db.session.commit()
        flash(f'Поставка №{supply.supply_id} удалена.', 'warning')
    except Exception:
        db.session.rollback()
        flash('Ошибка удаления поставки. Убедитесь, что нет связанных запчастей.', 'danger')
    return redirect(url_for('admin_bp.admin_supplies'))


@admin_bp.route('/users', methods=['GET'], endpoint='admin_users')
@admin_required
def admin_users():
    search_query = request.args.get('q', '').strip()
    date_filter = request.args.get('date', '').strip()
    users_q = User.query.order_by(desc(User.created_at))
    
    if search_query:
        search = f'%{search_query}%'
        users_q = users_q.filter(or_(
            User.email.ilike(search), 
            Client.last_name.ilike(search)
        )).outerjoin(Client, User.client_id == Client.client_id)
    if date_filter:
        try:
            date_obj = datetime.strptime(date_filter, '%Y-%m-%d').date()
            users_q = users_q.filter(User.created_at >= date_obj).filter(User.created_at < date_obj + datetime.timedelta(days=1))
        except ValueError:
            pass
    return render_template('admin/admin_users.html', users=users_q.all(), search_query=search_query, date_filter=date_filter)
