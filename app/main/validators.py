import re
import time

import pwnedpasswords
import requests
import validators
from flask import current_app, g
from flask_babel import _
from flask_babel import lazy_gettext as _l
from notifications_utils.field import Field
from notifications_utils.recipients import InvalidEmailError, validate_email_address
from notifications_utils.sanitise_text import SanitiseSMS
from wtforms import ValidationError
from wtforms.validators import Email

from app import current_service, formatted_list, service_api_client
from app.main._blocked_passwords import blocked_passwords
from app.utils import Spreadsheet, email_safe, email_safe_name, is_gov_user


class Blocklist:
    def __init__(self, message=None):
        if not message:
            message = _("This password is not allowed. Try a different password.")
        self.message = message

    def __call__(self, form, field):
        if current_app.config.get("HIPB_ENABLED", None):
            hibp_bad_password_found = False
            # Try 3 times. If the HIPB API is down then fall back to the old banlist.
            for i in range(0, 3):
                try:
                    response = pwnedpasswords.check(field.data)
                    if response > 0:
                        hibp_bad_password_found = True
                        break
                    elif response == 0:
                        return

                except Exception:
                    time.sleep(0.5)
                    pass

            if hibp_bad_password_found:
                raise ValidationError(self.message)

        if field.data in blocked_passwords:
            raise ValidationError(self.message)


class CsvFileValidator:
    def __init__(self, message=_("Not a csv file")):
        self.message = message

    def __call__(self, form, field):
        if not Spreadsheet.can_handle(field.data.filename):
            raise ValidationError(
                "{} {}".format(
                    field.data.filename,
                    _("is not a spreadsheet that GC Notify can read"),
                )
            )


class ValidTeamMemberDomain:
    def __call__(self, form, field):
        if not field.data:
            return
        email_domain = field.data.split("@")[-1]
        # Merge domains from team members and safelisted domains, use set to ensure no duplicates
        safelisted_domains = set(current_app.config.get("REPLY_TO_DOMAINS_SAFELIST", set()))
        valid_domains = g.team_member_email_domains.union(safelisted_domains)

        if email_domain not in valid_domains:
            message = _(
                "{} is not an email domain used by team members of this service. Only email domains found in your team list can be used as an email reply-to: {}."
            ).format(email_domain, ", ".join(valid_domains))
            raise ValidationError(message)


class ValidGovEmail:
    def __call__(self, form, field):
        if not field.data:
            return

        # extract domain name from given email address

        domain = re.search(r"@(.*)$", field.data)

        if domain:
            domain = domain.group(1)
        else:
            domain = ""

        contact_text = _("contact us")
        message = _("{} is not on our list of government domains. If it’s a government email address, {}.").format(
            domain, contact_text
        )
        if not is_gov_user(field.data.lower()):
            raise ValidationError(message)


class ValidEmail(Email):
    def __init__(self):
        super().__init__(_l("Enter a valid email address"))

    def __call__(self, form, field):
        if not field.data:
            return

        try:
            validate_email_address(field.data)
        except InvalidEmailError:
            raise ValidationError(_l(self.message))


class NoCommasInPlaceHolders:
    def __init__(self, message=_("You cannot put commas between double brackets")):
        self.message = message

    def __call__(self, form, field):
        if "," in "".join(Field(field.data).placeholders):
            raise ValidationError(self.message)


class OnlySMSCharacters:
    def __call__(self, form, field):
        non_sms_characters = sorted(list(SanitiseSMS.get_non_compatible_characters(field.data)))
        if non_sms_characters:
            raise ValidationError(
                "You can’t use {} in text messages. {} won’t show up properly on everyone’s phones.".format(
                    formatted_list(
                        non_sms_characters,
                        conjunction="or",
                        before_each="",
                        after_each="",
                    ),
                    ("It" if len(non_sms_characters) == 1 else "They"),
                )
            )


class LettersNumbersAndFullStopsOnly:
    regex = re.compile(r"^[a-zA-Z0-9\s\.]+$")

    def __init__(self, message="Use letters and numbers only"):
        self.message = message

    def __call__(self, form, field):
        if field.data and not re.match(self.regex, field.data):
            raise ValidationError(self.message)


class DoesNotStartWithDoubleZero:
    def __init__(self, message="Can't start with 00"):
        self.message = message

    def __call__(self, form, field):
        if field.data and field.data.startswith("00"):
            raise ValidationError(self.message)


class ValidCallbackUrl:
    def __init__(self, message="Enter a URL that starts with https://"):
        self.message = message

    def __call__(self, form, field):
        if field.data:
            validate_callback_url(field.data, form.bearer_token.data)


def validate_callback_url(service_callback_url, bearer_token):
    """Validates a callback URL, checking that it is https and by sending a POST request to the URL with a health_check parameter.
    4xx responses are considered invalid. 5xx responses are considered valid as it indicates there is at least a service running
    at the URL, and we are sending a payload that the service will not understand.

    Args:
        service_callback_url (str): The url to validate.
        bearer_token (str): The bearer token to use in the request, specified by the user requesting callbacks.

    Raises:
        ValidationError: If the URL is not HTTPS or the http response is 4xx.
    """
    if not validators.url(service_callback_url):
        current_app.logger.warning(
            f"Unable to create callback for service: {current_service.id}. Error: Invalid callback URL format: URL: {service_callback_url}"
        )
        raise ValidationError(_l("Enter a URL that starts with https://"))

    try:
        response = requests.post(
            url=service_callback_url,
            allow_redirects=True,
            json={"health_check": True},
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {bearer_token}"},
            timeout=2,
        )

        g.callback_response_time = response.elapsed.total_seconds()

        if response.status_code < 500 and response.status_code >= 400:
            current_app.logger.warning(
                f"Unable to create callback for service: {current_service.id} Error: Callback URL not reachable URL: {service_callback_url}"
            )
            raise ValidationError(_l("Check your service is running and not using a proxy we cannot access"))

    except requests.RequestException as e:
        current_app.logger.warning(
            f"Unable to create callback for service: {current_service.id} Error: Callback URL not reachable URL: {service_callback_url} Exception: {e}"
        )
        raise ValidationError(_l("Check your service is running and not using a proxy we cannot access"))


def validate_email_from(form, field):
    if email_safe(field.data) != field.data.lower():
        # fix their data instead of only warning them
        field.data = email_safe(field.data)
    if len(field.data) > 64:
        raise ValidationError(_l("This cannot exceed 64 characters in length"))
    # this filler is used because service id is not available when validating a new service to be created
    service_id = getattr(form, "service_id", current_app.config["NOTIFY_BAD_FILLER_UUID"])
    unique_name = service_api_client.is_service_email_from_unique(service_id, field.data)
    if not unique_name:
        raise ValidationError(_l("This email address is already in use"))


def validate_service_name(form, field):
    if len(field.data) > 255:
        raise ValidationError(_l("This cannot exceed 255 characters in length"))
    if field.data != email_safe_name(field.data):
        raise ValidationError(_l("Make sure we formatted your email address correctly."))
    service_id = getattr(form, "service_id", current_app.config["NOTIFY_BAD_FILLER_UUID"])
    unique_name = service_api_client.is_service_name_unique(
        service_id,
        field.data,
    )
    if not unique_name:
        raise ValidationError(_l("This service name is already in use"))
