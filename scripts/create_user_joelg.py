#!/usr/bin/env python
"""
Script para crear usuario Joelg.

Ejecutar con PostgreSQL local activo:
    cd backend && python ../scripts/create_user_joelg.py

O desde Azure Cloud Shell conectado a la BD de produccion.
"""
import os
import sys

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

import django
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

EMAIL = 'joelg@casateva.es'
PASSWORD = 'CasaTeva2026!'
USERNAME = 'joelg'
FIRST_NAME = 'Joel'
LAST_NAME = 'G'


def create_user():
    if User.objects.filter(email=EMAIL).exists():
        print(f'Usuario {EMAIL} ya existe')
        return

    user = User.objects.create_user(
        username=USERNAME,
        email=EMAIL,
        password=PASSWORD,
        first_name=FIRST_NAME,
        last_name=LAST_NAME,
    )
    print(f'Usuario creado: {user.email}')


if __name__ == '__main__':
    create_user()
