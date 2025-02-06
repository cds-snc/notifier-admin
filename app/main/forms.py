import weakref
from datetime import datetime, timedelta
from itertools import chain

import pytz
from flask import request
from flask_babel import lazy_gettext as _l
from flask_wtf import FlaskForm as Form
from flask_wtf.file import FileAllowed
from flask_wtf.file import FileField as FileField_wtf
from notifications_utils.columns import Columns
from notifications_utils.formatters import strip_whitespace
from notifications_utils.recipients import InvalidPhoneError, validate_phone_number
from notifications_utils.strftime_codes import no_pad_hour12, no_pad_hour24
from wtforms import (
    BooleanField,
    DateField,
    FieldList,
    FileField,
    HiddenField,
    IntegerField,
    PasswordField,
    SelectField,
    SelectMultipleField,
    StringField,
    SubmitField,
    TextAreaField,
    ValidationError,
    validators,
    widgets,
)
from wtforms import RadioField as WTFormsRadioField
from wtforms.fields import EmailField, SearchField, TelField
from wtforms.validators import (
    URL,
    AnyOf,
    DataRequired,
    InputRequired,
    Length,
    Optional,
    Regexp,
)
from wtforms.widgets import CheckboxInput, ListWidget

from app import format_thousands
from app.main.validators import (
    Blocklist,
    CsvFileValidator,
    DoesNotStartWithDoubleZero,
    LettersNumbersAndFullStopsOnly,
    NoCommasInPlaceHolders,
    OnlySMSCharacters,
    ValidCallbackUrl,
    ValidEmail,
    ValidGovEmail,
    ValidTeamMemberDomain,
    validate_email_from,
    validate_service_name,
)
from app.models.enum.template_categories import DefaultTemplateCategories
from app.models.organisation import Organisation
from app.models.roles_and_permissions import permissions, roles
from app.utils import get_logo_cdn_domain, guess_name_from_email_address, is_blank


def get_time_value_and_label(future_time):
    return (
        future_time.replace(tzinfo=None).isoformat(),
        "{} at {}".format(
            get_human_day(future_time.astimezone(pytz.timezone("Europe/London"))),
            get_human_time(future_time.astimezone(pytz.timezone("Europe/London"))),
        ),
    )


def get_human_time(time):
    return {"0": "midnight", "12": "midday"}.get(time.strftime(no_pad_hour24()), time.strftime(f"{no_pad_hour12()}%p").lower())


def get_human_day(time, prefix_today_with="T"):
    #  Add 1 hour to get ‘midnight today’ instead of ‘midnight tomorrow’
    time = (time - timedelta(hours=1)).strftime("%A")
    if time == datetime.utcnow().strftime("%A"):
        return "{}oday".format(prefix_today_with)
    if time == (datetime.utcnow() + timedelta(days=1)).strftime("%A"):
        return "Tomorrow"
    return time


def get_furthest_possible_scheduled_time():
    return (datetime.utcnow() + timedelta(days=4)).replace(hour=0)


def get_next_hours_until(until):
    now = datetime.utcnow()
    hours = int((until - now).total_seconds() / (60 * 60))
    return [(now + timedelta(hours=i)).replace(minute=0, second=0).replace(tzinfo=pytz.utc) for i in range(1, hours + 1)]


def get_next_days_until(until):
    now = datetime.utcnow()
    days = int((until - now).total_seconds() / (60 * 60 * 24))
    return [
        get_human_day(
            (now + timedelta(days=i)).replace(tzinfo=pytz.utc),
            prefix_today_with="Later t",
        )
        for i in range(0, days + 1)
    ]


class RadioField(WTFormsRadioField):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.validate_choice = False

    def pre_validate(self, form):
        super().pre_validate(form)
        if self.data not in dict(self.choices).keys():
            raise ValidationError(_l("You need to choose an option"))


class MultiCheckboxField(SelectMultipleField):
    widget = ListWidget(prefix_label=False)
    option_widget = CheckboxInput()


def email_address(label=_l("Email address"), gov_user=True, only_team_member_domains=False, required=True):
    if label == "email address":
        label = _l("email address")
    elif label == "phone number":
        label = _l("phone number")

    validators = [
        ValidEmail(),
    ]

    if gov_user:
        validators.append(ValidGovEmail())

    if required:
        validators.append(DataRequired(message=_l("Enter an email address")))

    if only_team_member_domains:
        validators.append(ValidTeamMemberDomain())

    return EmailField(label, validators, render_kw={"spellcheck": "false"})


class UKMobileNumber(TelField):
    def pre_validate(self, form):
        try:
            validate_phone_number(self.data)
        except InvalidPhoneError as e:
            raise ValidationError(_l(str(e)))


class InternationalPhoneNumber(TelField):
    def pre_validate(self, form):
        try:
            if self.data:
                validate_phone_number(self.data, international=True)
        except InvalidPhoneError as e:
            raise ValidationError(_l(str(e)))


def uk_mobile_number(label="Mobile number"):
    return UKMobileNumber(label, validators=[DataRequired(message=_l("This cannot be empty"))])


def international_phone_number(label=_l("Mobile number")):
    return InternationalPhoneNumber(label, validators=[DataRequired(message=_l("This cannot be empty"))])


def password(label=_l("Password")):
    return PasswordField(
        label,
        validators=[
            DataRequired(message=_l("This cannot be empty")),
            Length(8, 255, message=_l("Must be at least 8 characters")),
            Blocklist(
                message=_l(
                    "A password that is hard to guess contains: uppercase and lowercase letters, numbers and special characters, and words separated by a space."
                )
            ),
        ],
    )


class TwoFactorCode(StringField):
    validators = [
        DataRequired(message=_l("This cannot be empty")),
        Regexp(regex=r"^\d+$", message=_l("Numbers only")),
        Length(min=5, message=_l("Not enough numbers")),
        Length(max=5, message=_l("Too many numbers")),
    ]

    def __call__(self, **kwargs):
        return super().__call__(type="text", inputmode="numeric", autocomplete="one-time-code", pattern="[0-9]*", **kwargs)


class ForgivingIntegerField(StringField):
    #  Actual value is 2147483647 but this is a scary looking arbitrary number
    POSTGRES_MAX_INT = 2000000000

    def __init__(self, label=None, things="items", format_error_suffix="", **kwargs):
        self.things = things
        self.format_error_suffix = format_error_suffix
        super().__init__(label, **kwargs)

    def process_formdata(self, valuelist):
        if valuelist:
            value = valuelist[0].replace(",", "").replace(" ", "")

            try:
                value = int(value)
            except ValueError:
                pass

            if value == "":
                value = 0

        return super().process_formdata([value])

    def pre_validate(self, form):
        if self.data:
            error = None
            try:
                if int(self.data) > self.POSTGRES_MAX_INT:
                    error = "Number of {} must be {} or less".format(
                        self.things,
                        format_thousands(self.POSTGRES_MAX_INT),
                    )
            except ValueError:
                error = "Enter the number of {} {}".format(
                    self.things,
                    self.format_error_suffix,
                )

            if error:
                raise ValidationError(error)

        return super().pre_validate(form)

    def __call__(self, **kwargs):
        if self.get_form().is_submitted() and not self.get_form().validate():
            return super().__call__(value=(self.raw_data or [None])[0], **kwargs)

        try:
            value = int(self.data)
            value = format_thousands(value)
        except (ValueError, TypeError):
            value = self.data if self.data is not None else ""

        return super().__call__(value=value, **kwargs)


