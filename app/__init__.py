import itertools
import os
import re
import secrets
import urllib
from datetime import datetime, timedelta, timezone
from numbers import Number
from time import monotonic
from urllib.parse import urljoin

import timeago
from flask import (
    Markup,
    current_app,
    flash,
    g,
    make_response,
    render_template,
    request,
    session,
)
from flask.globals import _request_ctx_stack  # type: ignore
from flask_babel import Babel, _
from flask_login import LoginManager, current_user
from flask_wtf import CSRFProtect
from flask_wtf.csrf import CSRFError
from itsdangerous import BadSignature
from notifications_python_client.errors import HTTPError
from notifications_utils import formatters, logging, request_helper
from notifications_utils.formatters import formatted_list
from notifications_utils.recipients import (
    InvalidPhoneError,
    format_phone_number_human_readable,
    validate_phone_number,
)
from notifications_utils.sanitise_text import SanitiseASCII
from notifications_utils.timezones import utc_string_to_aware_gmt_datetime
from user_agents import parse
from werkzeug.exceptions import HTTPException as WerkzeugHTTPException
from werkzeug.exceptions import abort
from werkzeug.local import LocalProxy

from app import proxy_fix
from app.articles.routing import gca_url_for
from app.asset_fingerprinter import asset_fingerprinter
from app.commands import setup_commands
from app.config import configs
from app.extensions import (
    antivirus_client,
    bounce_rate_client,
    cache,
    redis_client,
    statsd_client,
    zendesk_client,
)
from app.models.organisation import Organisation
from app.models.service import Service
from app.models.user import AnonymousUser, User
from app.monkeytype_config import MonkeytypeConfig
from app.navigation import (
    AdminNavigation,
    HeaderNavigation,
    MainNavigation,
    OrgNavigation,
)
from app.notify_client.api_key_api_client import api_key_api_client
from app.notify_client.billing_api_client import billing_api_client
from app.notify_client.complaint_api_client import complaint_api_client
from app.notify_client.email_branding_client import email_branding_client
from app.notify_client.events_api_client import events_api_client
from app.notify_client.inbound_number_client import inbound_number_client
from app.notify_client.invite_api_client import invite_api_client
from app.notify_client.job_api_client import job_api_client
from app.notify_client.letter_branding_client import letter_branding_client
from app.notify_client.letter_jobs_client import letter_jobs_client
from app.notify_client.notification_api_client import notification_api_client
from app.notify_client.org_invite_api_client import org_invite_api_client
from app.notify_client.organisations_api_client import organisations_client
from app.notify_client.platform_stats_api_client import platform_stats_api_client
from app.notify_client.provider_client import provider_client
from app.notify_client.service_api_client import service_api_client
from app.notify_client.status_api_client import status_api_client
from app.notify_client.support_api_client import support_api_client
from app.notify_client.template_api_prefill_client import template_api_prefill_client
from app.notify_client.template_category_api_client import template_category_api_client
from app.notify_client.template_folder_api_client import template_folder_api_client
from app.notify_client.template_statistics_api_client import template_statistics_client
from app.notify_client.user_api_client import user_api_client
from app.s3_client.s3_gc_organisations_client import get_gc_organisations
from app.scanfiles.scanfiles_api_client import scanfiles_api_client
from app.tou import EVENTS_KEY, show_tou_prompt
from app.utils import documentation_url, id_safe

login_manager = LoginManager()
csrf = CSRFProtect()

# The current service attached to the request stack.
current_service: Service = LocalProxy(lambda: g.current_service)  # type: ignore

# The current organisation attached to the request stack.
current_organisation: Organisation = LocalProxy(lambda: g.current_organisation)  # type: ignore

navigation = {
    "header_navigation": HeaderNavigation(),
    "admin_navigation": AdminNavigation(),
    "org_navigation": OrgNavigation(),
    "main_navigation": MainNavigation(),
}


def get_current_locale(application):
    requestLang = request.accept_languages.best_match(application.config["LANGUAGES"])
    if requestLang is None:
        requestLang = "en"

    if request.args.get("lang") and request.args.get("lang") in ["en", "fr"]:
        lang = request.args.get("lang")
    else:
        lang = session.get("userlang", requestLang)

    session["userlang"] = lang
    return lang


