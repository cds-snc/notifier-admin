import csv
import os
import random
import re
import unicodedata
import uuid
from collections import defaultdict
from datetime import datetime, time, timedelta
from functools import wraps
from io import BytesIO, StringIO
from itertools import chain
from os import path
from typing import Any

import boto3
import dateutil
import pyexcel
import pyexcel_xlsx
import requests
from dateutil import parser
from flask import abort, current_app, json, redirect, request, session, url_for
from flask_babel import _
from flask_babel import lazy_gettext as _l
from flask_login import current_user, login_required
from notifications_utils.field import Field
from notifications_utils.formatters import make_quotes_smart
from notifications_utils.letter_timings import letter_can_be_cancelled
from notifications_utils.recipients import RecipientCSV
from notifications_utils.strftime_codes import no_pad_month
from notifications_utils.take import Take
from notifications_utils.template import (
    EmailPreviewTemplate,
    LetterImageTemplate,
    LetterPreviewTemplate,
    SMSPreviewTemplate,
)
from notifications_utils.timezones import (
    convert_utc_to_est,
    utc_string_to_aware_gmt_datetime,
)
from orderedset._orderedset import OrderedSet
from werkzeug.datastructures import MultiDict
from werkzeug.routing import RequestRedirect

from app import cache
from app.notify_client.organisations_api_client import organisations_client
from app.notify_client.service_api_client import service_api_client

SENDING_STATUSES = ["created", "pending", "sending", "pending-virus-check"]
DELIVERED_STATUSES = ["delivered", "sent", "returned-letter"]
FAILURE_STATUSES = [
    "failed",
    "temporary-failure",
    "permanent-failure",
    "technical-failure",
    "virus-scan-failed",
    "validation-failed",
]
REQUESTED_STATUSES = SENDING_STATUSES + DELIVERED_STATUSES + FAILURE_STATUSES

with open("{}/email_domains.txt".format(os.path.dirname(os.path.realpath(__file__)))) as email_domains:
    GOVERNMENT_EMAIL_DOMAIN_NAMES = [line.strip() for line in email_domains]


user_is_logged_in = login_required


def from_lambda_api(line):
    """
    We need to detect if we are connected to the lambda api rather than the k8s api,
    since some response data is different
    """
    return isinstance(line, dict)


@cache.memoize(timeout=3600)
def get_latest_stats(lang):
    results = service_api_client.get_stats_by_month()["data"]

    monthly_stats = {}
    emails_total = 0
    sms_total = 0
    for line in results:
        if from_lambda_api(line):
            date = line["month"]
            notification_type = line["notification_type"]
            count = line["count"]
        else:
            date, notification_type, count = line
        year = date[:4]
        year_month = date[:7]
        month = f"{get_month_name(date)} {year}"
        if month not in monthly_stats:
            monthly_stats[month] = defaultdict(int)
        monthly_stats[month][notification_type] = count
        monthly_stats[month]["total"] += count
        monthly_stats[month]["year_month"] = year_month

        if notification_type == "sms":
            sms_total += count
        elif notification_type == "email":
            emails_total += count

    live_services = len(service_api_client.get_live_services_data()["data"])

    return {
        "monthly_stats": monthly_stats,
        "emails_total": emails_total,
        "sms_total": sms_total,
        "notifications_total": sms_total + emails_total,
        "live_services": live_services,
    }


def user_has_permissions(*permissions, **permission_kwargs):
    def wrap(func):
        @wraps(func)
        def wrap_func(*args, **kwargs):
            if not current_user.is_authenticated:
                return current_app.login_manager.unauthorized()
            if not current_user.has_permissions(*permissions, **permission_kwargs):
                abort(403)
            return func(*args, **kwargs)

        return wrap_func

    return wrap


