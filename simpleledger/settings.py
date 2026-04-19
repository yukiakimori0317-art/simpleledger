from pathlib import Path
import os
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get(
    "SECRET_KEY",
    "django-insecure-change-me"
)

#DEBUG = os.environ.get("DEBUG", "False") == "True"
DEBUG = True

ALLOWED_HOSTS = os.environ.get(
    "ALLOWED_HOSTS",
    "127.0.0.1,localhost,.onrender.com"
).split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    'django.contrib.humanize',

    # 自分のアプリ
    "kakeibo",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",

    # WhiteNoise は SecurityMiddleware の直後
    "whitenoise.middleware.WhiteNoiseMiddleware",

    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "simpleledger.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "kakeibo.context_processors.nickname_context",
            ],
        },
    },
]

WSGI_APPLICATION = "simpleledger.wsgi.application"

DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "ja"
TIME_ZONE = "Asia/Tokyo"
USE_I18N = True
USE_TZ = True

# ---------- Static ----------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# プロジェクト直下の static を読む
STATICFILES_DIRS = [
    BASE_DIR / "static",
]

# Django 4.2+ 以降はこちら推奨
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# WhiteNoise の追加設定
WHITENOISE_USE_FINDERS = False
WHITENOISE_AUTOREFRESH = DEBUG

# ---------- Media ----------
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ---------- Auth ----------
LOGIN_URL = "kakeibo:login"
LOGIN_REDIRECT_URL = "kakeibo:index"
LOGOUT_REDIRECT_URL = "kakeibo:login"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"