def create_app(application):
    setup_commands(application)

    notify_environment = os.environ["NOTIFY_ENVIRONMENT"]
    config = configs[notify_environment]

    application.config.from_object(config)
    asset_fingerprinter._cdn_domain = application.config["ASSET_DOMAIN"]
    asset_fingerprinter._asset_root = urljoin(application.config["ADMIN_BASE_URL"], application.config["ASSET_PATH"])

    application.config["BABEL_DEFAULT_LOCALE"] = "en"
    babel = Babel(application)

    @babel.localeselector
    def get_locale():
        return get_current_locale(application)

    init_app(application)

    for client in (
        # Gubbins
        csrf,
        login_manager,
        proxy_fix,
        request_helper,
        cache,
        # API clients
        api_key_api_client,
        billing_api_client,
        complaint_api_client,
        email_branding_client,
        events_api_client,
        inbound_number_client,
        invite_api_client,
        job_api_client,
        letter_branding_client,
        letter_jobs_client,
        notification_api_client,
        org_invite_api_client,
        organisations_client,
        platform_stats_api_client,
        provider_client,
        service_api_client,
        status_api_client,
        support_api_client,
        template_category_api_client,
        template_folder_api_client,
        template_statistics_client,
        template_api_prefill_client,
        user_api_client,
        # External API clients
        antivirus_client,
        statsd_client,
        zendesk_client,
        redis_client,
        bounce_rate_client,
    ):
        client.init_app(application)

    # pass the scanfiles url and token
    scanfiles_api_client.init_app(application.config["SCANFILES_URL"], application.config["SCANFILES_AUTH_TOKEN"])

    logging.init_app(application, statsd_client)

    # Log a warning message if Redis is not enabled
    if not application.config["REDIS_ENABLED"]:
        application.logger.warning(
            "Redis is not enabled. Some features may not be supported. "
            "If you want to enable Redis, look at REDIS_* config variables."
        )

    login_manager.login_view = "main.sign_in"
    login_manager.login_message_category = "default"
    login_manager.session_protection = None
    login_manager.anonymous_user = AnonymousUser

    # make sure we handle unicode correctly
    redis_client.redis_store.decode_responses = True

    # Log the application configuration
    application.logger.info(f"Notify config: {config.get_safe_config()}")

    from app.main import main as main_blueprint

    application.register_blueprint(main_blueprint)

    from .status import status as status_blueprint

    application.register_blueprint(status_blueprint)

    add_template_filters(application)

    register_errorhandlers(application)

    setup_event_handlers()

    # allow gca_url_for to be called from any template
    application.jinja_env.globals["gca_url_for"] = gca_url_for
    application.jinja_env.globals["current_service"] = current_service

    # cross-cutting concerns for TOU/login events
    application.jinja_env.globals["show_tou_prompt"] = show_tou_prompt
    application.jinja_env.globals["parse_ua"] = parse
    application.jinja_env.globals["events_key"] = EVENTS_KEY
    application.jinja_env.globals["now"] = datetime.utcnow

    # Initialize the GC Organisation list
    if application.config["FF_SALESFORCE_CONTACT"]:
        application.config["CRM_ORG_LIST"] = get_gc_organisations(application)

    # Specify packages to be traced by MonkeyType. This can be overriden
    # via the MONKEYTYPE_TRACE_MODULES environment variable. e.g:
    # MONKEYTYPE_TRACE_MODULES="app.,notifications_utils."
    if application.config["NOTIFY_ENVIRONMENT"] == "development":
        packages_prefix = ["app.", "notifications_utils."]
        application.monkeytype_config = MonkeytypeConfig(packages_prefix)


def init_app(application):
    application.after_request(useful_headers_after_request)
    application.after_request(save_service_or_org_after_request)
    application.before_request(load_service_before_request)
    application.before_request(load_organisation_before_request)
    application.before_request(request_helper.check_proxy_header_before_request)
    application.before_request(load_request_nonce)

    @application.before_request
    def make_session_permanent():
        # This is misleading. You'd think, given that there's `config['PERMANENT_SESSION_LIFETIME']`, that you'd enable
        # permanent sessions in the config too - but no, you have to declare it for each request.
        # https://stackoverflow.com/questions/34118093/flask-permanent-session-where-to-define-them
        # session.permanent is also, helpfully, a way of saying that the session isn't permanent - in that, it will
        # expire on its own, as opposed to being controlled by the browser's session. Because session is a proxy, it's
        # only accessible from within a request context, so we need to set this before every request.
        session.permanent = True

    @application.context_processor
    def _attach_current_service():
        return {"current_service": current_service}

    @application.context_processor
    def _attach_current_organisation():
        return {"current_org": current_organisation}

    @application.context_processor
    def _attach_current_user():
        return {"current_user": current_user}

    @application.context_processor
    def _nav_selected():
        return navigation

    @application.before_request
    def record_start_time():
        g.start = monotonic()
        g.endpoint = request.endpoint

    @application.context_processor
    def inject_global_template_variables():
        nonce = safe_get_request_nonce()
        current_app.logger.debug(f"Injecting nonce {nonce} in request")
        return {
            "admin_base_url": application.config["ADMIN_BASE_URL"],
            "asset_url": asset_fingerprinter.get_url,
            "sri_hash": asset_fingerprinter.get_sri,
            "asset_s3_url": asset_fingerprinter.get_s3_url,
            "current_lang": get_current_locale(application),
            "documentation_url": documentation_url,
            "google_analytics_id": application.config["GOOGLE_ANALYTICS_ID"],
            "google_tag_manager_id": application.config["GOOGLE_TAG_MANAGER_ID"],
            "request_nonce": nonce,
            "sending_domain": application.config["SENDING_DOMAIN"],
        }


