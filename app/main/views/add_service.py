import json
from abc import ABC
from typing import List, Text

from flask import current_app, redirect, render_template, request, session, url_for
from flask_babel import _
from notifications_python_client.errors import HTTPError

from app import billing_api_client, service_api_client
from app.main import main
from app.main.forms import (
    CreateServiceStepLogoForm,
    CreateServiceStepNameForm,
    CreateServiceStepFederalOrganisationForm,
    CreateServiceStepPtOrganisationForm,
    CreateServiceStepOrganisationTypeForm,
    CreateServiceStepOtherOrganisationForm,
    FieldWithLanguageOptions,
)
from app.utils import email_safe, user_is_gov_user, user_is_logged_in

# Constants

SESSION_FORM_KEY = "add_service_form"

DEFAULT_ORGANISATION_TYPE: str = "central"

STEP_NAME: str = "choose_service_name"
STEP_LOGO: str = "choose_logo"
STEP_ORGANISATION: str = "choose_organisation"
STEP_ORGANISATION_TYPE: str = "choose_organisation_type"

STEP_SERVICE_AND_EMAIL = STEP_NAME

STEP_NAME_HEADER: str = _("Create service name and email address")
STEP_LOGO_HEADER: str = _("Choose order for official languages")
STEP_ORGANISATION_HEADER: str = _("About your service")
STEP_ORGANISATION_TYPE_HEADER: str = _("About your service")

WIZARD_ORDER = [STEP_LOGO, STEP_SERVICE_AND_EMAIL, STEP_ORGANISATION_TYPE, STEP_ORGANISATION]

# wizard list init here for current_app context usage
WIZARD_DICT = {
    STEP_SERVICE_AND_EMAIL: {
        "form_cls": CreateServiceStepNameForm,
        "header": STEP_NAME_HEADER,
        "tmpl": "partials/add-service/step-create-service.html",
    },
    STEP_LOGO: {
        "form_cls": CreateServiceStepLogoForm,
        "header": STEP_LOGO_HEADER,
        "tmpl": "partials/add-service/step-choose-logo.html",
    },
    STEP_ORGANISATION_TYPE: {
        "form_cls": CreateServiceStepOrganisationTypeForm,
        "header": STEP_ORGANISATION_TYPE_HEADER,
        "tmpl": "partials/add-service/step-enter-organisation-type.html",
    },
    STEP_ORGANISATION: {
        "form_cls": "",
        "header": STEP_ORGANISATION_HEADER,
        "tmpl": "",
    },
}

ORGANISIATION_STEP_DICT = {
    "federal": {
        "tmpl": "partials/add-service/step-enter-federal-organisation.html",
        "form_cls": CreateServiceStepFederalOrganisationForm
    },
    "pt": {
        "tmpl": "partials/add-service/step-enter-pt-organisation.html",
        "form_cls": CreateServiceStepPtOrganisationForm
    },
    "other": {
        "tmpl": "partials/add-service/step-enter-other-organisation.html",
        "form_cls": CreateServiceStepOtherOrganisationForm
    }
}

# Utility classes
class ServiceResult(ABC):
    def __init__(self, errors: List[str] = []):
        self.errors = errors

    def is_success(self) -> bool:
        return not self.errors


class DuplicateNameResult(ServiceResult):
    def __init__(self, errors: List[str]):
        super().__init__(errors)


class SuccessResult(ServiceResult):
    def __init__(self, service_id: str):
        self.service_id = service_id
        super().__init__()


# Utility functions


def _create_service(
    service_name: str,
    organisation_type: str,
    email_from: str,
    default_branding_is_french: bool,
) -> ServiceResult:
    free_sms_fragment_limit = current_app.config["DEFAULT_FREE_SMS_FRAGMENT_LIMITS"].get(organisation_type)

    try:
        service_id = service_api_client.create_service(
            service_name=service_name,
            organisation_type=organisation_type,
            message_limit=current_app.config["DEFAULT_SERVICE_LIMIT"],
            sms_daily_limit=current_app.config["DEFAULT_SMS_DAILY_LIMIT"],
            restricted=True,
            user_id=session["user_id"],
            email_from=email_from,
            default_branding_is_french=default_branding_is_french,
        )
        session["service_id"] = service_id

        billing_api_client.create_or_update_free_sms_fragment_limit(service_id, free_sms_fragment_limit)

        return SuccessResult(service_id)
    except HTTPError as e:
        # TODO: Investigate typing issue
        if e.status_code == 400 and e.message["name"]:  # type: ignore
            errors = [_("This service name is already in use")]
            return DuplicateNameResult(errors)
        # TODO: Investigate typing issue
        if e.status_code == 400 and e.message["email_from"]:  # type: ignore
            errors = [_("This email address is already in use")]
            return DuplicateNameResult(errors)
        else:
            raise e