class OrganisationTypeField(RadioField):
    def __init__(self, *args, include_only=None, validators=None, **kwargs):
        super().__init__(
            *args,
            choices=[(value, label) for value, label in Organisation.TYPES if not include_only or value in include_only],
            validators=validators or [],
            **kwargs,
        )


class FieldWithNoneOption:
    # This is a special value that is specific to our forms. This is
    # more expicit than casting `None` to a string `'None'` which can
    # have unexpected edge cases
    NONE_OPTION_VALUE = "__NONE__"

    # When receiving Python data, eg when instantiating the form object
    # we want to convert that data to our special value, so that it gets
    # recognised as being one of the valid choices
    def process_data(self, value):
        self.data = self.NONE_OPTION_VALUE if value is None else value

    # After validation we want to convert it back to a Python `None` for
    # use elsewhere, eg posting to the API
    def post_validate(self, form, validation_stopped):
        if self.data == self.NONE_OPTION_VALUE and not validation_stopped:
            self.data = None


class FieldWithLanguageOptions:
    ENGLISH_OPTION_VALUE = "__FIP-EN__"
    FRENCH_OPTION_VALUE = "__FIP-FR__"

    def process_data(self, value):
        self.data = self.ENGLISH_OPTION_VALUE if value is None else value


class RadioFieldWithNoneOption(FieldWithNoneOption, RadioField):
    pass


class NestedFieldMixin:
    def children(self):
        # start map with root option as a single child entry
        child_map = {None: [option for option in self if option.data == self.NONE_OPTION_VALUE]}

        # add entries for all other children
        for option in self:
            if option.data == self.NONE_OPTION_VALUE:
                child_ids = [folder["id"] for folder in self.all_template_folders if folder["parent_id"] is None]
                key = self.NONE_OPTION_VALUE
            else:
                child_ids = [folder["id"] for folder in self.all_template_folders if folder["parent_id"] == option.data]
                key = option.data

            child_map[key] = [option for option in self if option.data in child_ids]

        return child_map


class NestedRadioField(RadioFieldWithNoneOption, NestedFieldMixin):
    pass


class NestedCheckboxesField(SelectMultipleField, NestedFieldMixin):
    NONE_OPTION_VALUE = None


class HiddenFieldWithLanguageOptions(FieldWithLanguageOptions, HiddenField):
    pass


class RadioFieldWithRequiredMessage(RadioField):
    def __init__(self, *args, required_message=_l("Not a valid choice"), **kwargs):
        self.required_message = required_message
        super().__init__(*args, **kwargs)

    def pre_validate(self, form):
        try:
            return super().pre_validate(form)
        except ValueError:
            raise ValueError(self.required_message)


class StripWhitespaceForm(Form):
    class Meta:
        def bind_field(self, form, unbound_field, options):
            # FieldList simply doesn't support filters.
            # @see: https://github.com/wtforms/wtforms/issues/148
            no_filter_fields = (FieldList, PasswordField)
            filters = [strip_whitespace] if not issubclass(unbound_field.field_class, no_filter_fields) else []
            filters += unbound_field.kwargs.get("filters", [])
            bound = unbound_field.bind(form=form, filters=filters, **options)
            # GC won't collect the form if we don't use a weakref
            bound.get_form = weakref.ref(form)
            return bound


class StripWhitespaceStringField(StringField):
    def __init__(self, label=None, **kwargs):
        kwargs["filters"] = tuple(
            chain(
                kwargs.get("filters", ()),
                (strip_whitespace,),
            )
        )
        super(StringField, self).__init__(label, **kwargs)


class LoginForm(StripWhitespaceForm):
    email_address = EmailField(
        _l("Email address"),
        validators=[
            Length(min=5, max=255),
            DataRequired(message=_l("This cannot be empty")),
            ValidEmail(),
        ],
    )
    password = PasswordField(_l("Password"), validators=[DataRequired(message=_l("Enter your password"))])


class RegisterUserForm(StripWhitespaceForm):
    name = StringField(_l("Full name"), validators=[DataRequired(message=_l("This cannot be empty"))])
    email_address = email_address()
    mobile_number = international_phone_number()
    password = password()
    # always register as email type
    auth_type = HiddenField("auth_type", default="email_auth")
    tou_agreed = HiddenField("tou_agreed", validators=[])

    def validate_tou_agreed(self, field):
        if field.data is not None and field.data.strip() == "":
            raise ValidationError(_l("Read and agree to continue"))


class RegisterUserFromInviteForm(RegisterUserForm):
    def __init__(self, invited_user):
        super().__init__(
            service=invited_user.service,
            email_address=invited_user.email_address,
            auth_type=invited_user.auth_type,
            name=guess_name_from_email_address(invited_user.email_address),
        )

    mobile_number = InternationalPhoneNumber(_l("Mobile number"), validators=[])
    service = HiddenField("service")
    email_address = HiddenField("email_address")
    auth_type = HiddenField("auth_type", validators=[DataRequired()])

    def validate_mobile_number(self, field):
        if self.auth_type.data == "sms_auth" and not field.data:
            raise ValidationError(_l("This cannot be empty"))


class RegisterUserFromOrgInviteForm(StripWhitespaceForm):
    def __init__(self, invited_org_user):
        super().__init__(
            organisation=invited_org_user.organisation,
            email_address=invited_org_user.email_address,
        )

    name = StringField("Full name", validators=[DataRequired(message=_l("This cannot be empty"))])

    mobile_number = InternationalPhoneNumber(
        _l("Mobile number"),
        validators=[DataRequired(message=_l("This cannot be empty"))],
    )
    password = password()
    organisation = HiddenField("organisation")
    email_address = HiddenField("email_address")
    auth_type = HiddenField("auth_type", validators=[DataRequired()])


PermissionsAbstract = type(
    "PermissionsAbstract",
    (StripWhitespaceForm,),
    {permission: BooleanField(label) for permission, label in permissions},
)