def safe_get_request_nonce():
    # Using hasattr() won't work when digging into the request stack with
    # inexistent attribute as the request stack overrides the normal behavior
    # and will deviate from expected behavior.
    try:
        nonce = _request_ctx_stack.top.nonce
        current_app.logger.debug(f"Safe get request nonce of {nonce}.")
        return nonce
    except AttributeError:
        current_app.logger.warning("Request nonce could not be safely retrieved; returning empty string.")
        return ""


def linkable_name(value):
    return urllib.parse.quote_plus(value)


def format_number(number):
    lang = get_current_locale(current_app)

    if lang == "fr":
        # Spaces as separators
        return "{:,}".format(number).replace(",", "\xa0")  # \xa0: nbsp
    return "{:,}".format(number)  # Commas as separators


def format_datetime(date):
    return "{} at {}".format(format_date(date), format_time(date))


def format_datetime_24h(date):
    return "{} at {}".format(
        format_date(date),
        format_time_24h(date),
    )


def format_datetime_normal(date):
    return "{} at {}".format(format_date_normal(date), format_time(date))


def format_datetime_short(date):
    return "{} at {}".format(format_date_short(date), format_time(date))


def format_datetime_relative(date):
    return "{} at {}".format(get_human_day(date), format_time(date))


def format_datetime_numeric(date):
    return "{} {}".format(
        format_date_numeric(date),
        format_time_24h(date),
    )


def format_date_numeric(date):
    return utc_string_to_aware_gmt_datetime(date).strftime("%Y-%m-%d")


def format_time_24h(date):
    return utc_string_to_aware_gmt_datetime(date).strftime("%H:%M")


def get_human_day(time):
    #  Add 1 minute to transform 00:00 into ‘midnight today’ instead of ‘midnight tomorrow’
    date = (utc_string_to_aware_gmt_datetime(time) - timedelta(minutes=1)).date()
    if date == (datetime.utcnow() + timedelta(days=1)).date():
        return "tomorrow"
    if date == datetime.utcnow().date():
        return "today"
    if date == (datetime.utcnow() - timedelta(days=1)).date():
        return "yesterday"
    return _format_datetime_short(date)


def format_time(date):
    return {"12:00AM": "Midnight", "12:00PM": "Midday"}.get(
        utc_string_to_aware_gmt_datetime(date).strftime("%-I:%M%p"),
        utc_string_to_aware_gmt_datetime(date).strftime("%-I:%M%p"),
    ).lower()


def format_date(date):
    return utc_string_to_aware_gmt_datetime(date).strftime("%A %d %B %Y")


def format_date_normal(date):
    return utc_string_to_aware_gmt_datetime(date).strftime("%d %B %Y").lstrip("0")


def format_date_short(date):
    return _format_datetime_short(utc_string_to_aware_gmt_datetime(date))


def _format_datetime_short(datetime):
    return datetime.strftime("%d %B").lstrip("0")


def format_delta(_date):
    lang = get_current_locale(current_app)
    date = utc_string_to_aware_gmt_datetime(_date)
    now = datetime.now(timezone.utc)
    return timeago.format(date, now, lang)


def translate_preview_template(_template_str):
    def translate_brackets(x):
        match, word = x.group(0), x.group(1)
        return {
            "From": _("From"),
            "To": _("To"),
            "Subject": _("Subject"),
            "Reply to": _("Reply to"),
            "From:": _("From:"),
            "To:": _("To:"),
            "phone number": _("phone number"),
            "email address": _("email address"),
            "hidden": _("hidden"),
        }.get(word, match)

    # This regex finds words inside []
    template_str = re.sub(r"\[([^]]*)\]", translate_brackets, _template_str)
    return Markup(template_str)


