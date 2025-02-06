import os
from typing import Any, List

from dotenv import load_dotenv
from environs import Env
from notifications_utils import logging

from app.articles.routing import GC_ARTICLES_ROUTES

env = Env()
env.read_env()
load_dotenv()


if os.environ.get("VCAP_APPLICATION"):
    # on cloudfoundry, config is a json blob in VCAP_APPLICATION - unpack it, and populate
    # standard environment variables from it
    from app.cloudfoundry_config import extract_cloudfoundry_config

    extract_cloudfoundry_config()


class Config(object):
    ACTIVITY_STATS_LIMIT_DAYS = 7
    ALLOW_DEBUG_ROUTE = env.bool("ALLOW_DEBUG_ROUTE", False)

    # List of allowed service IDs that are allowed to send HTML through their templates.
    ALLOW_HTML_SERVICE_IDS: List[str] = [id.strip() for id in os.getenv("ALLOW_HTML_SERVICE_IDS", "").split(",")]
    ADMIN_BASE_URL = (
        "https://" + os.environ.get("HEROKU_APP_NAME", "") + ".herokuapp.com"
        if os.environ.get("HEROKU_APP_NAME", "") != ""
        else os.environ.get("ADMIN_BASE_URL", "http://localhost:6012")
    )
    ADMIN_CLIENT_SECRET = os.environ.get("ADMIN_CLIENT_SECRET")
    ADMIN_CLIENT_USER_NAME = "notify-admin"
    ANTIVIRUS_API_HOST = os.environ.get("ANTIVIRUS_API_HOST")
    ANTIVIRUS_API_KEY = os.environ.get("ANTIVIRUS_API_KEY")
    API_HOST_NAME = os.environ.get("API_HOST_NAME")
    ASSET_DOMAIN = os.getenv("ASSET_DOMAIN", "assets.notification.canada.ca")
    ASSET_PATH = "/static/"
    ASSETS_DEBUG = False
    AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

    # Bounce Rate parameters
    BR_DISPLAY_VOLUME_MINIMUM = 1000

    BULK_SEND_AWS_BUCKET = os.getenv("BULK_SEND_AWS_BUCKET")

    CHECK_PROXY_HEADER = False
    CONTACT_EMAIL = os.environ.get("CONTACT_EMAIL", "assistance+notification@cds-snc.ca")
    CSV_MAX_ROWS = env.int("CSV_MAX_ROWS", 50_000)
    CSV_MAX_ROWS_BULK_SEND = env.int("CSV_MAX_ROWS_BULK_SEND", 100_000)
    CSV_UPLOAD_BUCKET_NAME = os.getenv("CSV_UPLOAD_BUCKET_NAME", "notification-alpha-canada-ca-csv-upload")
    DANGEROUS_SALT = os.environ.get("DANGEROUS_SALT")
    DEBUG = False
    DEBUG_KEY = os.environ.get("DEBUG_KEY", "")
    DEFAULT_FREE_SMS_FRAGMENT_LIMITS = {
        "central": 25_000,
        "local": 25_000,
        "nhs_central": 250_000,
        "nhs_local": 25_000,
        "nhs_gp": 25_000,
        "emergency_service": 25_000,
        "school_or_college": 25_000,
        "other": 25_000,
    }
    DEFAULT_LIVE_SERVICE_LIMIT = env.int("DEFAULT_LIVE_SERVICE_LIMIT", 10_000)
    DEFAULT_LIVE_SMS_DAILY_LIMIT = env.int("DEFAULT_LIVE_SMS_DAILY_LIMIT", 1000)
    DEFAULT_SERVICE_LIMIT = env.int("DEFAULT_SERVICE_LIMIT", 50)
    DEFAULT_SMS_DAILY_LIMIT = env.int("DEFAULT_SMS_DAILY_LIMIT", 50)
    DOCUMENTATION_DOMAIN = os.getenv("DOCUMENTATION_DOMAIN", "documentation.notification.canada.ca")
    REPLY_TO_DOMAINS_SAFELIST = ["gc.ca", "canada.ca"]
    EMAIL_2FA_EXPIRY_SECONDS = 1_800  # 30 Minutes
    EMAIL_EXPIRY_SECONDS = 3600  # 1 hour

    # for waffles: pull out the routes into a flat list of the form ['/home', '/accueil', '/why-gc-notify', ...]
    EXTRA_ROUTES = [item for sublist in map(lambda x: x.values(), GC_ARTICLES_ROUTES.values()) for item in sublist]

    # FEATURE FLAGS
    FF_SALESFORCE_CONTACT = env.bool("FF_SALESFORCE_CONTACT", True)
    FF_RTL = env.bool("FF_RTL", True)
    FF_ANNUAL_LIMIT = env.bool("FF_ANNUAL_LIMIT", False)

    FREE_YEARLY_EMAIL_LIMIT = env.int("FREE_YEARLY_EMAIL_LIMIT", 20_000_000)
    FREE_YEARLY_SMS_LIMIT = env.int("FREE_YEARLY_SMS_LIMIT", 100_000)
    GC_ARTICLES_API = os.environ.get("GC_ARTICLES_API", "articles.alpha.canada.ca/notification-gc-notify")
    GC_ARTICLES_API_AUTH_PASSWORD = os.environ.get("GC_ARTICLES_API_AUTH_PASSWORD")
    GC_ARTICLES_API_AUTH_USERNAME = os.environ.get("GC_ARTICLES_API_AUTH_USERNAME")
    GC_ORGANISATIONS_BUCKET_NAME = os.environ.get("GC_ORGANISATIONS_BUCKET_NAME")
    GC_ORGANISATIONS_FILENAME = os.getenv("GC_ORGANISATIONS_FILENAME", "all.json")
    GOOGLE_ANALYTICS_ID = os.getenv("GOOGLE_ANALYTICS_ID", "UA-102484926-14")
    GOOGLE_TAG_MANAGER_ID = os.getenv("GOOGLE_TAG_MANAGER_ID", "GTM-KRKRZQV")
    HC_EN_SERVICE_ID = os.getenv("HC_EN_SERVICE_ID")
    HC_FR_SERVICE_ID = os.getenv("HC_FR_SERVICE_ID")
    HIPB_ENABLED = True
    HTTP_PROTOCOL = "http"
    INVITATION_EXPIRY_SECONDS = 3_600 * 24 * 2  # 2 days - also set on api
    IP_GEOLOCATE_SERVICE = os.environ.get("IP_GEOLOCATE_SERVICE", "").rstrip("/")
    LANGUAGES = ["en", "fr"]
    LOGO_UPLOAD_BUCKET_NAME = os.getenv("ASSET_UPLOAD_BUCKET_NAME", "notification-alpha-canada-ca-asset-upload")
    MAX_FAILED_LOGIN_COUNT = 10
    MOU_BUCKET_NAME = os.getenv("MOU_BUCKET_NAME", "")

    NOTIFY_APP_NAME = "admin"
    NOTIFY_BAD_FILLER_UUID = "00000000-0000-0000-0000-000000000000"
    NOTIFY_ENVIRONMENT = "development"
    NOTIFY_LOG_LEVEL = "DEBUG"
    NOTIFY_LOG_PATH = os.getenv("NOTIFY_LOG_PATH", "")

    NOTIFY_TEMPLATE_PREFILL_SERVICE_ID = "93305b36-b0a0-4a34-9ab2-c1b7bb5ca489"

    PERMANENT_SESSION_LIFETIME = 8 * 60 * 60  # 8 hours
    REDIS_ENABLED = env.bool("REDIS_ENABLED", False)
    REDIS_URL = os.environ.get("REDIS_URL")
    ROUTE_SECRET_KEY_1 = os.environ.get("ROUTE_SECRET_KEY_1", "")
    ROUTE_SECRET_KEY_2 = os.environ.get("ROUTE_SECRET_KEY_2", "")

    # Scan files integration
    SCANFILES_AUTH_TOKEN = os.environ.get("SCANFILES_AUTH_TOKEN", "")
    SCANFILES_URL = os.environ.get("SCANFILES_URL", "")

    SECRET_KEY = env.list("SECRET_KEY", [])
    SECURITY_EMAIL = os.environ.get("SECURITY_EMAIL", "security+securite@cds-snc.ca")
    SENDING_DOMAIN = os.environ.get("SENDING_DOMAIN", "notification.alpha.canada.ca")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_NAME = "notify_admin_session"
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = True
    SESSION_REFRESH_EACH_REQUEST = True
    SHOW_STYLEGUIDE = env.bool("SHOW_STYLEGUIDE", True)

    # Hosted graphite statsd prefix
    STATSD_HOST = os.getenv("STATSD_HOST")
    STATSD_ENABLED = bool(STATSD_HOST)
    STATSD_PORT = 8_125
    STATSD_PREFIX = os.getenv("STATSD_PREFIX")

    TEMPLATE_PREVIEW_API_HOST = os.environ.get("TEMPLATE_PREVIEW_API_HOST", "http://localhost:6013")
    TEMPLATE_PREVIEW_API_KEY = os.environ.get("TEMPLATE_PREVIEW_API_KEY", "my-secret-key")
    WAF_SECRET = os.environ.get("WAF_SECRET", "waf-secret")
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None
    ZENDESK_API_KEY = os.environ.get("ZENDESK_API_KEY")

    # Various IDs
    BULK_SEND_TEST_SERVICE_ID = os.getenv("BULK_SEND_TEST_SERVICE_ID")

    NOTIFY_USER_ID = "6af522d0-2915-4e52-83a3-3690455a5fe6"
    NOTIFY_SERVICE_ID = "d6aa2c68-a2d9-4437-ab19-3ae8eb202553"
    NO_BRANDING_ID = os.environ.get("NO_BRANDING_ID", "0af93cf1-2c49-485f-878f-f3e662e651ef")

    @classmethod
    def get_sensitive_config(cls) -> list[str]:
        "List of config keys that contain sensitive information"
        return [
            "ADMIN_CLIENT_SECRET",
            "ANTIVIRUS_API_KEY",
            "DANGEROUS_SALT",
            "DEBUG_KEY",
            "GC_ARTICLES_API_AUTH_PASSWORD",
            "GC_ARTICLES_API_AUTH_USERNAME",
            "ROUTE_SECRET_KEY_1",
            "ROUTE_SECRET_KEY_2",
            "SECRET_KEY",
            "TEMPLATE_PREVIEW_API_KEY",
            "WAF_SECRET",
            "ZENDESK_API_KEY",
        ]

    @classmethod
    def get_safe_config(cls) -> dict[str, Any]:
        "Returns a dict of config keys and values with sensitive values masked"
        return logging.get_class_attrs(cls, cls.get_sensitive_config())


