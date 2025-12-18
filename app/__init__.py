import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config import Config
from datetime import datetime

db = SQLAlchemy()

def create_app(config_class=Config):
    app = Flask(__name__) 
    
    app.config.from_object(config_class)

    db.init_app(app)

    def date_fmt(date_obj):
        if date_obj:
            return date_obj.strftime('%d.%m.%Y')
        return '-'
    app.jinja_env.filters['date_fmt'] = date_fmt

    def rubles_fmt(value):
        try:
            return f"{float(value):,.2f} BYN".replace(",", " ").replace(".", ",")
        except Exception:
            return "0,00 BYN"
    app.jinja_env.filters['rubles'] = rubles_fmt

    from app.routes import auth_bp, main_bp, admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)

    with app.app_context():
        from app import models
        models.ensure_admin_user()


    return app