def format_thousands(value):
    if isinstance(value, Number):
        return "{:,.0f}".format(float(value))
    if value is None:
        return ""
    return value


def valid_phone_number(phone_number):
    try:
        validate_phone_number(phone_number)
        return True
    except InvalidPhoneError:
        return False


def format_notification_type(notification_type):
    return {"email": "Email", "sms": "SMS", "letter": "Letter"}[notification_type]


def format_notification_status(status, template_type, provider_response=None, feedback_subtype=None):
    if template_type == "sms" and provider_response:
        return _(provider_response)

    def _getStatusByBounceSubtype():
        """Return the status of a notification based on the bounce sub type"""
        if feedback_subtype:
            return {
                "email": {
                    "suppressed": _("Blocked"),
                    "on-account-suppression-list": _("Blocked"),
                },
            }[template_type].get(feedback_subtype, _("No such address"))
        else:
            return _("No such address")

    return {
        "email": {
            "failed": _("Failed"),
            "technical-failure": _("Tech issue"),
            "temporary-failure": _("Content or inbox issue"),
            "virus-scan-failed": _("Virus in attachment"),
            "permanent-failure": _getStatusByBounceSubtype(),
            "delivered": _("Delivered"),
            "sending": _("In transit"),
            "created": _("In transit"),
            "sent": _("Delivered"),
            "pending": _("In transit"),
            "pending-virus-check": _("In transit"),
            "pii-check-failed": _("Exceeds Protected A"),
        },
        "sms": {
            "failed": _("Failed"),
            "technical-failure": _("Tech issue"),
            "temporary-failure": _("Carrier issue"),
            "permanent-failure": _("No such number"),
            "delivered": _("Delivered"),
            "sending": _("In transit"),
            "created": _("In transit"),
            "pending": _("In transit"),
            "sent": _("In transit"),
        },
        "letter": {
            "failed": "",
            "technical-failure": "Technical failure",
            "temporary-failure": "",
            "permanent-failure": "",
            "delivered": "",
            "received": "",
            "accepted": "",
            "sending": "",
            "created": "",
            "sent": "",
            "pending-virus-check": "",
            "virus-scan-failed": "Virus detected",
            "returned-letter": "",
            "cancelled": "",
            "validation-failed": "Validation failed",
        },
    }[template_type].get(status, status)


def format_notification_status_as_time(status, created, updated):
    return dict.fromkeys(
        {"created", "pending", "sending"},
        " " + _("since") + ' <time class="local-datetime-short">{}</time>'.format(created),
    ).get(status, '<time class="local-datetime-short">{}</time>'.format(updated))


def format_notification_status_as_field_status(status, notification_type):
    return {
        "letter": {
            "failed": "error",
            "technical-failure": "error",
            "temporary-failure": "error",
            "permanent-failure": "error",
            "delivered": None,
            "sent": None,
            "sending": None,
            "created": None,
            "accepted": None,
            "pending-virus-check": None,
            "virus-scan-failed": "error",
            "returned-letter": None,
            "cancelled": "error",
        }
    }.get(
        notification_type,
        {
            "failed": "error",
            "technical-failure": "error",
            "temporary-failure": "error",
            "permanent-failure": "error",
            "delivered": None,
            "sent": None,
            "sending": "default",
            "created": "default",
            "pending": "default",
        },
    ).get(status, "error")


def format_notification_status_as_url(status, notification_type):
    def url(_anchor):
        return gca_url_for("message_delivery_status") + "#" + _anchor

    if status not in {
        "technical-failure",
        "temporary-failure",
        "permanent-failure",
    }:
        return None

    return {
        "email": url(_anchor="email-statuses"),
        "sms": url(_anchor="sms-statuses"),
    }.get(notification_type)


def get_and_n_more_text(number_of_addresses):
    "number_of_addresses could be email addresses or sms sending numbers"
    number_of_hidden_addresses = number_of_addresses - 1
    if number_of_hidden_addresses < 1:
        # This should never happen - this function is not
        # called in this case.
        return _("…and 0 more")
    if number_of_hidden_addresses == 1:
        return _("…and 1 more")
    if number_of_hidden_addresses > 1:
        return _("…and {} more").format(number_of_hidden_addresses)


def nl2br(value):
    return formatters.nl2br(value) if value else ""


