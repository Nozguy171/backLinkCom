from datetime import datetime, timedelta, timezone

from slugify import slugify

from app.extensions import db
from app.models import (
    Category,
    ChatConversation,
    ChatMessage,
    Product,
    Promotion,
    Setting,
    Submission,
    Supplier,
    SupplierCategory,
    User,
    Video,
    VideoSection,
)


UTC_NOW = lambda: datetime.now(timezone.utc)


def register_seed_commands(app):
    @app.cli.command('seed-demo')
    def seed_demo_command():
        seed_demo()



def seed_demo():
    admin = User.query.filter_by(email='admin@linkcom.mx').first()
    if not admin:
        admin = User(name='Admin LinkCom', email='admin@linkcom.mx', role='admin', company='LinkCom.mx')
        admin.set_password('Admin123!')
        db.session.add(admin)

    user = User.query.filter_by(email='user@linkcom.mx').first()
    if not user:
        user = User(name='Usuario Demo', email='user@linkcom.mx', role='user', company='Tienda Demo')
        user.set_password('User123!')
        db.session.add(user)

    db.session.flush()

    category_names = [
        'Ropa deportiva',
        'Ropa de verano',
        'Ropa de gala',
        'Accesorios',
        'Calzado',
        'Temporada',
    ]
    categories = {}
    for idx, name in enumerate(category_names, start=1):
        slug = slugify(name)
        category = Category.query.filter_by(slug=slug).first()
        if not category:
            category = Category(name=name, slug=slug, display_order=idx, is_active=True)
            db.session.add(category)
        categories[slug] = category

    db.session.flush()

    suppliers_data = [
        {
            'name': 'Textiles Nova',
            'description': 'Proveedor de ropa deportiva y básicos para negocio.',
            'location': 'Monterrey, NL',
            'categories': ['ropa-deportiva', 'temporada'],
            'featured': True,
        },
        {
            'name': 'Calzado Prisma',
            'description': 'Calzado casual y de temporada para mayoreo.',
            'location': 'León, GTO',
            'categories': ['calzado', 'temporada'],
            'featured': True,
        },
        {
            'name': 'Accesorios Orión',
            'description': 'Accesorios de moda y catálogo flexible.',
            'location': 'CDMX',
            'categories': ['accesorios'],
            'featured': False,
        },
    ]

    created_suppliers = []
    for idx, info in enumerate(suppliers_data, start=1):
        slug = slugify(info['name'])
        supplier = Supplier.query.filter_by(slug=slug).first()
        if not supplier:
            supplier = Supplier(
                name=info['name'],
                slug=slug,
                description=info['description'],
                logo_url=f'https://placehold.co/200x200?text={slug}',
                banner_url=f'https://placehold.co/1200x320?text={slug}',
                location=info['location'],
                rating=4.5,
                review_count=20 * idx,
                years_in_business=5 + idx,
                employee_count='10-50',
                website=f'https://{slug}.example.com',
                email=f'contacto@{slug}.mx',
                phone='6860000000',
                is_verified=True,
                is_featured=info['featured'],
                is_active=True,
            )
            db.session.add(supplier)
            db.session.flush()
            for cat_index, category_slug in enumerate(info['categories']):
                db.session.add(
                    SupplierCategory(
                        supplier_id=supplier.id,
                        category_id=categories[category_slug].id,
                        is_primary=cat_index == 0,
                    )
                )
            for product_index in range(1, 4):
                db.session.add(
                    Product(
                        supplier_id=supplier.id,
                        name=f'Producto {product_index} de {supplier.name}',
                        description='Producto demo para catálogo.',
                        image_url=f'https://placehold.co/600x400?text=producto+{product_index}',
                        price=199.99 + (product_index * 50),
                        sku=f'{slug.upper()}-{product_index:03d}',
                        is_active=True,
                    )
                )
        created_suppliers.append(supplier)

    now = UTC_NOW()
    if Promotion.query.count() == 0:
        db.session.add(
            Promotion(
                title='Campaña de temporada',
                subtitle='Descubre proveedores destacados para primavera-verano.',
                image_url='https://placehold.co/1200x500?text=promo+linkcom',
                link_url='/suppliers',
                badge_text='NUEVO',
                display_order=1,
                starts_at=now - timedelta(days=1),
                ends_at=now + timedelta(days=30),
                is_active=True,
                supplier_id=created_suppliers[0].id if created_suppliers else None,
            )
        )

    sections_data = [
        ('Rápido y sencillo', 'rapido-y-sencillo', 'clips'),
        ('Crecimiento y desarrollo', 'crecimiento-y-desarrollo', 'workshops'),
    ]
    sections = {}
    for idx, (name, slug, section_type) in enumerate(sections_data, start=1):
        section = VideoSection.query.filter_by(slug=slug).first()
        if not section:
            section = VideoSection(
                name=name,
                slug=slug,
                description=f'Sección demo: {name}',
                section_type=section_type,
                display_order=idx,
                is_active=True,
            )
            db.session.add(section)
        sections[slug] = section

    db.session.flush()

    if Video.query.count() == 0:
        db.session.add_all([
            Video(
                section_id=sections['rapido-y-sencillo'].id,
                supplier_id=created_suppliers[0].id if created_suppliers else None,
                title='Cómo pedir mercancía en 2 minutos',
                description='Video corto demo.',
                thumbnail_url='https://placehold.co/480x800?text=clip+1',
                video_url='https://example.com/videos/clip-1',
                duration='0:45',
                view_count=120,
                display_order=1,
                is_active=True,
            ),
            Video(
                section_id=sections['crecimiento-y-desarrollo'].id,
                supplier_id=created_suppliers[1].id if len(created_suppliers) > 1 else None,
                title='Taller: cómo evaluar un proveedor',
                description='Taller demo largo.',
                thumbnail_url='https://placehold.co/640x360?text=taller+1',
                video_url='https://example.com/videos/workshop-1',
                duration='18:20',
                view_count=340,
                display_order=1,
                is_active=True,
            ),
        ])

    if ChatConversation.query.count() == 0 and admin and user:
        conversation = ChatConversation(user_id=user.id, assigned_admin_id=admin.id, last_message_at=now)
        db.session.add(conversation)
        db.session.flush()
        db.session.add_all([
            ChatMessage(
                conversation_id=conversation.id,
                sender_user_id=user.id,
                sender_role='user',
                content='Hola, quisiera saber si tienen proveedores de ropa deportiva.',
                is_read=True,
            ),
            ChatMessage(
                conversation_id=conversation.id,
                sender_user_id=admin.id,
                sender_role='admin',
                content='Sí, te podemos ayudar. Revisa Textiles Nova y Calzado Prisma.',
                is_read=False,
            ),
        ])

    if Submission.query.count() == 0 and user:
        db.session.add(
            Submission(
                user_id=user.id,
                supplier_id=created_suppliers[0].id if created_suppliers else None,
                submission_type='extra_merchandise',
                status='pending',
                data={
                    'productName': 'Playeras dry-fit',
                    'quantity': '250',
                    'specifications': 'Tallas surtidas, colores neutros',
                    'deliveryDate': (now + timedelta(days=14)).date().isoformat(),
                    'budget': '25000',
                },
                notes='Solicitud demo cargada por seed.',
            )
        )

    if Setting.query.count() == 0:
        db.session.add_all([
            Setting(key='site_name', value='LinkCom.mx', description='Nombre del sitio'),
            Setting(key='support_email', value='soporte@linkcom.mx', description='Correo de soporte'),
            Setting(key='max_promotions_home', value='5', description='Cantidad máxima de promos en home'),
        ])

    db.session.commit()
    print('Seed demo completado.')
