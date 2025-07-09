# backend/settings.py

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import urllib.parse

# --- IMPORTANT: Add virtual environment's site-packages to sys.path ---
# This helps Celery and other processes find packages correctly on Windows.
# Determine the path to the virtual environment's site-packages
# Assumes 'venv' is in the project root.
venv_path = os.path.join(Path(__file__).resolve().parent.parent, 'venv')

# Common paths for site-packages in virtual environments
site_packages_paths = [
    os.path.join(venv_path, 'Lib', 'site-packages'), # Windows
    os.path.join(venv_path, 'lib', f'python{sys.version_info.major}.{sys.version_info.minor}', 'site-packages'), # Linux/macOS
]

for sp_path in site_packages_paths:
    if os.path.exists(sp_path) and sp_path not in sys.path:
        sys.path.insert(0, sp_path)
        break

# ---------------------------------------------------------------------


# Load environment variables from .env file
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'your-super-secret-key-for-dev')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DJANGO_DEBUG', 'True') == 'True'

ALLOWED_HOSTS = ['*'] # Allow all hosts for development, restrict in production


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'channels',
    'audio_processor', # Our custom app
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

ROOT_URLCONF = 'backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'frontend')], # Point to our frontend directory
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

WSGI_APPLICATION = 'backend.wsgi.application'
ASGI_APPLICATION = 'backend.asgi.application' # For Channels


# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/

STATIC_URL = 'static/'
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'frontend', 'static'), # Serve static files from frontend/static
]
# Define STATIC_ROOT for collectstatic and for Django's static file serving in DEBUG mode
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles') # This directory will hold collected static files


# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Channels settings
# Use a simple host/port for direct connection if REDIS_URL is not complex
REDIS_HOST = os.environ.get('REDIS_HOST', '127.0.0.1') # CHANGED FROM 'localhost' TO '127.0.0.1'
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.pubsub.RedisPubSubChannelLayer',
        'CONFIG': {
            "hosts": [f"redis://{REDIS_HOST}:{REDIS_PORT}/0"], # Use f-string for clarity
        },
    },
}

# Celery settings
CELERY_BROKER_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/0" # Use f-string for clarity
CELERY_RESULT_BACKEND = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_IMPORTS = ('audio_processor.tasks',)
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# OpenAI API Key
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
if not OPENAI_API_KEY:
    print("WARNING: OPENAI_API_KEY not set in environment variables.")

# Keyword configuration
DEFAULT_KEYWORDS = [
    "pricing", "cost", "budget", "discount", "feature", "solution",
    "problem", "challenge", "competitor", "roadmap", "integration",
    "support", "onboarding", "ROI", "value proposition"
]

# --- Logging Configuration ---
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple'
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'audio_processor': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'channels': {
            'handlers': ['console'],
            'level': 'DEBUG', # Keep DEBUG for Channels to see dispatching
            'propagate': False,
        },
        'channels_redis': {
            'handlers': ['console'],
            'level': 'DEBUG', # Set to DEBUG to see Redis interaction
            'propagate': False,
        },
        'celery': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'celery.app.trace': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'celery.app.autoreload': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'celery.worker.consumer.consumer': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'openai': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    }
}