class PermissionsForm(PermissionsAbstract):  # type: ignore
    def __init__(self, all_template_folders=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.folder_permissions.choices = []
        if all_template_folders is not None:
            self.folder_permissions.all_template_folders = all_template_folders
            self.folder_permissions.choices = [
                (item["id"], item["name"]) for item in ([{"name": _l("Templates"), "id": None}] + all_template_folders)
            ]

    folder_permissions = NestedCheckboxesField(_l("Folders this team member can see"))

    login_authentication = RadioField(
        _l("Sign in using"),
        choices=[
            ("sms_auth", _l("Text message code")),
            ("email_auth", _l("Email code")),
        ],
    )

    @property
    def permissions(self):
        return {role for role in roles.keys() if self[role].data is True}

    @property
    def permissions_fields(self):
        return (getattr(self, permission) for permission, _ in permissions)

    @classmethod
    def from_user(cls, user, service_id, **kwargs):
        return cls(
            **kwargs,
            **{role: user.has_permission_for_service(service_id, role) for role in roles.keys()},
            login_authentication=user.auth_type,
        )


class InviteUserForm(PermissionsForm):
    email_address = email_address(gov_user=True)

    def __init__(self, invalid_email_address, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.invalid_email_address = invalid_email_address.lower()

    def validate_email_address(self, field):
        if field.data.lower() == self.invalid_email_address:
            raise ValidationError(_l("You cannot send an invitation to yourself"))


class InviteOrgUserForm(StripWhitespaceForm):
    email_address = email_address(gov_user=False)

    def __init__(self, invalid_email_address, *args, **kwargs):
        super(InviteOrgUserForm, self).__init__(*args, **kwargs)
        self.invalid_email_address = invalid_email_address.lower()

    def validate_email_address(self, field):
        if field.data.lower() == self.invalid_email_address:
            raise ValidationError(_l("You cannot send an invitation to yourself"))


class TwoFactorForm(StripWhitespaceForm):
    def __init__(self, validate_code_func, *args, **kwargs):
        """
        Keyword arguments:
        validate_code_func -- Validates the code with the API.
        """
        self.validate_code_func = validate_code_func
        super(TwoFactorForm, self).__init__(*args, **kwargs)

    two_factor_code = TwoFactorCode(_l("Please enter the security code."))

    def validate(self, extra_validators=None):
        if not self.two_factor_code.validate(self):
            return False

        is_valid, reason = self.validate_code_func(self.two_factor_code.data)

        if not is_valid:
            self.two_factor_code.errors.append(_l(reason))
            return False

        return True


class TextNotReceivedForm(StripWhitespaceForm):
    mobile_number = international_phone_number()


class RenameServiceForm(StripWhitespaceForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        service_id = kwargs.get("service_id", None)
        if service_id:
            self.service_id = service_id

    name = StringField(
        _l("Bilingual service name"),
        validators=[
            DataRequired(message=_l("This cannot be empty")),
            validate_service_name,
        ],
    )


class ChangeEmailFromServiceForm(StripWhitespaceForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        service_id = kwargs.get("service_id", None)
        if service_id:
            self.service_id = service_id

    email_from = StringField(
        _l("Enter the part before ‘@notification.canada.ca’"),
        validators=[
            DataRequired(message=_l("This cannot be empty")),
            validate_email_from,
        ],
    )


class SendingDomainForm(StripWhitespaceForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sending_domain.choices = kwargs["sending_domain_choices"]

    sending_domain = SelectField(_l("Sending domain"), validators=[])


class RenameOrganisationForm(StripWhitespaceForm):
    name = StringField(
        _l("Organisation name"),
        validators=[DataRequired(message=_l("This cannot be empty"))],
    )


class OrganisationOrganisationTypeForm(StripWhitespaceForm):
    org_type = OrganisationTypeField(_l("What type of organisation is this?"))


class OrganisationCrownStatusForm(StripWhitespaceForm):
    crown_status = RadioField(
        _l("Is this organisation a crown body?"),
        choices=[
            ("crown", _l("Yes")),
            ("non-crown", _l("No")),
            ("unknown", _l("Not sure")),
        ],
    )


class OrganisationAgreementSignedForm(StripWhitespaceForm):
    agreement_signed = RadioField(
        _l("Has this organisation signed the agreement?"),
        choices=[
            ("yes", _l("Yes")),
            ("no", _l("No")),
            ("unknown", _l("No (but we have some service-specific agreements in place)")),
        ],
    )


class OrganisationDomainsForm(StripWhitespaceForm):
    def populate(self, domains_list):
        for index, value in enumerate(domains_list):
            self.domains[index].data = value

    domains = FieldList(
        StripWhitespaceStringField(
            "",
            validators=[
                Optional(),
            ],
            default="",
        ),
        min_entries=20,
        max_entries=20,
        label=_l("Domain names"),
    )


# class CreateServiceStepNameForm(StripWhitespaceForm):
#     name = StringField(
#         _l("Enter bilingual service name"),
#         validators=[]
#     )

#     email_from = StringField(
#         _l("Enter the part before ‘@notification.canada.ca’"),
#         validators=[]
#     )


class CreateServiceStepNameForm(StripWhitespaceForm):
    name = StringField(
        _l("Enter bilingual service name"),
        validators=[
            DataRequired(message=_l("This cannot be empty")),
            validate_service_name,
        ],
    )

    email_from = StringField(
        _l("Enter the part before ‘@notification.canada.ca’"),
        validators=[
            DataRequired(message=_l("This cannot be empty")),
            validate_email_from,
        ],
    )


class CreateServiceStepCombinedOrganisationForm(StripWhitespaceForm):
    parent_organisation_name = StringField(
        _l("Select your department or organisation"), validators=[DataRequired(_l("Choose name from drop-down menu"))]
    )

    child_organisation_name = StringField(
        _l("Enter any other names for your group (Optional)"),
        validators=[Optional(), Length(max=500)],
    )


class CreateServiceStepOtherOrganisationForm(StripWhitespaceForm):
    other_organisation_name = StringField(
        _l("Enter name of your group"),
        validators=[DataRequired(message=_l("Enter name to continue")), Length(max=500)],
    )


class CreateServiceStepLogoForm(StripWhitespaceForm):
    def _getSelectBilingualChoices(self):
        cdn_url = get_logo_cdn_domain()
        default_en_filename = "https://{}/gov-canada-en.svg".format(cdn_url)
        default_fr_filename = "https://{}/gov-canada-fr.svg".format(cdn_url)
        choices = [
            (
                FieldWithLanguageOptions.ENGLISH_OPTION_VALUE,
                _l("English-first")
                + "||"
                + default_en_filename
                + "||"
                + _l("Bilingual logo with Government of Canada written first in English, then in French"),
            ),
            (
                FieldWithLanguageOptions.FRENCH_OPTION_VALUE,
                _l("French-first")
                + "||"
                + default_fr_filename
                + "||"
                + _l("Bilingual logo with Government of Canada written first in French, then in English"),
            ),
        ]
        return choices

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.default_branding.choices = self._getSelectBilingualChoices()

    default_branding = RadioField(
        _l("Select which language shows first <span class='sr-only'>&nbsp;used in the Government of Canada signature</span>"),
        choices=[  # Choices by default, override to get more refined options.
            (FieldWithLanguageOptions.ENGLISH_OPTION_VALUE, _l("English-first")),
            (FieldWithLanguageOptions.FRENCH_OPTION_VALUE, _l("French-first")),
        ],
        default="__FIP-EN__",
        validators=[
            DataRequired(message=_l("This cannot be empty")),
            AnyOf(
                [
                    FieldWithLanguageOptions.FRENCH_OPTION_VALUE,
                    FieldWithLanguageOptions.ENGLISH_OPTION_VALUE,
                ]
            ),
        ],
    )


class SecurityKeyForm(StripWhitespaceForm):
    keyname = StringField(
        _l("What’s your key called?"),
        validators=[DataRequired(message=_l("This cannot be empty"))],
    )


class NewOrganisationForm(
    RenameOrganisationForm,
    OrganisationOrganisationTypeForm,
    OrganisationCrownStatusForm,
):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Don’t offer the ‘not sure’ choice
        self.crown_status.choices = self.crown_status.choices[:-1]


class MessageLimit(StripWhitespaceForm):
    message_limit = IntegerField(
        _l("Daily email limit"),
        validators=[
            DataRequired(message=_l("This cannot be empty")),
            validators.NumberRange(min=1),
        ],
    )


class EmailMessageLimit(StripWhitespaceForm):
    message_limit = IntegerField(
        _l("Daily email message limit"),
        validators=[
            DataRequired(message=_l("This cannot be empty")),
            validators.NumberRange(min=1),
        ],
    )


class SMSMessageLimit(StripWhitespaceForm):
    message_limit = IntegerField(
        _l("Daily text message limit"),
        validators=[DataRequired(message=_l("This cannot be empty")), validators.NumberRange(min=1)],
    )


class SMSAnnualMessageLimit(StripWhitespaceForm):
    message_limit = IntegerField(
        _l("Annual text message limit"),
        validators=[
            DataRequired(message=_l("This cannot be empty")),
            validators.NumberRange(min=1),
        ],
    )


class EmailAnnualMessageLimit(StripWhitespaceForm):
    message_limit = IntegerField(
        _l("Annual email limit"),
        validators=[
            DataRequired(message=_l("This cannot be empty")),
            validators.NumberRange(min=1),
        ],
    )


class FreeSMSAllowance(StripWhitespaceForm):
    free_sms_allowance = IntegerField(
        _l("Numbers of text messages per fiscal year"),
        validators=[DataRequired(message=_l("This cannot be empty"))],
    )


class ConfirmPasswordForm(StripWhitespaceForm):
    def __init__(self, validate_password_func, *args, **kwargs):
        self.validate_password_func = validate_password_func
        super(ConfirmPasswordForm, self).__init__(*args, **kwargs)

    password = PasswordField(_l("Enter password"))

    def validate_password(self, field):
        if not self.validate_password_func(field.data):
            raise ValidationError(_l("Invalid password"))


TC_PRIORITY_VALUE = "__use_tc"


class BaseTemplateForm(StripWhitespaceForm):
    name = StringField(
        _l("Template name"),
        validators=[DataRequired(message=_l("This cannot be empty"))],
    )

    template_content = TextAreaField(
        _l("Message"),
        validators=[
            DataRequired(message=_l("This cannot be empty")),
            NoCommasInPlaceHolders(),
        ],
    )

    text_direction_rtl = BooleanField("text_direction_rtl")

    process_type = RadioField(
        _l("Select a priority queue"),
        choices=[
            ("bulk", _l("Bulk — Not time-sensitive")),
            ("normal", _l("Normal")),
            ("priority", _l("Priority — Time-sensitive")),
            (TC_PRIORITY_VALUE, _l("Use template category")),
        ],
        default=TC_PRIORITY_VALUE,
    )


class RequiredIf(InputRequired):
    # a validator which makes a field required if
    # another field is set and has a truthy value

    def __init__(self, other_field_name, other_field_value, *args, **kwargs):
        self.other_field_name = other_field_name
        self.other_field_value = other_field_value
        super(RequiredIf, self).__init__(*args, **kwargs)

    def __call__(self, form, field):
        other_field = form._fields.get(self.other_field_name)
        if other_field is None:
            raise Exception('no field named "%s" in form' % self.other_field_name)
        if bool(other_field.data and other_field.data == self.other_field_value):
            super(RequiredIf, self).__call__(form, field)


class BaseTemplateFormWithCategory(BaseTemplateForm):
    template_category_id = RadioField(_l("Select category"), validators=[DataRequired(message=_l("This cannot be empty"))])

    template_category_other = StringField(
        _l("Describe category"), validators=[RequiredIf("template_category_id", DefaultTemplateCategories.LOW.value)]
    )


class SMSTemplateFormWithCategory(BaseTemplateFormWithCategory):
    def validate_template_content(self, field):
        OnlySMSCharacters()(None, field)

    template_content = TextAreaField(
        _l("Text message"),
        validators=[
            DataRequired(message=_l("This cannot be empty")),
            NoCommasInPlaceHolders(),
        ],
    )


class EmailTemplateFormWithCategory(BaseTemplateFormWithCategory):
    subject = TextAreaField(_l("Subject line of the email"), validators=[DataRequired(message=_l("This cannot be empty"))])

    template_content = TextAreaField(
        _l("Email content"),
        validators=[
            DataRequired(message=_l("This cannot be empty")),
            NoCommasInPlaceHolders(),
        ],
    )


class LetterTemplateFormWithCategory(EmailTemplateFormWithCategory):
    subject = TextAreaField("Main heading", validators=[DataRequired(message="This cannot be empty")])

    template_content = TextAreaField(
        "Body",
        validators=[
            DataRequired(message="This cannot be empty"),
            NoCommasInPlaceHolders(),
        ],
    )


class LetterTemplatePostageForm(StripWhitespaceForm):
    postage = RadioField(
        "Choose the postage for this letter template",
        choices=[
            ("first", "First class"),
            ("second", "Second class"),
        ],
    )


class ForgotPasswordForm(StripWhitespaceForm):
    email_address = email_address(gov_user=False)


class NewPasswordForm(StripWhitespaceForm):
    new_password = password()


class ChangePasswordForm(StripWhitespaceForm):
    def __init__(self, validate_password_func, *args, **kwargs):
        self.validate_password_func = validate_password_func
        super(ChangePasswordForm, self).__init__(*args, **kwargs)

    old_password = password(_l("Current password"))
    new_password = password(_l("New password"))

    def validate_old_password(self, field):
        if not self.validate_password_func(field.data):
            raise ValidationError(_l("Invalid password"))


class CsvUploadForm(StripWhitespaceForm):
    file = FileField(
        _l("Choose a file"),
        validators=[DataRequired(message="Please pick a file"), CsvFileValidator()],
    )


class ChangeNameForm(StripWhitespaceForm):
    new_name = StringField(_l("Your name"))


class ChangeEmailForm(StripWhitespaceForm):
    def __init__(self, validate_email_func, *args, **kwargs):
        self.validate_email_func = validate_email_func
        super(ChangeEmailForm, self).__init__(*args, **kwargs)

    email_address = email_address()

    def validate_email_address(self, field):
        is_valid = self.validate_email_func(field.data)
        if is_valid:
            raise ValidationError(_l("The email address is already in use"))


class ChangeNonGovEmailForm(ChangeEmailForm):
    email_address = email_address(gov_user=False)


class ChangeMobileNumberForm(StripWhitespaceForm):
    mobile_number = international_phone_number()


class ChooseTimeForm(StripWhitespaceForm):
    def __init__(self, *args, **kwargs):
        super(ChooseTimeForm, self).__init__(*args, **kwargs)
        self.scheduled_for.choices = [("", "Now")] + [
            get_time_value_and_label(hour) for hour in get_next_hours_until(get_furthest_possible_scheduled_time())
        ]
        self.scheduled_for.categories = get_next_days_until(get_furthest_possible_scheduled_time())

    scheduled_for = RadioField(
        _l("When should we send these messages?"),
        default="",
    )


class CreateKeyForm(StripWhitespaceForm):
    def __init__(self, existing_keys, *args, **kwargs):
        self.existing_key_names = [key["name"].lower() for key in existing_keys if not key["expiry_date"]]
        super().__init__(*args, **kwargs)

    key_type = RadioField(
        _l("Type of API key"),
    )

    key_name = StringField(
        "Description of key",
        validators=[DataRequired(message=_l("You need to give the key a name")), Length(max=255)],
    )

    def validate_key_name(self, key_name):
        if key_name.data.lower() in self.existing_key_names:
            raise ValidationError(_l("A key with this name already exists"))


class CreateInboundSmsForm(StripWhitespaceForm):
    def __init__(self, existing_numbers, *args, **kwargs):
        self.existing_numbers = [n for n in existing_numbers]
        super().__init__(*args, **kwargs)

    inbound_number = StringField(
        _l("Inbound SMS number"),
        validators=[DataRequired(message=_l("You need to provide a number"))],
    )

    def validate_number(self, number):
        if number in self.existing_numbers:
            raise ValidationError(_l("This number already exists"))


class ContactNotify(StripWhitespaceForm):
    not_empty = _l("Enter your name")
    name = StringField(_l("Your name"), validators=[DataRequired(message=not_empty), Length(max=255)])
    support_type = RadioField(
        _l("How can we help?"),
        choices=[
            ("ask_question", _l("Ask a question")),
            ("technical_support", _l("Get technical support")),
            ("give_feedback", _l("Give feedback")),
            ("other", _l("Other")),
        ],
    )
    email_address = email_address(label=_l("Your email"), gov_user=False)


class ContactMessageStep(ContactNotify):
    message = TextAreaField(
        _l("Message"),
        validators=[DataRequired(message=_l("You need to enter something if you want to contact us")), Length(max=2000)],
    )


class SelectLogoForm(StripWhitespaceForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.branding_style.choices = kwargs["choices"]
        self.branding_style.label.text = kwargs["label"]
        self.branding_style.validators = [DataRequired()]

    branding_style = SelectField()
    file = FileField_wtf(
        _l("Upload logo"),
        validators=[FileAllowed(["png"], _l("Your logo must be an image in PNG format"))],
    )


class Triage(StripWhitespaceForm):
    severe = RadioField(
        "Is it an emergency?",
        choices=[
            ("yes", "Yes"),
            ("no", "No"),
        ],
    )


class ProviderForm(StripWhitespaceForm):
    priority = IntegerField(
        "Priority",
        [validators.NumberRange(min=1, max=100, message="Must be between 1 and 100")],
    )


class ServiceContactDetailsForm(StripWhitespaceForm):
    contact_details_type = RadioField(
        "Type of contact details",
        choices=[
            ("url", "Link"),
            ("email_address", "Email address"),
            ("phone_number", "Phone number"),
        ],
    )

    url = StringField("URL")
    email_address = EmailField(_l("Email address"))
    phone_number = StringField(_l("Phone number"))

    def validate(self, extra_validators=None):
        if self.contact_details_type.data == "url":
            self.url.validators = [DataRequired(), URL(message="Must be a valid URL")]

        elif self.contact_details_type.data == "email_address":
            self.email_address.validators = [
                DataRequired(),
                Length(min=5, max=255),
                ValidEmail(),
            ]

        elif self.contact_details_type.data == "phone_number":

            def valid_phone_number(self, num):
                try:
                    validate_phone_number(num.data)
                    return True
                except InvalidPhoneError:
                    raise ValidationError(_l("Must be a valid phone number"))

            self.phone_number.validators = [
                DataRequired(),
                Length(min=5, max=20),
                valid_phone_number,
            ]

        return super().validate(extra_validators)


class SelectCsvFromS3Form(StripWhitespaceForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.s3_files.choices = kwargs["choices"]
        self.s3_files.label.text = kwargs["label"]

    s3_files = RadioField()


class ServiceReplyToEmailForm(StripWhitespaceForm):
    label_text = _l("Reply-to email address")
    email_address = email_address(label=_l(label_text), only_team_member_domains=True, gov_user=False)
    is_default = BooleanField(_l("Make this email address the default"))


class ServiceSmsSenderForm(StripWhitespaceForm):
    sms_sender = StringField(
        _l("Text message sender"),
        validators=[
            DataRequired(message=_l("This cannot be empty")),
            Length(max=11, message=_l("Enter 11 characters or fewer")),
            Length(min=4, message=_l("Enter 4 characters or more")),
            LettersNumbersAndFullStopsOnly(),
            DoesNotStartWithDoubleZero(),
        ],
    )
    is_default = BooleanField(_l("Make this text message sender the default"))


class ServiceEditInboundNumberForm(StripWhitespaceForm):
    is_default = BooleanField(_l("Make this text message sender the default"))


class ServiceLetterContactBlockForm(StripWhitespaceForm):
    letter_contact_block = TextAreaField(
        validators=[
            DataRequired(message="This cannot be empty"),
            NoCommasInPlaceHolders(),
        ]
    )
    is_default = BooleanField("Set as your default address")

    def validate_letter_contact_block(self, field):
        line_count = field.data.strip().count("\n")
        if line_count >= 10:
            raise ValidationError("Contains {} lines, maximum is 10".format(line_count + 1))


class OnOffField(RadioField):
    def __init__(self, label, *args, **kwargs):
        super().__init__(
            label,
            choices=[
                (True, _l("On")),
                (False, _l("Off")),
            ],
            *args,
            **kwargs,
        )

    def process_formdata(self, valuelist):
        if valuelist:
            value = valuelist[0]
            self.data = (value == "True") if value in ["True", "False"] else value


class ServiceOnOffSettingForm(StripWhitespaceForm):
    def __init__(self, name, *args, truthy="On", falsey="Off", **kwargs):
        super().__init__(*args, **kwargs)

        if truthy == "On":
            truthy = _l("On")

        if falsey == "Off":
            falsey = _l("Off")

        self.enabled.label.text = name
        self.enabled.choices = [
            (True, truthy),
            (False, falsey),
        ]

    enabled = OnOffField("Choices")


class ServiceSwitchChannelForm(ServiceOnOffSettingForm):
    def __init__(self, channel, *args, **kwargs):
        name = _l(
            "Send {}".format(
                {
                    "email": "emails",
                    "sms": "text messages",
                    "letter": "letters",
                }.get(channel)
            )
        )

        super().__init__(name, *args, **kwargs)


class SetEmailBranding(StripWhitespaceForm):
    branding_style = RadioFieldWithNoneOption(
        _l("Branding style"),
    )

    DEFAULT_EN = (
        FieldWithLanguageOptions.ENGLISH_OPTION_VALUE,
        _l("English Government of Canada signature"),
    )
    DEFAULT_FR = (
        FieldWithLanguageOptions.FRENCH_OPTION_VALUE,
        _l("French Government of Canada signature"),
    )

    def __init__(self, all_branding_options, current_branding):
        super().__init__(branding_style=current_branding)

        self.branding_style.choices = sorted(
            all_branding_options + [self.DEFAULT_EN] + [self.DEFAULT_FR],
            key=lambda branding: (
                branding[0] != current_branding,
                branding[0] is not self.DEFAULT_EN[0],
                branding[0] is not self.DEFAULT_FR[0],
                branding[1].lower(),
            ),
        )


class SetLetterBranding(SetEmailBranding):
    # form is the same, but instead of GOV.UK we have None as a valid option
    DEFAULT = (FieldWithNoneOption.NONE_OPTION_VALUE, "None")


class PreviewBranding(StripWhitespaceForm):
    branding_style = HiddenFieldWithLanguageOptions("branding_style")


class ServiceUpdateEmailBranding(StripWhitespaceForm):
    name = StringField(_l("Name of brand"))
    text = StringField(_l("Text"))
    colour = StringField(
        _l("Colour"),
        validators=[
            Regexp(
                regex="^$|^#(?:[0-9a-fA-F]{3}){1,2}$",
                message=_l("Must be a valid color hex code (starting with #)"),
            )
        ],
    )
    file = FileField_wtf(_l("Upload a PNG logo"))
    brand_type = RadioField(
        _l("Brand type"),
        choices=[
            ("both_english", _l("English Government of Canada signature and custom logo")),
            ("both_french", _l("French Government of Canada signature and custom logo")),
            ("custom_logo", _l("Custom Logo")),
            (
                "custom_logo_with_background_colour",
                _l("Custom Logo on a background colour"),
            ),
            ("no_branding", _l("No branding")),
        ],
    )
    organisation = RadioField(_l("Select an organisation"), choices=[])
    alt_text_en = StringField(_l("Alternative text for English logo"))
    alt_text_fr = StringField(_l("Alternative text for French logo"))

    def validate_name(form, name):
        op = request.form.get("operation")
        if op == "email-branding-details" and not form.name.data:
            raise ValidationError(_l("This field is required"))

    def validate_alt_text_en(form, alt_text_en):
        op = request.form.get("operation")
        if op == "email-branding-details" and not form.alt_text_en.data:
            raise ValidationError(_l("This field is required"))

    def validate_alt_text_fr(form, alt_text_fr):
        op = request.form.get("operation")
        if op == "email-branding-details" and not form.alt_text_fr.data:
            raise ValidationError(_l("This field is required"))


class SVGFileUpload(StripWhitespaceForm):
    file = FileField_wtf(
        _l("Upload an SVG logo"),
        validators=[
            FileAllowed(["svg"], _l("SVG Images only!")),
            DataRequired(message=_l("You need to upload a file to submit")),
        ],
    )


class ServiceLetterBrandingDetails(StripWhitespaceForm):
    name = StringField("Name of brand", validators=[DataRequired()])


class PDFUploadForm(StripWhitespaceForm):
    file = FileField_wtf(
        "Upload a letter in PDF format to check if it fits in the printable area",
        validators=[
            FileAllowed(["pdf"], "PDF documents only!"),
            DataRequired(message="You need to upload a file to submit"),
        ],
    )


class EmailFieldInSafelist(EmailField, StripWhitespaceStringField):
    pass


class InternationalPhoneNumberInSafelist(InternationalPhoneNumber, StripWhitespaceStringField):
    pass


class Safelist(StripWhitespaceForm):
    def populate(self, email_addresses, phone_numbers):
        for form_field, existing_safelist in (
            (self.email_addresses, email_addresses),
            (self.phone_numbers, phone_numbers),
        ):
            for index, value in enumerate(existing_safelist):
                form_field[index].data = value

    email_addresses = FieldList(
        EmailFieldInSafelist("", validators=[Optional(), ValidEmail()], default=""),
        min_entries=5,
        max_entries=5,
        label=_l("Email safelist"),
    )

    phone_numbers = FieldList(
        InternationalPhoneNumberInSafelist("", validators=[Optional()], default=""),
        min_entries=5,
        max_entries=5,
        label=_l("Phone safelist"),
    )


class DateFilterForm(StripWhitespaceForm):
    start_date = DateField(_l("Start Date"), [validators.optional()])
    end_date = DateField(_l("End Date"), [validators.optional()])
    include_from_test_key = BooleanField(_l("Include test keys"), default="checked", false_values={"N"})


class RequiredDateFilterForm(StripWhitespaceForm):
    start_date = DateField(_l("Start Date"))
    end_date = DateField(_l("End Date"))


class SearchByNameForm(StripWhitespaceForm):
    search = SearchField(
        _l("Search by name"),
        validators=[DataRequired("You need to enter full or partial name to search by.")],
    )


class SearchUsersByEmailForm(StripWhitespaceForm):
    search = SearchField(
        _l("Search by name or email address"),
        validators=[DataRequired(_l("You need to enter full or partial email address to search by."))],
    )


class SearchIds(StripWhitespaceForm):
    search = SearchField(
        _l("List of UUIDs"),
        validators=[DataRequired(_l("You need to enter one or more UUIDs to search by."))],
    )


class SearchUsersForm(StripWhitespaceForm):
    search = SearchField(_l("Search by name or email address"))


class SearchNotificationsForm(StripWhitespaceForm):
    to = SearchField()

    labels = {
        "email": _l("Search by email address"),
        "sms": _l("Search by phone number"),
    }

    def __init__(self, message_type, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.to.label.text = self.labels.get(
            message_type,
            _l("Search by email address or phone number"),
        )


class PlaceholderForm(StripWhitespaceForm):
    pass


class PasswordFieldShowHasContent(StringField):
    widget = widgets.PasswordInput(hide_value=False)


class ServiceInboundNumberForm(StripWhitespaceForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.inbound_number.choices = kwargs["inbound_number_choices"]

    inbound_number = RadioField(
        "Select your inbound number",
    )


class CallbackForm(StripWhitespaceForm):
    def validate(self, extra_validators=None):
        return super().validate(extra_validators)


class ServiceReceiveMessagesCallbackForm(CallbackForm):
    url = StringField(
        "URL",
        validators=[
            DataRequired(message=_l("This cannot be empty")),
            Regexp(regex="^https.*", message=_l("Enter a URL that starts with https://")),
            ValidCallbackUrl(),
        ],
    )
    bearer_token = PasswordFieldShowHasContent(
        _l("Bearer token"),
        validators=[
            DataRequired(message=_l("This cannot be empty")),
            Length(min=10, message=_l("Must be at least 10 characters")),
        ],
    )


class ServiceDeliveryStatusCallbackForm(CallbackForm):
    url = StringField(
        "URL",
        validators=[
            DataRequired(message=_l("This cannot be empty")),
            Regexp(regex="^https.*", message=_l("Enter a URL that starts with https://")),
            ValidCallbackUrl(),
        ],
    )
    bearer_token = PasswordFieldShowHasContent(
        _l("Bearer token"),
        validators=[
            DataRequired(message=_l("This cannot be empty")),
            Length(min=10, message=_l("Must be at least 10 characters")),
        ],
    )
    test_response_time = SubmitField()


class InternationalSMSForm(StripWhitespaceForm):
    enabled = RadioField(
        _l("Send text messages to international phone numbers"),
        choices=[
            ("on", _l("On")),
            ("off", _l("Off")),
        ],
    )


class SMSPrefixForm(StripWhitespaceForm):
    enabled = RadioField(
        "",
        choices=[
            ("on", _l("On")),
            ("off", _l("Off")),
        ],
    )


def get_placeholder_form_instance(
    placeholder_name,
    dict_to_populate_from,
    template_type,
    is_conditional=False,
    optional_placeholder=False,
    allow_international_phone_numbers=False,
):
    if Columns.make_key(placeholder_name) == "emailaddress" and template_type == "email":
        field = email_address(label=placeholder_name, gov_user=False)
    elif Columns.make_key(placeholder_name) == "phonenumber" and template_type == "sms":
        if allow_international_phone_numbers:
            field = international_phone_number(label=placeholder_name)
        else:
            field = uk_mobile_number(label=placeholder_name)
    elif optional_placeholder:
        field = StringField(_l("What is the custom content in (({})) ?").format(placeholder_name))
    elif is_conditional:
        field = RadioField(
            _l("Do you want to include the content in (({})) ?").format(placeholder_name),
            choices=[
                ("yes", _l("Yes")),
                ("no", _l("No")),
            ],
        )
    else:
        field = StringField(
            _l("What is the custom content in (({})) ?").format(placeholder_name),
            validators=[DataRequired(message=_l("This cannot be empty"))],
        )

    PlaceholderForm.placeholder_value = field

    return PlaceholderForm(placeholder_value=dict_to_populate_from.get(placeholder_name, ""))


class SetSenderForm(StripWhitespaceForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sender.choices = kwargs["sender_choices"]
        self.sender.label.text = kwargs["sender_label"]

    sender = RadioField()


class SetTemplateSenderForm(StripWhitespaceForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sender.choices = kwargs["sender_choices"]
        self.sender.label.text = "Select your sender"

    sender = RadioField()


class LinkOrganisationsForm(StripWhitespaceForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.organisations.choices = kwargs["choices"]

    organisations = RadioField("Select an organisation")


branding_options = (
    ("fip_english", "English Government of Canada signature"),
    ("fip_french", "French Government of Canada signature"),
    ("both_english", "English Government of Canada signature and custom logo"),
    ("both_french", "French Government of Canada signature and custom logo"),
    ("custom_logo", "Your logo"),
    ("custom_logo_with_background_colour", "Your logo on a colour"),
)
branding_options_dict = dict(branding_options)


class BrandingOptionsEmail(StripWhitespaceForm):
    options = RadioField(
        "Branding options",
        choices=branding_options,
    )


class ServiceDataRetentionForm(StripWhitespaceForm):
    notification_type = RadioField(
        "What notification type?",
        choices=[
            ("email", "Email"),
            ("sms", "SMS"),
            ("letter", "Letter"),
        ],
    )
    days_of_retention = IntegerField(
        label="Days of retention",
        validators=[validators.NumberRange(min=3, max=7, message="Must be between 3 and 7")],
    )


class ServiceDataRetentionEditForm(StripWhitespaceForm):
    days_of_retention = IntegerField(
        label="Days of retention",
        validators=[validators.NumberRange(min=3, max=7, message="Must be between 3 and 7")],
    )


class ReturnedLettersForm(StripWhitespaceForm):
    references = TextAreaField(
        "Letter references",
        validators=[
            DataRequired(message="This cannot be empty"),
        ],
    )


class TemplateFolderForm(StripWhitespaceForm):
    def __init__(self, all_service_users=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if all_service_users is not None:
            self.users_with_permission.all_service_users = all_service_users
            self.users_with_permission.choices = [(item.id, item.name) for item in all_service_users]

    users_with_permission = MultiCheckboxField(_l("Team members who can see this folder"))
    name = StringField(_l("Folder name"), validators=[DataRequired(message=_l("This cannot be empty"))])


def required_for_ops(*operations):
    operations = set(operations)

    def validate(form, field):
        if form.op not in operations and any(field.raw_data):
            # super weird
            raise validators.StopValidation("Must be empty")
        if form.op in operations and all(map(is_blank, field.raw_data)):
            raise validators.StopValidation(_l("This cannot be empty"))

    return validate


class CreateTemplateForm(Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.what_type.choices = [("email", _l("Email")), ("sms", _l("Text"))]

    what_type = RadioField("")


class AddEmailRecipientsForm(Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.what_type.choices = [("many_recipients", _l("Many recipients")), ("one_recipient", _l("One recipient"))]

    what_type = RadioField("")
    placeholder_value = email_address(_l("Email address of recipient"), gov_user=False)


class AddSMSRecipientsForm(Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.what_type.choices = [("many_recipients", _l("Many recipients")), ("one_recipient", _l("One recipient"))]

    what_type = RadioField("")
    placeholder_value = international_phone_number(_l("Phone number of recipient"))


class TemplateAndFoldersSelectionForm(Form):
    """
    This form expects the form data to include an operation, based on which submit button is clicked.
    If enter is pressed, unknown will be sent by a hidden submit button at the top of the form.
    The value of this operation affects which fields are required, expected to be empty, or optional.

    * unknown
        currently not implemented, but in the future will try and work out if there are any obvious commands that can be
        assumed based on which fields are empty vs populated.
    * move-to-existing-folder
        must have data for templates_and_folders checkboxes, and move_to radios
    * move-to-new-folder
        must have data for move_to_new_folder_name, cannot have data for move_to_existing_folder_name
    * add-new-folder
        must have data for move_to_existing_folder_name, cannot have data for move_to_new_folder_name
    """

    ALL_TEMPLATES_FOLDER = {
        "name": "Templates",
        "id": RadioFieldWithNoneOption.NONE_OPTION_VALUE,
    }

    def __init__(
        self,
        all_template_folders,
        template_list,
        allow_adding_letter_template,
        allow_adding_copy_of_template,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.templates_and_folders.choices = template_list.as_id_and_name

        self.op = None
        self.is_move_op = self.is_add_folder_op = False

        self.move_to.all_template_folders = all_template_folders
        self.move_to.choices = [(item["id"], item["name"]) for item in ([self.ALL_TEMPLATES_FOLDER] + all_template_folders)]

    def is_selected(self, template_folder_id):
        return template_folder_id in (self.templates_and_folders.data or [])

    def validate(self, extra_validators=None):
        self.op = request.form.get("operation")

        self.is_move_op = self.op in {"move-to-existing-folder", "move-to-new-folder"}
        self.is_add_folder_op = self.op in {"add-new-folder", "move-to-new-folder"}

        if not (self.is_add_folder_op or self.is_move_op):
            return False

        return super().validate(extra_validators)

    def get_folder_name(self):
        if self.op == "add-new-folder":
            return self.add_new_folder_name.data
        elif self.op == "move-to-new-folder":
            return self.move_to_new_folder_name.data
        return None

    templates_and_folders = MultiCheckboxField(
        "Choose templates or folders",
        validators=[required_for_ops("move-to-new-folder", "move-to-existing-folder")],
    )
    # if no default set, it is set to None, which process_data transforms to '__NONE__'
    # this means '__NONE__' (self.ALL_TEMPLATES option) is selected when no form data has been submitted
    # set default to empty string so process_data method doesn't perform any transformation
    move_to = NestedRadioField(
        _l("Select a folder"),
        default="",
        validators=[required_for_ops("move-to-existing-folder"), Optional()],
    )
    add_new_folder_name = StringField(_l("Folder name"), validators=[required_for_ops("add-new-folder")])
    move_to_new_folder_name = StringField(_l("Folder name"), validators=[required_for_ops("move-to-new-folder")])


class ClearCacheForm(StripWhitespaceForm):
    model_type = RadioField(
        _l("What do you want to clear today"),
    )


class GoLiveNotesForm(StripWhitespaceForm):
    request_to_go_live_notes = TextAreaField(
        _l("Go live notes"),
        filters=[lambda x: x or None],
    )


class AcceptAgreementForm(StripWhitespaceForm):
    @classmethod
    def from_organisation(cls, org):
        if org.agreement_signed_on_behalf_of_name and org.agreement_signed_on_behalf_of_email_address:
            who = "someone-else"
        elif org.agreement_signed_version:  # only set if user has submitted form previously
            who = "me"
        else:
            who = None

        return cls(
            version=org.agreement_signed_version,
            who=who,
            on_behalf_of_name=org.agreement_signed_on_behalf_of_name,
            on_behalf_of_email=org.agreement_signed_on_behalf_of_email_address,
        )

    version = StringField(_l("Which version of the agreement do you want to accept?"))

    who = RadioField(
        _l("Who are you accepting the agreement for?"),
        choices=(
            (
                "me",
                _l("Yourself"),
            ),
            (
                "someone-else",
                _l("Someone else"),
            ),
        ),
    )

    on_behalf_of_name = StringField(_l("What’s their name?"))

    on_behalf_of_email = email_address(
        _l("What’s their email address?"),
        required=False,
        gov_user=False,
    )

    def __validate_if_nominating(self, field):
        if self.who.data == "someone-else":
            if not field.data:
                raise ValidationError(_l("This cannot be empty"))
        else:
            field.data = ""

    validate_on_behalf_of_name = __validate_if_nominating
    validate_on_behalf_of_email = __validate_if_nominating

    def validate_version(self, field):
        try:
            float(field.data)
        except (TypeError, ValueError):
            raise ValidationError(_l("Must be a number"))


class GoLiveAboutServiceForm(StripWhitespaceForm):
    department_org_name = StringField(
        _l("Name of department or organisation"),
        validators=[DataRequired(), Length(max=500)],
    )
    purpose = TextAreaField(
        _l("For what purpose are you using GC Notify?"),
        validators=[DataRequired(), Length(max=2000)],
    )
    intended_recipients = MultiCheckboxField(
        _l("Who are the intended recipients of notifications?"),
        default="",
        choices=[
            ("internal", _l("Colleagues within your department (internal)")),
            ("external", _l("Partners from other organisations (external)")),
            ("public", _l("Public")),
        ],
        validators=[DataRequired()],
    )


class GoLiveAboutServiceFormNoOrg(StripWhitespaceForm):
    purpose = TextAreaField(
        _l("For what purpose are you using GC Notify?"),
        validators=[DataRequired(), Length(max=2000)],
    )
    intended_recipients = MultiCheckboxField(
        _l("Who are the intended recipients of notifications?"),
        default="",
        choices=[
            ("internal", _l("Colleagues within your department (internal)")),
            ("external", _l("Partners from other organisations (external)")),
            ("public", _l("Public")),
        ],
        validators=[DataRequired()],
    )


class GoLiveAboutNotificationsForm(GoLiveAboutServiceForm):
    notification_types = MultiCheckboxField(
        _l("Specify the type of notifications you plan on sending."),
        choices=[
            ("email", _l("Email")),
            ("sms", _l("Text message")),
        ],
        validators=[DataRequired()],
    )
    expected_volume = RadioField(
        _l("How many notifications do you plan on sending per month?"),
        choices=[
            ("1-1k", _l("1 to 1,000 notifications")),
            ("1k-10k", _l("1,000 to 10,000 notifications")),
            ("10k-100k", _l("10,000 to 100,000 notifications")),
            ("100k+", _l("More than 100,000 notifications")),
        ],
        validators=[DataRequired()],
    )


class GoLiveAboutNotificationsFormNoOrg(GoLiveAboutServiceFormNoOrg):
    notification_types = MultiCheckboxField(
        _l("Specify the type of notifications you plan on sending."),
        choices=[
            ("email", _l("Email")),
            ("sms", _l("Text message")),
        ],
        validators=[DataRequired()],
    )
    expected_volume = RadioField(
        _l("How many notifications do you plan on sending per month?"),
        choices=[
            ("1-1k", _l("1 to 1,000 notifications")),
            ("1k-10k", _l("1,000 to 10,000 notifications")),
            ("10k-100k", _l("10,000 to 100,000 notifications")),
            ("100k+", _l("More than 100,000 notifications")),
        ],
        validators=[DataRequired()],
    )


class BrandingGOCForm(StripWhitespaceForm):
    """
    Form for selecting logo from GOC options

    Attributes:
        goc_branding (RadioField): Field for entering the the logo
    """

    goc_branding = RadioField(
        _l("Choose which language shows first <span class='sr-only'>&nbsp;used in the Government of Canada signature</span>"),
        choices=[  # Choices by default, override to get more refined options.
            (FieldWithLanguageOptions.ENGLISH_OPTION_VALUE, _l("English-first")),
            (FieldWithLanguageOptions.FRENCH_OPTION_VALUE, _l("French-first")),
        ],
        validators=[DataRequired(message=_l("You must select an option to continue"))],
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class BrandingPoolForm(StripWhitespaceForm):
    """
    Form for selecting alternate branding logo from a pool of options associated with the service's organisation.

    Attributes:
        pool_branding (RadioField): Field for entering the the logo
    """

    pool_branding = RadioField(
        _l("Select alternate logo"),
        # Choices by default, override to get more refined options.
        choices=[],
        validators=[DataRequired(message=_l("You must select an option to continue"))],
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class BrandingRequestForm(StripWhitespaceForm):
    """
    Form for handling new branding requests.

    Attributes:
        name (StringField): Field for entering the name of the logo.
        file (FileField_wtf): Field for uploading the logo file.
    """

    name = StringField(label=_l("Name of logo"), validators=[DataRequired(message=_l("Enter the name of the logo"))])
    alt_text_en = StringField(label=_l("English"), validators=[DataRequired(message=_l("This cannot be empty"))])
    alt_text_fr = StringField(label=_l("French"), validators=[DataRequired(message=_l("This cannot be empty"))])
    file = FileField_wtf(
        label=_l("Prepare your logo"),
        validators=[
            DataRequired(message=_l("You must select a file to continue")),
        ],
    )


class TemplateCategoryForm(StripWhitespaceForm):
    name_en = StringField("EN", validators=[DataRequired(message=_l("This cannot be empty"))])
    name_fr = StringField("FR", validators=[DataRequired(message=_l("This cannot be empty"))])
    description_en = StringField("EN")
    description_fr = StringField("FR")
    hidden = RadioField(_l("Hide category"), choices=[("True", _l("Hide")), ("False", _l("Show"))])
    sms_sending_vehicle = RadioField(
        _l("Sending method for text messages"), choices=[("long_code", _l("Long code")), ("short_code", _l("Short code"))]
    )

    email_process_type = RadioField(
        _l("Email priority"),
        choices=[
            ("priority", _l("Priority")),
            ("normal", _l("Normal")),
            ("bulk", _l("Bulk")),
        ],
        validators=[DataRequired(message=_l("This cannot be empty"))],
    )
    sms_process_type = RadioField(
        _l("Text message priority"),
        choices=[
            ("priority", _l("Priority")),
            ("normal", _l("Normal")),
            ("bulk", _l("Bulk")),
        ],
        validators=[DataRequired(message=_l("This cannot be empty"))],
    )