def get_form_class(current_step, government_type):
    if current_step == STEP_ORGANISATION:
        return ORGANISIATION_STEP_DICT[government_type]["form_cls"]
    return WIZARD_DICT[current_step]["form_cls"]


def get_form_template(current_step, government_type):
    government_type = government_type if government_type else "federal"
    if current_step == STEP_ORGANISATION:
        return ORGANISIATION_STEP_DICT[government_type]["tmpl"]
    return WIZARD_DICT[current_step]["tmpl"]


def _renderTemplateStep(form, current_step, government_type) -> Text:
    back_link = None
    step_num = WIZARD_ORDER.index(current_step) + 1
    autocomplete_items = {
        "en": json.load(open("app/assets/data/departments-agencies-en.json", "r")),
        "fr": json.load(open("app/assets/data/departments-agencies-fr.json", "r")),
    }
    if step_num > 1:
        back_link = url_for(".add_service", current_step=WIZARD_ORDER[step_num - 2])
    
    tmpl = get_form_template(current_step, government_type)
    return render_template(
        "views/add-service.html",
        form=form,
        heading=_(WIZARD_DICT[current_step]["header"]),
        step_num=step_num,
        step_max=len(WIZARD_ORDER),
        tmpl=tmpl,
        back_link=back_link,
        autocomplete_items=autocomplete_items,
    )


@main.route("/add-service", methods=["GET", "POST"])
@user_is_logged_in
@user_is_gov_user
def add_service():
    current_step = request.args.get("current_step", None)
    government_type = request.args.get("government_type", None)

    current_step_is_junk = False
    # if nothing supplied or bad data in the querystring, step_logo is first
    if not current_step or current_step not in WIZARD_ORDER:
        current_step_is_junk = current_step is not None and current_step not in WIZARD_ORDER
        current_step = STEP_LOGO

    # init session
    if SESSION_FORM_KEY not in session:
        session[SESSION_FORM_KEY] = {}
    # get the right form class
    form_cls = get_form_class(current_step, government_type)

    # as the form always does a 302 after success, GET is a fresh form with possible re-use of session data i.e. Back
    if request.method == "GET" or current_step_is_junk or len(request.form) == 0:
        return _renderTemplateStep(form_cls(data=session[SESSION_FORM_KEY]), current_step, government_type)
    if current_step == STEP_LOGO and len(request.form) > 0 and "default_branding" not in request.form:
        return _renderTemplateStep(form_cls(data=session[SESSION_FORM_KEY]), current_step, government_type)
    # must be a POST, continue to validate
    form = form_cls(request.form)
    if not form.validate_on_submit():
        # invalid form, re-render with validation response
        return _renderTemplateStep(form, current_step, government_type)
    # valid form, save data and move on or finalize
    # get the current place in the wizard based on ordering
    idx = WIZARD_ORDER.index(current_step)
    if idx < len(WIZARD_ORDER) - 1:
        # more steps to go, save valid submitted data to session and redirct to next form
        current_step = WIZARD_ORDER[idx + 1]
        session[SESSION_FORM_KEY].update(form.data)
        if idx == len(WIZARD_ORDER) - 2:
            government_type = form.data["government_type"]
        return redirect(url_for(".add_service", current_step=current_step, government_type=government_type))
    # no more steps left, re-validate validate session in case of stale session data
    data = session[SESSION_FORM_KEY]
    data.update(form.data)  # add newly submitted data from POST
    # iterate through all forms and validate
    for step in WIZARD_ORDER:
        temp_form_cls = get_form_class(current_step, government_type)
        temp_form = temp_form_cls(data=data)
        if not temp_form.validate():  # something isn't right, jump to the form with bad / missing data
            return redirect(url_for(".add_service", current_step=step, government_type=government_type))

    # all forms valid from session data, time to transact
    email_from = email_safe(data["email_from"])
    service_name = data["name"]
    default_branding_is_french = data["default_branding"] == FieldWithLanguageOptions.FRENCH_OPTION_VALUE
    service_result: ServiceResult = _create_service(
        service_name,
        DEFAULT_ORGANISATION_TYPE,
        email_from,
        default_branding_is_french,
    )

    # clear session after API POST
    session.pop(SESSION_FORM_KEY, None)

    if service_result.is_success():
        return redirect(url_for("main.service_dashboard", service_id=service_result.service_id))
    form_cls = get_form_class(current_step, government_type)
    form = form_cls(request.form)
    session[SESSION_FORM_KEY] = form.data
    if isinstance(service_result, DuplicateNameResult):
        form.validate()  # Necessary to make the `errors` field mutable!
        form.name.errors.append(_("This service name is already in use"))
    return _renderTemplateStep(form, current_step, government_type)
