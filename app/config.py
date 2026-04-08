import os


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'change-me-in-production')
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL',
        'postgresql+psycopg://linkcom:linkcom123@localhost:56329/linkcom',
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'change-me-too')
    JWT_ACCESS_TOKEN_EXPIRES = 60 * 60 * 24
    JSON_SORT_KEYS = False
    CORS_ORIGINS = [origin.strip() for origin in os.getenv('CORS_ORIGINS', '*').split(',') if origin.strip()]
