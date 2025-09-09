# backend/settings.py

import os
from pathlib import Path
from dotenv import load_dotenv
import urllib.parse # Import urllib.parse to parse the Redis URL

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
# Get Redis URL from environment or use default
REDIS_URL_STR = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

# Parse the Redis URL to extract host and port
# This ensures explicit host/port are passed to channels_redis
parsed_redis_url = urllib.parse.urlparse(REDIS_URL_STR)
REDIS_HOST = parsed_redis_url.hostname
REDIS_PORT = parsed_redis_url.port if parsed_redis_url.port else 6379 # Default Redis port

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.pubsub.RedisPubSubChannelLayer',
        'CONFIG': {
            "hosts": [{
                'host': REDIS_HOST,
                'port': REDIS_PORT,
                'db': 0 # Assuming database 0 from the default URL
            }],
        },
    },
}

# Celery settings
CELERY_BROKER_URL = REDIS_URL_STR # Keep using the URL string for Celery
CELERY_RESULT_BACKEND = REDIS_URL_STR
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json' # CORRECTED THIS LINE - Removed the extra ']'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_IMPORTS = ('audio_processor.tasks',) # Ensure Celery finds your tasks
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True # Ensure Celery retries connection on startup

# OpenAI API Key
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
if not OPENAI_API_KEY:
    print("WARNING: OPENAI_API_KEY not set in environment variables.")

# OpenAI Organization and Project IDs
OPENAI_ORGANIZATION_ID = os.environ.get('OPENAI_ORGANIZATION_ID')
OPENAI_PROJECT_ID = os.environ.get('OPENAI_PROJECT_ID')


# Keyword configuration (can be moved to DB for dynamic management)
# For now, a simple list
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
            'level': 'DEBUG', # Set console handler to DEBUG to see all messages
            'class': 'logging.StreamHandler',
            'formatter': 'simple'
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO', # Django's default logs
            'propagate': False,
        },
        'django.request': { # For HTTP requests (4xx, 5xx errors)
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'audio_processor': { # Your custom app's logger
            'handlers': ['console'],
            'level': 'DEBUG', # Set to DEBUG to see all custom app logs
            'propagate': False,
        },
        'channels': { # Django Channels internal logs
            'handlers': ['console'],
            'level': 'DEBUG', # Keep DEBUG for Channels to see dispatching
            'propagate': False,
        },
        'channels_redis': { # Channels Redis backend logs
            'handlers': ['console'],
            'level': 'DEBUG', # Set to DEBUG to see Redis interaction
            'propagate': False,
        },
        'celery': { # Celery overall logs
            'handlers': ['console'],
            'level': 'INFO', # Celery's default logs
            'propagate': False,
        },
        'celery.app.trace': { # Celery task execution traces
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'celery.worker.consumer.consumer': { # Celery worker consumer details
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'celery.beat': { # Celery beat scheduler logs
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'openai': { # OpenAI library logs
            'handlers': ['console'],
            'level': 'INFO', # Keep OpenAI logging at INFO or WARNING
            'propagate': False,
        },
        'httpx': { # HTTPX library (used by OpenAI client)
            'handlers': ['console'],
            'level': 'WARNING', # Suppress verbose HTTPX logs unless debugging network
            'propagate': False,
        },
        'daphne': { # Daphne server logs
            'handlers': ['console'],
            'level': 'INFO', # Keep Daphne logs at INFO for general operation
            'propagate': False,
        },
        'urllib3': { # Used by requests/httpx
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'asyncio': { # Python's asyncio library
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    }
}