@login_manager.user_loader
def load_user(user_id):
    return User.from_id(user_id)


def load_service_before_request():
    g.current_service = None

    if "/static/" in request.url:
        return

    if request.view_args:
        service_id = request.view_args.get("service_id", session.get("service_id"))
    else:
        service_id = session.get("service_id")

    if service_id:
        try:
            g.current_service = Service.from_id(service_id)
        except HTTPError as exc:
            # if service id isn't real, then 404 rather than 500ing later because we expect service to be set
            if exc.status_code == 404:
                abort(404)
            else:
                raise


def load_organisation_before_request():
    g.current_organisation = None

    if "/static/" in request.url:
        return

    if request.view_args:
        org_id = request.view_args.get("org_id")

        if org_id:
            try:
                g.current_organisation = Organisation.from_id(org_id)
            except HTTPError as exc:
                # if org id isn't real, then 404 rather than 500ing later because we expect org to be set
                if exc.status_code == 404:
                    abort(404)
                else:
                    raise


def load_request_nonce():
    if "/static/" in request.url:
        _request_ctx_stack.top.nonce = None
    elif _request_ctx_stack.top is not None:
        token = secrets.token_urlsafe()
        _request_ctx_stack.top.nonce = token
        current_app.logger.debug(f"Set request nonce to {token}")


def save_service_or_org_after_request(response):
    # Only save the current session if the request is 200
    service_id = request.view_args.get("service_id", None) if request.view_args else None
    organisation_id = request.view_args.get("org_id", None) if request.view_args else None
    if response.status_code == 200:
        if service_id:
            session["service_id"] = service_id
            session["organisation_id"] = None
        elif organisation_id:
            session["service_id"] = None
            session["organisation_id"] = organisation_id
    return response