class Development(Config):
    ADMIN_CLIENT_SECRET = os.environ.get("ADMIN_CLIENT_SECRET", "dev-notify-secret-key")
    ANTIVIRUS_API_HOST = "http://localhost:6016"
    ANTIVIRUS_API_KEY = "test-key"
    API_HOST_NAME = os.environ.get("API_HOST_NAME", "http://localhost:6011")
    DANGEROUS_SALT = os.environ.get("DANGEROUS_SALT", "dev-notify-salt")
    DEBUG = True
    DEBUG_KEY = "debug"
    MOU_BUCKET_NAME = "notify.tools-mou"
    REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    SECRET_KEY = env.list("SECRET_KEY", ["dev-notify-secret-key"])
    SESSION_COOKIE_SECURE = False
    SESSION_PROTECTION = None
    SYSTEM_STATUS_URL = "https://localhost:3000"
    NO_BRANDING_ID = "0af93cf1-2c49-485f-878f-f3e662e651ef"


class Test(Development):
    ADMIN_CLIENT_SECRET = os.environ.get("ADMIN_CLIENT_SECRET", "dev-notify-secret-key")
    ANTIVIRUS_API_HOST = "https://test-antivirus"
    ANTIVIRUS_API_KEY = "test-antivirus-secret"
    API_HOST_NAME = os.environ.get("API_HOST_NAME", "http://localhost:6011")
    ASSET_DOMAIN = "static.example.com"
    DANGEROUS_SALT = os.environ.get("DANGEROUS_SALT", "dev-notify-salt")
    DEBUG = True
    DEBUG_KEY = "debug"
    MOU_BUCKET_NAME = "test-mou"
    NOTIFY_ENVIRONMENT = "test"
    SECRET_KEY = ["dev-notify-secret-key"]
    TEMPLATE_PREVIEW_API_HOST = "http://localhost:9999"
    TEMPLATE_PREVIEW_API_KEY = "dev-notify-secret-key"
    TESTING = True
    WTF_CSRF_ENABLED = False
    GC_ARTICLES_API = "articles.alpha.canada.ca/notification-gc-notify"
    FF_SALESFORCE_CONTACT = False
    SYSTEM_STATUS_URL = "https://localhost:3000"
    NO_BRANDING_ID = "0af93cf1-2c49-485f-878f-f3e662e651ef"
    GC_ORGANISATIONS_BUCKET_NAME = "test-gc-organisations"
    FF_RTL = True
    FF_ANNUAL_LIMIT = True


