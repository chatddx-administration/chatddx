# src/chatddx/django/settings/prod.py
import os
from pathlib import Path

DEBUG = False

with open(os.environ["SECRET_KEY_FILE"]) as f:
    SECRET_KEY = f.read()

SALT_KEY = SECRET_KEY

ALLOWED_HOSTS = ["." + os.environ["HOST"]]


SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