#  https://www.owasp.org/index.php/List_of_useful_HTTP_headers
def useful_headers_after_request(response):
    response.headers.add("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.add("Strict-Transport-Security", "max-age=63072000; includeSubDomains; preload")
    response.headers.add("X-Frame-Options", "deny")
    response.headers.add("X-Content-Type-Options", "nosniff")
    response.headers.add("X-XSS-Protection", "1; mode=block")
    response.headers.add("Upgrade-Insecure-Requests", "1")
    nonce = safe_get_request_nonce()
    asset_domain = current_app.config["ASSET_DOMAIN"]
    response.headers.add(
        "Report-To",
        """{"group":"default","max_age":1800,"endpoints":[{"url":"https://csp-report-to.security.cdssandbox.xyz/report"}]""",
    )
    response.headers.add(
        "Content-Security-Policy",
        (
            f"default-src 'self' {asset_domain} 'unsafe-inline';"
            f"script-src 'self' {asset_domain} *.google-analytics.com *.googletagmanager.com https://tagmanager.google.com https://js-agent.newrelic.com *.siteintercept.qualtrics.com https://siteintercept.qualtrics.com 'nonce-{nonce}' 'unsafe-eval' data:;"
            f"script-src-elem 'self' https://js-agent.newrelic.com *.siteintercept.qualtrics.com https://siteintercept.qualtrics.com 'nonce-{nonce}' 'unsafe-eval' data:;"
            "connect-src 'self' *.google-analytics.com *.googletagmanager.com https://bam.nr-data.net *.siteintercept.qualtrics.com https://siteintercept.qualtrics.com;"
            "object-src 'self';"
            f"style-src 'self' fonts.googleapis.com https://tagmanager.google.com https://fonts.googleapis.com 'unsafe-inline';"
            f"font-src 'self' {asset_domain} fonts.googleapis.com fonts.gstatic.com *.gstatic.com data:;"
            f"img-src 'self' blob: {asset_domain} *.canada.ca *.cdssandbox.xyz *.google-analytics.com *.googletagmanager.com *.notifications.service.gov.uk *.gstatic.com https://siteintercept.qualtrics.com data:;"  # noqa: E501
            "media-src 'self' *.alpha.canada.ca;"
            "frame-ancestors 'self';"
            "form-action 'self' *.siteintercept.qualtrics.com https://siteintercept.qualtrics.com;"
            "frame-src 'self' www.googletagmanager.com https://cdssnc.qualtrics.com/;"
            "report-uri https://csp-report-to.security.cdssandbox.xyz/report;"
            "report-to default;"
        ),
    )
    if "Cache-Control" in response.headers:
        del response.headers["Cache-Control"]
    # Cache static assets (CSS, JS, images) for a long time
    # as they have unique hashes thanks to the asset
    # fingerprinter
    if asset_fingerprinter.is_static_asset(request.url):
        response.headers.add("Cache-Control", "public, max-age=31536000, immutable")
    else:
        response.headers.add("Cache-Control", "no-store, no-cache, private, must-revalidate")
    for key, value in response.headers:
        response.headers[key] = SanitiseASCII.encode(value)
    return response


def register_errorhandlers(application):  # noqa (C901 too complex)
    def _error_response(error_code):
        resp = make_response(render_template("error/{0}.html".format(error_code)), error_code)
        return useful_headers_after_request(resp)

    @application.errorhandler(HTTPError)
    def render_http_error(error):
        application.logger.warning(
            "API {} failed with status {} message {}".format(
                error.response.url if error.response else "unknown",
                error.status_code,
                error.message,
            )
        )
        error_code = error.status_code
        if error_code == 400:
            # all incoming 400 errors from the API are wrapped for translation
            # Need to make sure all of them have translations in the csv files
            if isinstance(error.message, str):
                msg = [_(error.message)]
            else:
                msg = list(itertools.chain(_(error.message[x]) for x in error.message.keys()))

            resp = make_response(render_template("error/400.html", message=msg))
            return useful_headers_after_request(resp)
        elif error_code not in [401, 404, 403, 410]:
            # probably a 500 or 503
            application.logger.exception(
                "API {} failed with status {} message {}".format(
                    error.response.url if error.response else "unknown",
                    error.status_code,
                    error.message,
                )
            )
            error_code = 500
        return _error_response(error_code)

    @application.errorhandler(400)
    def handle_400(error):
        return _error_response(400)

    @application.errorhandler(410)
    def handle_gone(error):
        return _error_response(410)

    @application.errorhandler(413)
    def handle_payload_too_large(error):
        return _error_response(413)

    @application.errorhandler(404)
    def handle_not_found(error):
        return _error_response(404)

    @application.errorhandler(403)
    def handle_not_authorized(error):
        return _error_response(403)

    @application.errorhandler(401)
    def handle_no_permissions(error):
        return _error_response(401)

    @application.errorhandler(BadSignature)
    def handle_bad_token(error):
        # if someone has a malformed token
        flash(_("There’s something wrong with the link you’ve used."))
        return _error_response(404)

    @application.errorhandler(CSRFError)
    def handle_csrf(reason):
        application.logger.warning("csrf.error_message: {}".format(reason))

        if "user_id" not in session:
            application.logger.warning("csrf.session_expired: Redirecting user to log in page")

            return application.login_manager.unauthorized()

        application.logger.warning(
            "csrf.invalid_token: Aborting request, user_id: {user_id}",
            extra={"user_id": session["user_id"]},
        )

        resp = make_response(
            render_template(
                "error/400.html",
                message=["Something went wrong, please go back and try again."],
            ),
            400,
        )
        return useful_headers_after_request(resp)

    @application.errorhandler(405)
    def handle_405(error):
        resp = make_response(
            render_template(
                "error/400.html",
                message=["Something went wrong, please go back and try again."],
            ),
            405,
        )
        return useful_headers_after_request(resp)

    @application.errorhandler(WerkzeugHTTPException)
    def handle_http_error(error):
        if error.code == 301:
            # PermanentRedirect exception
            return error

        return _error_response(error.code)

    @application.errorhandler(500)
    @application.errorhandler(Exception)
    def handle_bad_request(error):
        current_app.logger.exception(error)
        # We want the Flask in browser stacktrace
        if current_app.config.get("DEBUG", None):
            raise error
        if "Detected newline in header value" in str(error):
            return _error_response(400)
        else:
            return _error_response(500)


def setup_event_handlers():
    from flask_login import user_logged_in

    from app.event_handlers import on_user_logged_in

    user_logged_in.connect(on_user_logged_in)


def add_template_filters(application):
    for fn in [
        format_number,
        format_datetime,
        format_datetime_24h,
        format_datetime_normal,
        format_datetime_short,
        format_time,
        valid_phone_number,
        linkable_name,
        format_date,
        format_date_normal,
        format_date_short,
        format_datetime_relative,
        format_delta,
        translate_preview_template,
        format_notification_status,
        format_notification_type,
        format_notification_status_as_time,
        format_notification_status_as_field_status,
        format_notification_status_as_url,
        formatted_list,
        get_and_n_more_text,
        nl2br,
        format_phone_number_human_readable,
        format_thousands,
        id_safe,
    ]:
        application.add_template_filter(fn)
