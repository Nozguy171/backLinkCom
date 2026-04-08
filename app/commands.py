from app.extensions import db
from app.models import User


def register_commands(app):
    @app.cli.command("create-admin")
    def create_admin():
        email = "admin@linkcom.mx"
        password = "admin123"
        name = "Administrador Demo"

        existing = User.query.filter_by(email=email).first()

        if existing:
            existing.name = name
            existing.role = "admin"
            existing.company = "LinkCom.mx"
            existing.phone = "6860000000"
            existing.set_password(password)
            db.session.commit()

            print("Admin actualizado correctamente")
            print(f"Email: {email}")
            print(f"Password: {password}")
            return

        user = User(
            name=name,
            email=email,
            role="admin",
            company="LinkCom.mx",
            phone="6860000000",
        )
        user.set_password(password)

        db.session.add(user)
        db.session.commit()

        print("Admin creado correctamente")
        print(f"Email: {email}")
        print(f"Password: {password}")