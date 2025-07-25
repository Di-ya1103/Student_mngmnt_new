
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # Points to C:\Student_mngmnt_new\stuproject

SECRET_KEY = 'your-secret-key-here'  # Replace with a secure value

DEBUG = True

ALLOWED_HOSTS = []

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'students',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'stuproject.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'stuproject.wsgi.application'

# Database Configuration
# Using MySQL with the 'student_manages' database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'student_manages',
        'USER': 'root',  # Replace with your MySQL username (e.g., 'root')
        'PASSWORD': 'root',  # Replace with your MySQL password
        'HOST': 'localhost',
        'PORT': '3306',
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

STATIC_URL = '/static/'

# This is where Django will look for *extra* static files (used during development)
STATICFILES_DIRS = [
    BASE_DIR / 'static',  # example: custom folder for your static files
]

# This is where static files will be *collected* to during collectstatic (for production)
STATIC_ROOT = BASE_DIR / 'staticfiles'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Authentication settings
LOGIN_URL = '/students/accounts/login/'  # URL to redirect unauthenticated users
LOGIN_REDIRECT_URL = 'students:student_list'  # URL to redirect after login
#LOGOUT_REDIRECT_URL = '/students/accounts/login/' # URL to redirect after logout
LOGOUT_REDIRECT_URL = '/students/accounts/login/'
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'diya.dave1103@gmail.com'  # Replace with your email
EMAIL_HOST_PASSWORD = 'pqhpuwmppnrawdtb'  # Replace with your app-specific password
DEFAULT_FROM_EMAIL = 'diya.dave1103@gmail.com'  # Replace with your email

# Site configuration for password reset links
SITE_ID = 1  # Ensure you have a Site object in the admin with ID=1