class ProductionFF(Config):
    ADMIN_CLIENT_SECRET = os.environ.get("ADMIN_CLIENT_SECRET", "dev-notify-secret-key")
    ANTIVIRUS_API_HOST = "https://test-antivirus"
    ANTIVIRUS_API_KEY = "test-antivirus-secret"
    API_HOST_NAME = os.environ.get("API_HOST_NAME", "http://localhost:6011")
    ASSET_DOMAIN = "static.example.com"
    DANGEROUS_SALT = os.environ.get("DANGEROUS_SALT", "dev-notify-salt")
    DEBUG = True
    DEBUG_KEY = "debug"
    MOU_BUCKET_NAME = "test-mou"
    NOTIFY_ENVIRONMENT = "test"
    SECRET_KEY = ["dev-notify-secret-key"]
    TEMPLATE_PREVIEW_API_HOST = "http://localhost:9999"
    TEMPLATE_PREVIEW_API_KEY = "dev-notify-secret-key"
    TESTING = True
    WTF_CSRF_ENABLED = False
    GC_ARTICLES_API = "articles.alpha.canada.ca/notification-gc-notify"
    FF_SALESFORCE_CONTACT = False
    SYSTEM_STATUS_URL = "https://localhost:3000"
    NO_BRANDING_ID = "0af93cf1-2c49-485f-878f-f3e662e651ef"
    GC_ORGANISATIONS_BUCKET_NAME = "dev-gc-organisations"
    FF_RTL = False
    FF_ANNUAL_LIMIT = False


class Production(Config):
    CHECK_PROXY_HEADER = False
    HTTP_PROTOCOL = "https"
    NOTIFY_ENVIRONMENT = "production"
    NOTIFY_LOG_LEVEL = "INFO"
    SYSTEM_STATUS_URL = "https://status.notification.canada.ca"
    NO_BRANDING_ID = "760c802a-7762-4f71-b19e-f93c66c92f1a"


class Staging(Production):
    NOTIFY_ENVIRONMENT = "staging"
    NOTIFY_LOG_LEVEL = "INFO"
    SYSTEM_STATUS_URL = "https://status.staging.notification.cdssandbox.xyz"
    NO_BRANDING_ID = "0af93cf1-2c49-485f-878f-f3e662e651ef"


class Scratch(Production):
    NOTIFY_ENVIRONMENT = "scratch"
    NOTIFY_LOG_LEVEL = "INFO"


class Dev(Production):
    NOTIFY_ENVIRONMENT = "dev"
    NOTIFY_LOG_LEVEL = "INFO"


configs = {
    "development": Development,
    "test": Test,
    "staging": Staging,
    "production": Production,
    "production_FF": ProductionFF,
    "scratch": Scratch,
    "dev": Dev,
}
