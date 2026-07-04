#!/usr/bin/env python
"""
One-time setup script: creates admin superuser if not exists.
Run via: python backend_app/setup_admin.py
"""
import os
import sys
import django

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vidnex_platform.settings')
django.setup()

from django.contrib.auth.models import User
from core.models import UserProfile

email = os.getenv('ADMIN_EMAIL', 'admin@vidnex.com')
password = os.getenv('ADMIN_PASSWORD', 'Admin@1234')

if not User.objects.filter(email=email).exists():
    user = User.objects.create_superuser(
        username=email,
        email=email,
        password=password
    )
    UserProfile.objects.filter(user=user).update(role='admin', status='approved')
    print(f"Admin created: {email}")
else:
    print(f"Admin already exists: {email}")
