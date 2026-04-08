# LinkCom.mx Backend (corregido)

Backend base para LinkCom.mx con Flask, PostgreSQL, SQLAlchemy, JWT y Flask-Migrate.

## Qué cambió respecto al intento anterior

- **Ya no incluye una migración inicial manual**.
- **Tú generas la primera migración automáticamente** con `flask db migrate`.
- **No uso enums nativos de PostgreSQL** para `role`, `status`, `section_type`, etc.
  Todo eso está modelado con columnas `String`, para evitar pedos con `CREATE TYPE` al arrancar.
- **Los proveedores no tienen cuenta**.
- El chat es **usuario ↔ admin**.

## Estructura

```
.
├── app/
│   ├── api/
│   ├── __init__.py
│   ├── config.py
│   ├── constants.py
│   ├── decorators.py
│   ├── extensions.py
│   ├── models.py
│   └── seed.py
├── .env.example
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── run.py
```

## Primer arranque

```bash
cp .env.example .env
docker compose up --build -d
```

## Generar la migración inicial

Como este proyecto ya viene pensado para que **tú la autogeneres**, corre esto:

```bash
docker compose exec api flask db init
docker compose exec api flask db migrate -m "initial schema"
docker compose exec api flask db upgrade
```

## Meter datos demo

```bash
docker compose exec api flask seed-demo
```

## Usuarios demo del seed

- Admin: `admin@linkcom.mx` / `Admin123!`
- User: `user@linkcom.mx` / `User123!`

## Reset rápido si la base se ensucia

```bash
docker compose exec db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
rm -rf migrations

docker compose exec api flask db init
docker compose exec api flask db migrate -m "initial schema"
docker compose exec api flask db upgrade
docker compose exec api flask seed-demo
```

## Endpoints incluidos

### Health
- `GET /api/health`

### Auth
- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`

### Catálogo
- `GET /api/categories`
- `GET /api/promotions`
- `GET /api/suppliers`
- `GET /api/suppliers/<supplier_id>`
- `GET /api/suppliers/slug/<slug>`
- `GET /api/suppliers/<supplier_id>/products`
- `GET /api/video-sections`
- `GET /api/videos`

### Chat usuario/admin
- `GET /api/chat/conversations`
- `POST /api/chat/conversations`
- `GET /api/chat/conversations/<conversation_id>/messages`
- `POST /api/chat/conversations/<conversation_id>/messages`
- `PATCH /api/chat/conversations/<conversation_id>/read`

### Solicitudes
- `POST /api/submissions`
- `GET /api/submissions`
- `GET /api/submissions/<submission_id>`

### Admin
- `GET /api/admin/dashboard`
- `GET /api/admin/categories`
- `POST /api/admin/categories`
- `PATCH /api/admin/categories/<category_id>`
- `DELETE /api/admin/categories/<category_id>`
- `GET /api/admin/suppliers`
- `POST /api/admin/suppliers`
- `PATCH /api/admin/suppliers/<supplier_id>`
- `DELETE /api/admin/suppliers/<supplier_id>`
- `GET /api/admin/suppliers/<supplier_id>/products`
- `POST /api/admin/suppliers/<supplier_id>/products`
- `PATCH /api/admin/products/<product_id>`
- `DELETE /api/admin/products/<product_id>`
- `GET /api/admin/promotions`
- `POST /api/admin/promotions`
- `PATCH /api/admin/promotions/<promotion_id>`
- `DELETE /api/admin/promotions/<promotion_id>`
- `GET /api/admin/video-sections`
- `POST /api/admin/video-sections`
- `PATCH /api/admin/video-sections/<section_id>`
- `DELETE /api/admin/video-sections/<section_id>`
- `GET /api/admin/videos`
- `POST /api/admin/videos`
- `PATCH /api/admin/videos/<video_id>`
- `DELETE /api/admin/videos/<video_id>`
- `GET /api/admin/submissions`
- `PATCH /api/admin/submissions/<submission_id>/status`

## Ejemplos rápidos

```bash
curl http://localhost:51783/api/health
```

```bash
curl -X POST http://localhost:51783/api/auth/login   -H "Content-Type: application/json"   -d '{
    "email": "admin@linkcom.mx",
    "password": "Admin123!"
  }'
```
