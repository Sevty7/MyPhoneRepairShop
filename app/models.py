from app import db
from datetime import datetime
from decimal import Decimal
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import func
import os


class Role(db.Model):
    __tablename__ = 'role'
    role_id = db.Column(db.Integer, primary_key=True)
    role_name = db.Column(db.String(20), unique=True, nullable=False)

    users = db.relationship('User', backref='role_obj', lazy=True)

    def __repr__(self):
        return f'<Role {self.role_name}>'
    
    
class User(db.Model):
    __tablename__ = 'user_account'
    user_account_id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    
    role_id = db.Column(db.Integer, db.ForeignKey('role.role_id'), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('client.client_id'), unique=True, nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)


    @property
    def role(self):
        #Возвращает строковое название роли
        if self.role_obj:
            return self.role_obj.role_name
        return None
    
    @property
    def display_name(self):
        # если привязан к клиенту — показываем ФИО, иначе email
        return self.email if not self.client_id else (self.client.full_name if self.client else self.email)


class Client(db.Model):
    __tablename__ = 'client'
    client_id = db.Column(db.Integer, primary_key=True)
    last_name = db.Column(db.String(50), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    middle_name = db.Column(db.String(50))
    phone = db.Column(db.String(20), index=True, unique=True)

    orders = db.relationship('WorkOrder', backref='client', lazy='dynamic')
    user = db.relationship('User', backref='client', uselist=False, lazy=True)

    @property
    def full_name(self):
        return f"{self.last_name} {self.first_name} {self.middle_name or ''}".strip()


class WorkOrder(db.Model):
    __tablename__ = 'work_order'
    work_order_id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client.client_id'), nullable=False, index=True)
    phone_model = db.Column(db.String(100), nullable=False)
    problem_description = db.Column(db.Text)
    received_date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    completion_date = db.Column(db.Date)
    status = db.Column(db.String(50), default='Принят')
    work_cost = db.Column(db.Numeric(10, 2), default=Decimal('0.00'))

    parts = db.relationship('Part', backref='order', lazy='dynamic')

    @property
    def total_parts_cost(self):
        total = db.session.query(func.sum(Part.price)).filter(Part.work_order_id == self.work_order_id).scalar()
        return total or Decimal('0.00')

    @property
    def total_cost(self):
        return (self.work_cost or Decimal('0.00')) + self.total_parts_cost

    @property
    def can_be_canceled(self):
        return self.status == 'Принят'

 
class Part(db.Model):
    __tablename__ = 'part'
    part_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    supply_id = db.Column(db.Integer, db.ForeignKey('supply.supply_id'), nullable=False, index=True)
    work_order_id = db.Column(db.Integer, db.ForeignKey('work_order.work_order_id'), nullable=True, index=True)


class Supply(db.Model):
    __tablename__ = 'supply'
    supply_id = db.Column(db.Integer, primary_key=True)
    supply_date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.supplier_id'), nullable=False, index=True)

    parts = db.relationship('Part', backref='supply', lazy='dynamic')
    

class Supplier(db.Model):
    __tablename__ = 'supplier'
    supplier_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    contacts = db.Column(db.Text)

    supplies = db.relationship('Supply', backref='supplier', lazy='dynamic')


# --- Вспомогательные функции ---

def ensure_admin_user():
    # Создаем роли, если их нет
    if Role.query.count() == 0:
        db.session.add(Role(role_name='admin'))
        db.session.add(Role(role_name='client'))
        db.session.commit()
        print("Роли 'admin' и 'client' созданы.")

    admin_email = os.environ.get('ADMIN_EMAIL') or 'admin@example.com'
    admin_password = os.environ.get('ADMIN_PASSWORD') or 'admin123'

    existing = User.query.filter_by(email=admin_email).first()
    if existing is None:
        admin_role = Role.query.filter_by(role_name='admin').first()
        if admin_role:
            admin_user = User(email=admin_email, role_id=admin_role.role_id, client_id=None)
            admin_user.set_password(admin_password)
            db.session.add(admin_user)
            db.session.commit()
            print(f"Администратор '{admin_email}' создан.")