def user_is_gov_user(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return current_app.login_manager.unauthorized()
        if not current_user.is_gov_user:
            abort(403)
        return f(*args, **kwargs)

    return wrapped


def user_is_platform_admin(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return current_app.login_manager.unauthorized()
        if not current_user.platform_admin:
            abort(403)
        return f(*args, **kwargs)

    return wrapped


def redirect_to_sign_in(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if "user_details" not in session:
            return redirect(url_for("main.sign_in"))
        else:
            return f(*args, **kwargs)

    return wrapped


def get_errors_for_csv(recipients, template_type):

    errors = []

    if any(recipients.rows_with_bad_recipients):
        number_of_bad_recipients = len(list(recipients.rows_with_bad_recipients))
        if "sms" == template_type:
            if 1 == number_of_bad_recipients:
                errors.append(_("fix") + " 1 " + _("phone number"))
            else:
                errors.append(_("fix") + " {} ".format(number_of_bad_recipients) + _("phone numbers"))
        elif "email" == template_type:
            if 1 == number_of_bad_recipients:
                errors.append(_("fix") + " 1 " + _("email address"))
            else:
                errors.append(_("fix") + " {} ".format(number_of_bad_recipients) + _("email addresses"))
        elif "letter" == template_type:
            if 1 == number_of_bad_recipients:
                errors.append(_("fix") + " 1 " + _("address"))
            else:
                errors.append(_("fix") + " {} ".format(number_of_bad_recipients) + _("addresses"))

    if any(recipients.rows_with_missing_data):
        number_of_rows_with_missing_data = len(list(recipients.rows_with_missing_data))
        if 1 == number_of_rows_with_missing_data:
            errors.append(_("enter missing data in 1 row"))
        else:
            errors.append(_("enter missing data in {} rows").format(number_of_rows_with_missing_data))

    return errors


def generate_notifications_csv(**kwargs):
    from app import notification_api_client
    from app.s3_client.s3_csv_client import s3download

    if "page" not in kwargs:
        kwargs["page"] = 1

    if kwargs.get("job_id"):
        original_file_contents = s3download(kwargs["service_id"], kwargs["job_id"])
        original_upload = RecipientCSV(
            original_file_contents,
            template_type=kwargs["template_type"],
        )
        original_column_headers = original_upload.column_headers
        fieldnames = ["Row number"] + original_column_headers + ["Template", "Type", "Job", "Status", "Time"]
    else:
        fieldnames = [
            "Recipient",
            "Template",
            "Type",
            "Sent by",
            "Sent by email",
            "Job",
            "Status",
            "Time",
        ]

    yield ",".join(fieldnames) + "\n"

    while kwargs["page"]:
        notifications_resp = notification_api_client.get_notifications_for_service(**kwargs)
        for notification in notifications_resp["notifications"]:
            if kwargs.get("job_id"):
                values = (
                    [
                        notification["row_number"],
                    ]
                    + [original_upload[notification["row_number"] - 1].get(header).data for header in original_column_headers]
                    + [
                        notification["template_name"],
                        notification["template_type"],
                        notification["job_name"],
                        notification["status"],
                        notification["created_at"],
                    ]
                )
            else:
                values = [
                    notification["recipient"],
                    notification["template_name"],
                    notification["template_type"],
                    notification["created_by_name"] or "",
                    notification["created_by_email_address"] or "",
                    notification["job_name"] or "",
                    notification["status"],
                    notification["created_at"],
                ]
            yield Spreadsheet.from_rows([map(str, values)]).as_csv_data

        if notifications_resp["links"].get("next"):
            kwargs["page"] += 1
        else:
            return
    raise Exception("Should never reach here")


def get_page_from_request():
    if "page" in request.args:
        try:
            return int(request.args["page"])
        except ValueError:
            return None
    else:
        return 1


def generate_previous_dict(view, service_id, page, url_args=None):
    return generate_previous_next_dict(view, service_id, page - 1, "Previous page", url_args or {})


def generate_next_dict(view, service_id, page, url_args=None):
    return generate_previous_next_dict(view, service_id, page + 1, "Next page", url_args or {})


def generate_previous_next_dict(view, service_id, page, title, url_args):
    return {
        "url": url_for(view, service_id=service_id, page=page, **url_args),
        "title": title,
        "label": "page {}".format(page),
    }


def email_safe(string, whitespace="."):
    # strips accents, diacritics etc
    string = "".join(c for c in unicodedata.normalize("NFD", string) if unicodedata.category(c) != "Mn")
    string = "".join(
        word.lower() if word.isalnum() or word in [whitespace, "-", "_"] else ""
        for word in re.sub(r"\s+", whitespace, string.strip())
    )
    string = re.sub(r"\.{2,}", ".", string)
    # Replace a sequence like ".-." or "._." to "-""
    string = re.sub(r"(\.)(-|_)(\.)", r"\g<2>", string)
    # Disallow to repeat - _ or .
    string = re.sub(r"(\.|-|_){2,}", r"\g<1>", string)
    return string.strip(".")


def email_safe_name(string):
    return string.replace('"', "").strip()


def id_safe(string):
    return email_safe(string, whitespace="-")


def get_remote_addr(request):
    try:
        return request.access_route[0]
    # This except block is here to prevent to fail when the env `REMOTE_ADDR`
    # is not set. This only happens when running tests
    except IndexError:
        return None


class Spreadsheet:

    allowed_file_extensions = ["csv", "xlsx", "xls", "ods", "xlsm", "tsv"]

    def __init__(self, csv_data=None, rows=None, filename=""):

        self.filename = filename

        if csv_data and rows:
            raise TypeError("Spreadsheet must be created from either rows or CSV data")

        self._csv_data = csv_data or ""
        self._rows = rows or []

    @property
    def as_dict(self):
        return {"file_name": self.filename, "data": self.as_csv_data}

    @property
    def as_csv_data(self):
        if not self._csv_data:
            with StringIO() as converted:
                output = csv.writer(converted)
                for row in self._rows:
                    output.writerow(row)
                self._csv_data = converted.getvalue()
        return self._csv_data

    @classmethod
    def can_handle(cls, filename):
        return cls.get_extension(filename) in cls.allowed_file_extensions

    @staticmethod
    def get_extension(filename):
        return path.splitext(filename)[1].lower().lstrip(".")

    @staticmethod
    def normalise_newlines(file_content):
        return "\r\n".join(file_content.read().decode("utf-8").splitlines())

    @classmethod
    def from_rows(cls, rows, filename=""):
        return cls(rows=rows, filename=filename)

    @classmethod
    def from_dict(cls, dictionary, filename=""):
        return cls.from_rows(
            zip(*sorted(dictionary.items(), key=lambda pair: pair[0])),
            filename=filename,
        )

    @classmethod
    def from_file(cls, file_content, filename=""):
        extension = cls.get_extension(filename)

        if extension == "csv":
            return cls(csv_data=Spreadsheet.normalise_newlines(file_content), filename=filename)

        if extension == "tsv":
            file_content = StringIO(Spreadsheet.normalise_newlines(file_content))

        instance = cls.from_rows(pyexcel.iget_array(file_type=extension, file_stream=file_content), filename)
        pyexcel.free_resources()
        return instance

    @property
    def as_rows(self):
        if not self._rows:
            self._rows = list(
                csv.reader(
                    StringIO(self._csv_data),
                    quoting=csv.QUOTE_MINIMAL,
                    skipinitialspace=True,
                )
            )
        return self._rows

    @property
    def as_excel_file(self):
        io = BytesIO()
        pyexcel_xlsx.save_data(io, {"Sheet 1": self.as_rows})
        return io.getvalue()


def get_help_argument():
    return request.args.get("help") if request.args.get("help") in ("1", "2", "3") else None


def email_address_ends_with(email_address, known_domains):
    return any(
        email_address.lower().endswith(
            (
                "@{}".format(known),
                ".{}".format(known),
            )
        )
        for known in known_domains
    )


def is_gov_user(email_address):
    return email_address_ends_with(email_address, GOVERNMENT_EMAIL_DOMAIN_NAMES) or email_address_ends_with(
        email_address, organisations_client.get_domains()
    )


def get_template(
    template,
    service,
    show_recipient=False,
    letter_preview_url=None,
    page_count=1,
    redact_missing_personalisation=False,
    email_reply_to=None,
    sms_sender=None,
):
    # Local Jinja support - add USE_LOCAL_JINJA_TEMPLATES=True to .env
    # Add a folder to the project root called 'jinja_templates' with copies from notification-utls repo of:
    # 'email_preview_template.jinja2'
    # 'sms_preview_template.jinja2'
    debug_template_path = path.dirname(path.abspath(__file__)) if os.environ.get("USE_LOCAL_JINJA_TEMPLATES") == "True" else None

    if "email" == template["template_type"]:
        return EmailPreviewTemplate(
            template,
            from_name=service.name,
            from_address="{}@notifications.service.gov.uk".format(service.email_from),
            show_recipient=show_recipient,
            redact_missing_personalisation=redact_missing_personalisation,
            reply_to=email_reply_to,
            jinja_path=debug_template_path,
            allow_html=(service.id in current_app.config["ALLOW_HTML_SERVICE_IDS"]),
            **get_email_logo_options(service),
        )
    if "sms" == template["template_type"]:
        return SMSPreviewTemplate(
            template,
            prefix=service.name,
            show_prefix=service.prefix_sms,
            sender=sms_sender,
            show_sender=bool(sms_sender),
            show_recipient=show_recipient,
            redact_missing_personalisation=redact_missing_personalisation,
            jinja_path=debug_template_path,
        )
    if "letter" == template["template_type"]:
        if letter_preview_url:
            return LetterImageTemplate(
                template,
                image_url=letter_preview_url,
                page_count=int(page_count),
                contact_block=template["reply_to_text"],
                postage=template["postage"],
            )
        else:
            return LetterPreviewTemplate(
                template,
                contact_block=template["reply_to_text"],
                admin_base_url=current_app.config["ADMIN_BASE_URL"],
                redact_missing_personalisation=redact_missing_personalisation,
            )


def get_email_logo_options(service):
    email_branding = service.email_branding
    if email_branding is None:
        return {
            "asset_domain": get_logo_cdn_domain(),
            "fip_banner_english": not service.default_branding_is_french,
            "fip_banner_french": service.default_branding_is_french,
        }

    return {
        "asset_domain": get_logo_cdn_domain(),
        "brand_colour": email_branding["colour"],
        "brand_logo": email_branding["logo"],
        "brand_text": email_branding["text"],
        "brand_name": email_branding["name"],
    }


def get_current_financial_year():
    now = datetime.utcnow()
    current_month = int(now.strftime(no_pad_month()))
    current_year = int(now.strftime("%Y"))
    return current_year if current_month > 3 else current_year - 1


def get_available_until_date(created_at, service_data_retention_days=7):
    created_at_date = dateutil.parser.parse(created_at).replace(hour=0, minute=0, second=0)
    return created_at_date + timedelta(days=service_data_retention_days + 1)


def email_or_sms_not_enabled(template_type, permissions):
    return (template_type in ["email", "sms"]) and (template_type not in permissions)


def get_logo_cdn_domain():
    return current_app.config["ASSET_DOMAIN"]


def parse_filter_args(filter_dict):
    if not isinstance(filter_dict, MultiDict):
        filter_dict = MultiDict(filter_dict)

    return MultiDict(
        (key, (",".join(filter_dict.getlist(key))).split(",")) for key in filter_dict.keys() if "".join(filter_dict.getlist(key))
    )


def set_status_filters(filter_args):
    status_filters = filter_args.get("status", [])
    return list(
        OrderedSet(
            chain(
                (status_filters or REQUESTED_STATUSES),
                DELIVERED_STATUSES if "delivered" in status_filters else [],
                SENDING_STATUSES if "sending" in status_filters else [],
                FAILURE_STATUSES if "failed" in status_filters else [],
            )
        )
    )


def unicode_truncate(s, length):
    encoded = s.encode("utf-8")[:length]
    return encoded.decode("utf-8", "ignore")


def starts_with_initial(name):
    return bool(re.match(r"^.\.", name))


def remove_middle_initial(name):
    return re.sub(r"\s+.\s+", " ", name)


def remove_digits(name):
    return "".join(c for c in name if not c.isdigit())


def normalize_spaces(name):
    return " ".join(name.split())


def guess_name_from_email_address(email_address):

    possible_name = re.split(r"[\@\+]", email_address)[0]

    if "." not in possible_name or starts_with_initial(possible_name):
        return ""

    return (
        Take(possible_name)
        .then(str.replace, ".", " ")
        .then(remove_digits)
        .then(remove_middle_initial)
        .then(str.title)
        .then(make_quotes_smart)
        .then(normalize_spaces)
    )


def should_skip_template_page(template_type):
    return (
        current_user.has_permissions("send_messages")
        and not current_user.has_permissions("manage_templates", "manage_api_keys")
        and template_type != "letter"
    )


def get_default_sms_sender(sms_senders):
    return str(
        next(
            (Field(x["sms_sender"], html="escape") for x in sms_senders if x["is_default"]),
            "None",
        )
    )


def printing_today_or_tomorrow():
    now_utc = datetime.utcnow()
    now_est = convert_utc_to_est(now_utc)

    if now_est.time() < time(17, 30):
        return "today"
    else:
        return "tomorrow"


def redact_mobile_number(mobile_number, spacing=""):
    indices = [-4, -5, -6, -7]
    redact_character = spacing + "•" + spacing
    mobile_number_list = list(mobile_number.replace(" ", ""))
    for i in indices:
        mobile_number_list[i] = redact_character
    return "".join(mobile_number_list)


def get_letter_printing_statement(status, created_at):
    created_at_dt = parser.parse(created_at).replace(tzinfo=None)
    if letter_can_be_cancelled(status, created_at_dt):
        return "Printing starts {} at 5:30pm".format(printing_today_or_tomorrow())
    else:
        printed_datetime = utc_string_to_aware_gmt_datetime(created_at) + timedelta(hours=6, minutes=30)
        if printed_datetime.date() == datetime.now().date():
            return "Printed today at 5:30pm"
        elif printed_datetime.date() == datetime.now().date() - timedelta(days=1):
            return "Printed yesterday at 5:30pm"

        printed_date = printed_datetime.strftime("%d %B").lstrip("0")

        return "Printed on {} at 5:30pm".format(printed_date)


def report_security_finding(
    title,
    finding,
    criticality,
    severity,
    url="",
    types=["Unusual Behaviors"],
    UserDefinedFields={"app": "NotifyAdmin"},
):
    client = boto3.client("sts")
    response = client.get_caller_identity()

    account = response["Account"]

    product = f'arn:aws:securityhub:{current_app.config["AWS_REGION"].lower()}:{account}:product/{account}/default'
    client = boto3.client("securityhub", region_name=current_app.config["AWS_REGION"].lower())
    client.batch_import_findings(
        Findings=[
            {
                "SchemaVersion": "2018-10-08",
                "Id": str(uuid.uuid4()),
                "ProductArn": product,
                "GeneratorId": "NotifyAdminFinding",
                "AwsAccountId": account,
                "Types": types,
                "CreatedAt": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "UpdatedAt": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "FirstObservedAt": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "Severity": {"Normalized": severity},
                "Criticality": criticality,
                "Title": title,
                "Description": finding,
                "SourceUrl": url,
                "Resources": [
                    {
                        "Type": "Container",
                        "Id": os.getenv("HOST", "localhost"),
                        "Partition": "aws",
                        "Region": current_app.config["AWS_REGION"].lower(),
                        "Details": {
                            "Container": {
                                "Name": os.getenv("HOST", "localhost"),
                                "ImageName": "notify/admin",
                            },
                        },
                    },
                ],
                "VerificationState": "UNKNOWN",
                "WorkflowState": "NEW",
                "RecordState": "ACTIVE",
                "UserDefinedFields": UserDefinedFields,
            },
        ]
    )


def get_month_name(string):
    monthNumber = yyyy_mm_to_datetime(string).strftime(no_pad_month())
    translatedMonth = {
        1: _l("January"),
        2: _l("February"),
        3: _l("March"),
        4: _l("April"),
        5: _l("May"),
        6: _l("June"),
        7: _l("July"),
        8: _l("August"),
        9: _l("September"),
        10: _l("October"),
        11: _l("November"),
        12: _l("December"),
    }

    return translatedMonth.get(int(monthNumber), _l("Invalid month"))


def yyyy_mm_to_datetime(string):
    return datetime(int(string[0:4]), int(string[5:7]), 1)


def documentation_url(feature=None, section=None):
    from app import get_current_locale

    mapping = {
        "start": {"en": "start", "fr": "commencer"},
        "send": {"en": "send", "fr": "envoyer"},
        "status": {"en": "status", "fr": "etat"},
        "testing": {"en": "testing", "fr": "essai"},
        "keys": {"en": "keys", "fr": "cles"},
        "limits": {"en": "limits", "fr": "limites"},
        "callbacks": {"en": "callbacks", "fr": "rappel"},
        "architecture": {"en": "architecture", "fr": "architecture"},
        "clients": {"en": "clients", "fr": "clients"},
    }

    sections = {
        "send": {
            "sending-a-file-by-email": {
                "en": "sending-a-file-by-email",
                "fr": "envoyer-un-fichier-par-courriel",
            }
        }
    }

    lang = get_current_locale(current_app)
    base_domain = current_app.config["DOCUMENTATION_DOMAIN"]

    if feature is None:
        return f"https://{base_domain}/{lang}/"

    page = mapping[feature][lang]
    query_hash = ""
    if section:
        query_hash = f"#{sections[feature][section][lang]}"
    return f"https://{base_domain}/{lang}/{page}.html{query_hash}"


class PermanentRedirect(RequestRedirect):
    """
    In Werkzeug 0.15.0 the status code for RequestRedirect changed from 301 to 308.
    308 status codes are not supported when Internet Explorer is used with Windows 7
    and Windows 8.1, so this class keeps the original status code of 301.
    """

    code = 301


def is_blank(content: Any) -> bool:
    content = str(content)
    return not content or content.isspace()


def request_content(endpoint: str, params={"slug": "", "lang": "en"}) -> str:
    base_endpoint = current_app.config["GC_ARTICLES_API"]
    params["bust_cache"] = random.random()
    lang_endpoint = ""

    if params["lang"] == "fr":
        lang_endpoint = "/fr"

    response = requests.get(f"https://{base_endpoint}{lang_endpoint}/wp-json/{endpoint}", params)
    if response:
        parsed = json.loads(response.content)
        cache.set(params['slug'], parsed)
        return parsed
    else:
        return cache.get(params['slug']) or ""
