from collections import OrderedDict
from datetime import datetime

from flask import (
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_babel import _
from flask_babel import lazy_gettext as _l
from flask_login import current_user
from notifications_python_client.errors import HTTPError

from app import (
    billing_api_client,
    current_service,
    email_branding_client,
    inbound_number_client,
    letter_branding_client,
    notification_api_client,
    organisations_client,
    service_api_client,
    user_api_client,
)
from app.main import main
from app.main.forms import (
    ChangeEmailFromServiceForm,
    ConfirmPasswordForm,
    EmailAnnualMessageLimit,
    FieldWithLanguageOptions,
    FreeSMSAllowance,
    GoLiveAboutNotificationsForm,
    GoLiveAboutNotificationsFormNoOrg,
    GoLiveAboutServiceForm,
    GoLiveAboutServiceFormNoOrg,
    InternationalSMSForm,
    LinkOrganisationsForm,
    MessageLimit,
    PreviewBranding,
    RenameServiceForm,
    SearchByNameForm,
    SelectLogoForm,
    SendingDomainForm,
    ServiceDataRetentionEditForm,
    ServiceDataRetentionForm,
    ServiceEditInboundNumberForm,
    ServiceInboundNumberForm,
    ServiceLetterContactBlockForm,
    ServiceOnOffSettingForm,
    ServiceReplyToEmailForm,
    ServiceSmsSenderForm,
    ServiceSwitchChannelForm,
    SetEmailBranding,
    SetLetterBranding,
    SMSAnnualMessageLimit,
    SMSMessageLimit,
    SMSPrefixForm,
)
from app.main.views.email_branding import get_preview_template
from app.s3_client.s3_logo_client import upload_email_logo
from app.utils import (
    DELIVERED_STATUSES,
    FAILURE_STATUSES,
    SENDING_STATUSES,
    documentation_url,
    email_safe,
    get_logo_cdn_domain,
    get_new_default_reply_to_address,
    get_verified_ses_domains,
    user_has_permissions,
    user_is_gov_user,
    user_is_platform_admin,
)

PLATFORM_ADMIN_SERVICE_PERMISSIONS = OrderedDict(
    [
        (
            "inbound_sms",
            {
                "title": _l("Receive inbound SMS"),
                "requires": "sms",
                "endpoint": ".service_set_inbound_number",
            },
        ),
        ("email_auth", {"title": _l("Email authentication")}),
        ("upload_letters", {"title": _l("Uploading letters"), "requires": "letter"}),
    ]
)


@main.route("/services/<service_id>/service-settings")
@user_has_permissions("manage_service", "manage_api_keys")
def service_settings(service_id: str):
    limits = {
        "free_yearly_email": current_app.config["FREE_YEARLY_EMAIL_LIMIT"],
        "free_yearly_sms": current_app.config["FREE_YEARLY_SMS_LIMIT"],
    }
    callback_api = (
        service_api_client.get_service_callback_api(current_service.id, current_service.service_callback_api[0])
        if current_service.service_callback_api
        else None
    )
    assert limits["free_yearly_email"] >= 2_000_000, "The user-interface does not support French translations of < 2M"
    return render_template(
        "views/service-settings.html",
        service_permissions=PLATFORM_ADMIN_SERVICE_PERMISSIONS,
        # type: ignore
        sending_domain=current_service.sending_domain or current_app.config["SENDING_DOMAIN"],
        limits=limits,
        callback_api=callback_api,
    )


@main.route("/services/<service_id>/service-settings/name", methods=["GET", "POST"])
@user_has_permissions("manage_service")
def service_name_change(service_id):
    form = RenameServiceForm(service_id=service_id)

    if request.method == "GET":
        form.name.data = current_service.name

    if form.validate_on_submit():
        if form.name.data == current_service.name:
            return redirect(url_for(".service_settings", service_id=service_id))

        session["service_name_change"] = form.name.data
        return redirect(url_for(".service_name_change_confirm", service_id=service_id))

    return render_template(
        "views/service-settings/name.html",
        form=form,
    )


@main.route("/services/<service_id>/service-settings/name/confirm", methods=["GET", "POST"])
@user_has_permissions("manage_service")
def service_name_change_confirm(service_id):
    # Validate password for form
    def _check_password(pwd):
        return user_api_client.verify_password(current_user.id, pwd)

    form = ConfirmPasswordForm(_check_password)

    if form.validate_on_submit():
        try:
            current_service.update(
                name=session["service_name_change"],
            )
        except HTTPError as e:
            error_msg = "Duplicate service name '{}'".format(session["service_name_change"])
            if e.status_code == 400 and error_msg in e.message["name"]:
                # Redirect the user back to the change service name screen
                flash(_("This service name is already in use"), "error")
                return redirect(url_for("main.service_name_change", service_id=service_id))
            else:
                raise e
        else:
            session.pop("service_name_change")
            flash(_("Setting updated"), "default_with_tick")
            return redirect(url_for(".service_settings", service_id=service_id))
    return render_template(
        "views/service-settings/confirm.html",
        heading=_("Change your service name"),
        form=form,
    )


@main.route("/services/<service_id>/service-settings/email_from", methods=["GET", "POST"])
@user_has_permissions("manage_service")
def service_email_from_change(service_id):
    form = ChangeEmailFromServiceForm(service_id=service_id, sending_domain=current_app.config["SENDING_DOMAIN"])

    if request.method == "GET":
        form.email_from.data = current_service.email_from

    if form.validate_on_submit():
        if form.email_from.data == current_service.email_from:
            return redirect(url_for(".service_settings", service_id=service_id))

        session["service_email_from_change"] = form.email_from.data
        return redirect(url_for(".service_email_from_change_confirm", service_id=service_id))

    return render_template(
        "views/service-settings/email_from.html",
        form=form,
        sending_domain=current_service.sending_domain or current_app.config["SENDING_DOMAIN"],
    )


@main.route(
    "/services/<service_id>/service-settings/email_from/confirm",
    methods=["GET", "POST"],
)
@user_has_permissions("manage_service")
def service_email_from_change_confirm(service_id):
    # Validate password for form
    def _check_password(pwd):
        return user_api_client.verify_password(current_user.id, pwd)

    form = ConfirmPasswordForm(_check_password)

    if form.validate_on_submit():
        try:
            current_service.update(email_from=email_safe(session["service_email_from_change"]))
        except HTTPError as e:
            error_msg = "Duplicate email address '{}'".format(session["service_email_from_change"])
            if e.status_code == 400 and error_msg in e.message["email_from"]:
                # Redirect the user back to the change service email_from screen
                flash(_("This email address is already in use"), "error")
                return redirect(url_for("main.service_email_from_change", service_id=service_id))
            else:
                raise e
        else:
            session.pop("service_email_from_change")
            flash(_("Setting updated"), "default_with_tick")
            return redirect(url_for(".service_settings", service_id=service_id))
    return render_template(
        "views/service-settings/confirm.html",
        heading=_("Change your sending email address"),
        form=form,
    )


@main.route("/services/<service_id>/service-settings/request-to-go-live", methods=["GET"])
@user_has_permissions()
@user_is_gov_user
def request_to_go_live(service_id):
    if current_user.has_permissions("manage_service"):
        return render_template("views/service-settings/request-to-go-live.html")
    else:
        return render_template("views/service-settings/request-to-go-live-no-admin.html")


@main.route(
    "/services/<service_id>/service-settings/request-to-go-live/terms-of-use",
    methods=["GET", "POST"],
)
@user_has_permissions("manage_service")
@user_is_gov_user
def terms_of_use(service_id):
    if request.method == "POST":
        service_api_client.accept_tos(service_id)
        return redirect(url_for(".request_to_go_live", service_id=service_id))

    return render_template("views/service-settings/terms-of-use.html")


@main.route(
    "/services/<service_id>/service-settings/request-to-go-live/use-case",
    methods=["GET", "POST"],
)
@user_has_permissions("manage_service")
@user_is_gov_user
def use_case(service_id):
    DEFAULT_STEP = "about-service"
    display_org_question = not current_service.organisation_notes or not current_app.config["FF_SALESFORCE_CONTACT"]
    steps = [
        {
            "form": GoLiveAboutServiceForm if display_org_question else GoLiveAboutServiceFormNoOrg,
            "current_step": DEFAULT_STEP,
            "previous_step": None,
            "next_step": "about-notifications",
            "page_title": _("About your service"),
            "step": 1,
            "back_link": url_for("main.request_to_go_live", service_id=current_service.id),
        },
        {
            "form": GoLiveAboutNotificationsForm if display_org_question else GoLiveAboutNotificationsFormNoOrg,
            "current_step": "about-notifications",
            "previous_step": DEFAULT_STEP,
            "next_step": None,
            "page_title": _("About your notifications"),
            "step": 2,
            "back_link": url_for(
                "main.use_case",
                service_id=current_service.id,
                current_step=DEFAULT_STEP,
            ),
        },
    ]

    step, form_data = current_service.use_case_data

    current_step = request.args.get("current_step", step or DEFAULT_STEP)
    try:
        form_details = [f for f in steps if f["current_step"] == current_step][0]
    except IndexError:
        return redirect(url_for(".request_to_go_live", service_id=service_id))
    form = form_details["form"](data=form_data)

    # Validating the final form
    if form_details["next_step"] is None and form.validate_on_submit():
        current_service.store_use_case_data(form_details["current_step"], form.data)
        current_service.register_submit_use_case()
        return redirect(url_for(".request_to_go_live", service_id=service_id))

    # Going on to the next step in the form
    if form.validate_on_submit():
        possibilities = [f for f in steps if f["previous_step"] == current_step]
        try:
            form_details = possibilities[0]
        except IndexError:
            return redirect(url_for(".request_to_go_live", service_id=service_id))
        form = form_details["form"](data=form_data)

    if request.method == "POST":
        current_service.store_use_case_data(form_details["current_step"], form.data)

    return render_template(
        "views/service-settings/use-case.html",
        form=form,
        page_title=form_details["page_title"],
        next_step=form_details["next_step"],
        current_step=form_details["current_step"],
        previous_step=form_details["previous_step"],
        step_hint=form_details["step"],
        total_steps_hint=len(steps),
        back_link=form_details["back_link"],
        display_org_question=display_org_question,
    )


def send_go_live_request(service, user, go_live_data) -> None:
    go_live_data = go_live_data | {
        "service_name": service.name,
        "service_id": str(service.id),
        "service_url": url_for(".service_dashboard", service_id=service.id, _external=True),
        "support_type": "go_live_request",
        "main_use_case": go_live_data["main_use_case"],
        "name": user.name,
        "email_address": user.email_address,
    }
    of_interest = {
        "service_name",
        "service_id",
        "service_url",
        "name",
        "email_address",
        "department_org_name",
        "intended_recipients",
        "main_use_case",
        "other_use_case",
        "support_type",
        "daily_email_volume",
        "annual_email_volume",
        "daily_sms_volume",
        "annual_sms_volume",
        "exact_daily_email",
        "exact_daily_sms",
    }
    data = {key: go_live_data[key] for key in of_interest if key in go_live_data}
    data["intended_recipients"] = ", ".join(data["intended_recipients"])
    user_api_client.send_contact_request(data)


@main.route("/services/<service_id>/service-settings/request-to-go-live", methods=["POST"])
@user_has_permissions("manage_service")
@user_is_gov_user
def submit_request_to_go_live(service_id):
    if not current_service.go_live_checklist_completed:
        return render_template("views/service-settings/request-to-go-live.html", error=True)

    go_live_data = current_service.use_case_data[1]
    current_service.update(go_live_user=current_user.id)

    flash(_("Your request was submitted."), "default")

    send_go_live_request(current_service, current_user, go_live_data)

    return redirect(url_for(".service_settings", service_id=service_id))


@main.route("/services/<service_id>/service-settings/switch-live", methods=["GET", "POST"])
@user_is_platform_admin
def service_switch_live(service_id):
    form = ServiceOnOffSettingForm(name="Make service live", enabled=not current_service.trial_mode)

    if form.validate_on_submit():
        live = form.enabled.data
        message_limit = current_app.config["DEFAULT_SERVICE_LIMIT"]
        sms_daily_limit = current_app.config["DEFAULT_SMS_DAILY_LIMIT"]

        if live:
            message_limit = current_app.config["DEFAULT_LIVE_SERVICE_LIMIT"]
            sms_daily_limit = current_app.config["DEFAULT_LIVE_SMS_DAILY_LIMIT"]

        flash(_("An email has been sent to service users"), "default_with_tick")

        current_service.update_status(live=live, message_limit=message_limit, sms_daily_limit=sms_daily_limit)
        return redirect(url_for(".service_settings", service_id=service_id))

    return render_template(
        "views/service-settings/set-service-setting.html",
        title="Make service live",
        form=form,
    )


@main.route("/services/<service_id>/service-settings/set-sensitive-service", methods=["GET", "POST"])
@user_is_platform_admin
def set_sensitive_service(service_id):
    title = _("Set sensitive service")
    form = ServiceOnOffSettingForm(name=title, enabled=current_service.sensitive_service)

    if form.validate_on_submit():
        current_service.update(sensitive_service=form.enabled.data)
        return redirect(url_for(".service_settings", service_id=service_id))

    return render_template(
        "views/service-settings/set-service-setting.html",
        title=_("Set sensitive service"),
        form=form,
    )


@main.route(
    "/services/<service_id>/service-settings/switch-upload-document",
    methods=["GET", "POST"],
)
@user_has_permissions("manage_service")
def service_switch_upload_document(service_id):
    title = _("Send files by email")
    form = ServiceOnOffSettingForm(name=title, enabled=current_service.has_permission("upload_document"))
    help = _(
        "This feature is only available when sending through the API.<br>" "Learn more in the <a href='{}'>API documentation</a>."
    ).format(documentation_url("send", section="sending-a-file-by-email"))

    if form.validate_on_submit():
        current_service.force_permission("upload_document", on=form.enabled.data)
        flash(_("Setting updated"), "default_with_tick")
        return redirect(url_for(".service_settings", service_id=service_id))

    return render_template(
        "views/service-settings/set-service-setting.html",
        title=title,
        form=form,
        help=help,
    )


@main.route(
    "/services/<service_id>/service-settings/switch-count-as-live",
    methods=["GET", "POST"],
)
@user_is_platform_admin
def service_switch_count_as_live(service_id):
    form = ServiceOnOffSettingForm(
        name="Count in list of live services",
        enabled=current_service.count_as_live,
        truthy="Yes",
        falsey="No",
    )

    if form.validate_on_submit():
        current_service.update_count_as_live(form.enabled.data)
        return redirect(url_for(".service_settings", service_id=service_id))

    return render_template(
        "views/service-settings/set-service-setting.html",
        title="Count in list of live services",
        form=form,
    )


@main.route(
    "/services/<service_id>/service-settings/permissions/<permission>",
    methods=["GET", "POST"],
)
@user_is_platform_admin
def service_set_permission(service_id, permission):
    if permission not in PLATFORM_ADMIN_SERVICE_PERMISSIONS:
        abort(404)

    title = PLATFORM_ADMIN_SERVICE_PERMISSIONS[permission]["title"]
    form = ServiceOnOffSettingForm(name=title, enabled=current_service.has_permission(permission))

    if form.validate_on_submit():
        current_service.force_permission(permission, on=form.enabled.data)

        return redirect(url_for(".service_settings", service_id=service_id))

    return render_template(
        "views/service-settings/set-service-setting.html",
        title=title,
        form=form,
    )


@main.route("/services/<service_id>/service-settings/archive", methods=["GET", "POST"])
@user_has_permissions("manage_service")
def archive_service(service_id):
    if not current_service.active and (current_service.trial_mode or current_user.platform_admin):
        abort(403)
    if request.method == "POST":
        service_api_client.archive_service(service_id)
        session.pop("service_id", None)
        flash(
            _("‘%(service_name)s’ was deleted", service_name=current_service.name),
            "default_with_tick",
        )
        return redirect(url_for(".choose_account"))
    else:
        flash(
            "{} ‘{}’? {}".format(
                _("Are you sure you want to delete"),
                current_service.name,
                _("There’s no way to undo this."),
            ),
            "delete",
        )
        return service_settings(service_id)


@main.route("/services/<service_id>/service-settings/suspend", methods=["GET", "POST"])
@user_has_permissions("manage_service")
def suspend_service(service_id):
    if request.method == "POST":
        service_api_client.suspend_service(service_id)
        return redirect(url_for(".service_settings", service_id=service_id))
    else:
        flash(
            _("This will suspend the service and revoke all API keys. Are you sure you want to suspend this service?"),
            "suspend",
        )
        return service_settings(service_id)


@main.route("/services/<service_id>/service-settings/resume", methods=["GET", "POST"])
@user_has_permissions("manage_service")
def resume_service(service_id):
    if request.method == "POST":
        service_api_client.resume_service(service_id)
        return redirect(url_for(".service_settings", service_id=service_id))
    else:
        flash(
            _("This will resume the service. New API keys are required for this service to use the API"),
            "resume",
        )
        return service_settings(service_id)


@main.route("/services/<service_id>/service-settings/set-reply-to-email", methods=["GET"])
@user_has_permissions("manage_service")
def service_set_reply_to_email(service_id):
    return redirect(url_for(".service_email_reply_to", service_id=service_id))


@main.route("/services/<service_id>/service-settings/sending-domain", methods=["GET", "POST"])
@user_is_platform_admin
def service_sending_domain(service_id):
    form = SendingDomainForm(sending_domain_choices=get_verified_ses_domains())

    if request.method == "GET":
        form.sending_domain.data = current_service.sending_domain

    if form.validate_on_submit():
        current_service.update(sending_domain=form.sending_domain.data)
        flash(_("Sending domain updated"), "default")
        return redirect(url_for(".service_settings", service_id=service_id))

    default_sending = current_app.config["SENDING_DOMAIN"]
    template = "views/service-settings/sending_domain.html"
    return render_template(template, service_id=service_id, sending_domain=default_sending, form=form)


@main.route("/services/<service_id>/service-settings/email-reply-to", methods=["GET"])
@user_has_permissions("manage_service", "manage_api_keys")
def service_email_reply_to(service_id):
    return render_template("views/service-settings/email_reply_to.html")


@main.route(
    "/services/<service_id>/service-settings/email-reply-to/add",
    methods=["GET", "POST"],
)
@user_has_permissions("manage_service")
def service_add_email_reply_to(service_id):
    form = ServiceReplyToEmailForm()
    first_email_address = current_service.count_email_reply_to_addresses == 0
    is_default = first_email_address if first_email_address else form.is_default.data
    if form.validate_on_submit():
        try:
            notification_id = service_api_client.verify_reply_to_email_address(service_id, form.email_address.data)["data"]["id"]
        except HTTPError as e:
            error_msg = "Your service already uses '{}' as an email reply-to address.".format(form.email_address.data)
            if e.status_code == 400 and error_msg == e.message:
                flash(error_msg, "error")
                return redirect(url_for(".service_email_reply_to", service_id=service_id))
            else:
                raise e
        return redirect(
            url_for(
                ".service_verify_reply_to_address",
                service_id=service_id,
                notification_id=notification_id,
                is_default=is_default,
            )
        )

    return render_template(
        "views/service-settings/email-reply-to/add.html",
        form=form,
        first_email_address=first_email_address,
    )


@main.route(
    "/services/<service_id>/service-settings/email-reply-to/<notification_id>/verify",
    methods=["GET", "POST"],
)
@user_has_permissions("manage_service")
def service_verify_reply_to_address(service_id, notification_id):
    replace = request.args.get("replace", False)
    is_default = request.args.get("is_default", False)
    return render_template(
        "views/service-settings/email-reply-to/verify.html",
        service_id=service_id,
        notification_id=notification_id,
        partials=get_service_verify_reply_to_address_partials(service_id, notification_id),
        verb=(_("Change") if replace else _("Add")),
        replace=replace,
        is_default=is_default,
    )


@main.route("/services/<service_id>/service-settings/email-reply-to/<notification_id>/verify.json")
@user_has_permissions("manage_service")
def service_verify_reply_to_address_updates(service_id, notification_id):
    return jsonify(**get_service_verify_reply_to_address_partials(service_id, notification_id))


def get_service_verify_reply_to_address_partials(service_id, notification_id):
    form = ServiceReplyToEmailForm()
    first_email_address = current_service.count_email_reply_to_addresses == 0
    notification = notification_api_client.get_notification(current_app.config["NOTIFY_SERVICE_ID"], notification_id)
    replace = request.args.get("replace", False)
    replace = False if replace == "False" else replace
    existing_is_default = False
    if replace:
        existing = current_service.get_email_reply_to_address(replace)
        existing_is_default = existing["is_default"]
    verification_status = "pending"
    is_default = True if (request.args.get("is_default", False) == "True") else False
    if notification["status"] in DELIVERED_STATUSES:
        verification_status = "success"
        if notification["to"] not in [i["email_address"] for i in current_service.email_reply_to_addresses]:
            if replace:
                service_api_client.update_reply_to_email_address(
                    current_service.id,
                    replace,
                    email_address=notification["to"],
                    is_default=is_default,
                )
            else:
                service_api_client.add_reply_to_email_address(
                    current_service.id,
                    email_address=notification["to"],
                    is_default=is_default,
                )
    created_at_no_tz = notification["created_at"][:-6]
    seconds_since_sending = (datetime.utcnow() - datetime.strptime(created_at_no_tz, "%Y-%m-%dT%H:%M:%S.%f")).seconds
    if notification["status"] in FAILURE_STATUSES or (notification["status"] in SENDING_STATUSES and seconds_since_sending > 45):
        verification_status = "failure"
        form.email_address.data = notification["to"]
        form.is_default.data = is_default
    return {
        "status": render_template(
            "views/service-settings/email-reply-to/_verify-updates.html",
            reply_to_email_address=notification["to"],
            service_id=current_service.id,
            notification_id=notification_id,
            verification_status=verification_status,
            is_default=is_default,
            existing_is_default=existing_is_default,
            form=form,
            first_email_address=first_email_address,
            replace=replace,
        ),
        "stop": 0 if verification_status == "pending" else 1,
    }


@main.route(
    "/services/<service_id>/service-settings/email-reply-to/<reply_to_email_id>/edit",
    methods=["GET", "POST"],
    endpoint="service_edit_email_reply_to",
)
@main.route(
    "/services/<service_id>/service-settings/email-reply-to/<reply_to_email_id>/delete",
    methods=["GET"],
    endpoint="service_confirm_delete_email_reply_to",
)
@user_has_permissions("manage_service")
def service_edit_email_reply_to(service_id, reply_to_email_id):
    form = ServiceReplyToEmailForm()
    reply_to_email_address = current_service.get_email_reply_to_address(reply_to_email_id)
    if request.method == "GET":
        form.email_address.data = reply_to_email_address["email_address"]
        form.is_default.data = reply_to_email_address["is_default"]
    if form.validate_on_submit():
        if form.email_address.data == reply_to_email_address["email_address"]:
            service_api_client.update_reply_to_email_address(
                current_service.id,
                reply_to_email_id=reply_to_email_id,
                email_address=form.email_address.data,
                is_default=True if reply_to_email_address["is_default"] else form.is_default.data,
            )
            return redirect(url_for(".service_email_reply_to", service_id=service_id))
        try:
            notification_id = service_api_client.verify_reply_to_email_address(service_id, form.email_address.data)["data"]["id"]
        except HTTPError as e:
            # TODO: missing translation
            error_msg = "Your service already uses ‘{}’ as a reply-to email address.".format(form.email_address.data)
            if e.status_code == 400 and error_msg == e.message:
                flash(error_msg, "error")
                return redirect(url_for(".service_email_reply_to", service_id=service_id))
            else:
                raise e
        return redirect(
            url_for(
                ".service_verify_reply_to_address",
                service_id=service_id,
                notification_id=notification_id,
                is_default=True if reply_to_email_address["is_default"] else form.is_default.data,
                replace=reply_to_email_id,
            )
        )

    if reply_to_email_address and request.endpoint == "main.service_confirm_delete_email_reply_to":
        if not reply_to_email_address["is_default"]:
            flash(_("Are you sure you want to delete this reply-to email address?"), "delete")
        elif current_service.count_email_reply_to_addresses == 1:
            flash(_("You're about to delete your default reply-to address."), "delete")
        elif current_service.email_reply_to_addresses and current_service.count_email_reply_to_addresses > 1:
            new_default_reply_to_address = get_new_default_reply_to_address(
                current_service.email_reply_to_addresses, reply_to_email_address
            )
            # type: ignore
            email_address = new_default_reply_to_address["email_address"]
            message: str = _("You're about to delete your default reply-to address.") + _(
                " The new default will be the next email on your list of reply-to addresses: ‘{}’"
            ).format(email_address)
            flash(message, "delete")
    return render_template(
        "views/service-settings/email-reply-to/edit.html",
        form=form,
        reply_to_email_address_id=reply_to_email_id,
    )


@main.route(
    "/services/<service_id>/service-settings/email-reply-to/<reply_to_email_id>/delete",
    methods=["POST"],
)
@user_has_permissions("manage_service")
def service_delete_email_reply_to(service_id, reply_to_email_id):
    reply_to_email_address = current_service.get_email_reply_to_address(reply_to_email_id)

    # if this is the default, and other reply-tos exist, we need to switch the default before deleting
    if reply_to_email_address and reply_to_email_address["is_default"] and current_service.count_email_reply_to_addresses > 1:
        new_default_reply_to_address = get_new_default_reply_to_address(
            current_service.email_reply_to_addresses, reply_to_email_address
        )
        if new_default_reply_to_address:
            service_api_client.update_reply_to_email_address(
                current_service.id,
                reply_to_email_id=new_default_reply_to_address["id"],
                email_address=new_default_reply_to_address["email_address"],
                is_default=True,
            )

    service_api_client.delete_reply_to_email_address(
        service_id=current_service.id,
        reply_to_email_id=reply_to_email_id,
    )
    return redirect(url_for(".service_email_reply_to", service_id=service_id))


@main.route(
    "/services/<service_id>/service-settings/set-inbound-number",
    methods=["GET", "POST"],
)
@user_has_permissions("manage_service")
def service_set_inbound_number(service_id):
    available_inbound_numbers = inbound_number_client.get_available_inbound_sms_numbers()
    inbound_numbers_value_and_label = [(number["id"], number["number"]) for number in available_inbound_numbers["data"]]
    no_available_numbers = available_inbound_numbers["data"] == []
    form = ServiceInboundNumberForm(inbound_number_choices=inbound_numbers_value_and_label)

    if form.validate_on_submit():
        service_api_client.add_sms_sender(
            current_service.id,
            sms_sender=form.inbound_number.data,
            is_default=True,
            inbound_number_id=form.inbound_number.data,
        )
        current_service.force_permission("inbound_sms", on=True)
        return redirect(url_for(".service_settings", service_id=service_id))

    return render_template(
        "views/service-settings/set-inbound-number.html",
        form=form,
        no_available_numbers=no_available_numbers,
    )


@main.route("/services/<service_id>/service-settings/sms-prefix", methods=["GET", "POST"])
@user_has_permissions("manage_service")
def service_set_sms_prefix(service_id):
    form = SMSPrefixForm(enabled=("on" if current_service.prefix_sms else "off"))

    form.enabled.label.text = "{} ‘{}:’".format(_("Start all text messages with"), current_service.name)

    if form.validate_on_submit():
        current_service.update(prefix_sms=(form.enabled.data == "on"))
        return redirect(url_for(".service_settings", service_id=service_id))

    return render_template("views/service-settings/sms-prefix.html", form=form)


@main.route(
    "/services/<service_id>/service-settings/set-international-sms",
    methods=["GET", "POST"],
)
@user_has_permissions("manage_service")
def service_set_international_sms(service_id):
    form = InternationalSMSForm(enabled="on" if current_service.has_permission("international_sms") else "off")
    if form.validate_on_submit():
        current_service.force_permission(
            "international_sms",
            on=(form.enabled.data == "on"),
        )
        return redirect(url_for(".service_settings", service_id=service_id))
    return render_template(
        "views/service-settings/set-international-sms.html",
        form=form,
    )


@main.route("/services/<service_id>/service-settings/set-inbound-sms", methods=["GET"])
@user_has_permissions("manage_service")
def service_set_inbound_sms(service_id):
    return render_template(
        "views/service-settings/set-inbound-sms.html",
    )


@main.route("/services/<service_id>/service-settings/set-letters", methods=["GET"])
@user_has_permissions("manage_service")
def service_set_letters(service_id):
    return redirect(
        url_for(
            ".service_set_channel",
            service_id=current_service.id,
            channel="letter",
        ),
        code=301,
    )


@main.route("/services/<service_id>/service-settings/set-<channel>", methods=["GET", "POST"])
@user_has_permissions("manage_service")
def service_set_channel(service_id, channel):
    if channel not in {"email", "sms", "letter"}:
        abort(404)

    form = ServiceSwitchChannelForm(channel=channel, enabled=current_service.has_permission(channel))

    if form.validate_on_submit():
        current_service.force_permission(
            channel,
            on=form.enabled.data,
        )
        flash(_("Setting updated"), "default_with_tick")
        return redirect(url_for(".service_settings", service_id=service_id))

    return render_template(
        "views/service-settings/set-{}.html".format(channel),
        form=form,
        limits={
            "free_yearly_email": current_app.config["FREE_YEARLY_EMAIL_LIMIT"],
            "free_yearly_sms": current_app.config["FREE_YEARLY_SMS_LIMIT"],
        },
    )


@main.route("/services/<service_id>/service-settings/set-auth-type", methods=["GET"])
@user_has_permissions("manage_service")
def service_set_auth_type(service_id):
    return render_template(
        "views/service-settings/set-auth-type.html",
    )


@main.route("/services/<service_id>/service-settings/letter-contacts", methods=["GET"])
@user_has_permissions("manage_service", "manage_api_keys")
def service_letter_contact_details(service_id):
    letter_contact_details = service_api_client.get_letter_contacts(service_id)
    return render_template(
        "views/service-settings/letter-contact-details.html",
        letter_contact_details=letter_contact_details,
    )


@main.route(
    "/services/<service_id>/service-settings/letter-contact/add",
    methods=["GET", "POST"],
)
@user_has_permissions("manage_service")
def service_add_letter_contact(service_id):
    form = ServiceLetterContactBlockForm()
    first_contact_block = current_service.count_letter_contact_details == 0
    from_template = request.args.get("from_template")
    if form.validate_on_submit():
        new_letter_contact = service_api_client.add_letter_contact(
            current_service.id,
            contact_block=form.letter_contact_block.data.replace("\r", "") or None,
            is_default=first_contact_block if first_contact_block else form.is_default.data,
        )
        if from_template:
            service_api_client.update_service_template_sender(
                service_id,
                from_template,
                new_letter_contact["data"]["id"],
            )
            return redirect(url_for(".view_template", service_id=service_id, template_id=from_template))
        return redirect(url_for(".service_letter_contact_details", service_id=service_id))
    return render_template(
        "views/service-settings/letter-contact/add.html",
        form=form,
        first_contact_block=first_contact_block,
        back_link=(
            url_for(
                "main.view_template",
                template_id=from_template,
                service_id=current_service.id,
            )
            if from_template
            else url_for(".service_letter_contact_details", service_id=current_service.id)
        ),
    )


@main.route(
    "/services/<service_id>/service-settings/letter-contact/<letter_contact_id>/edit",
    methods=["GET", "POST"],
    endpoint="service_edit_letter_contact",
)
@main.route(
    "/services/<service_id>/service-settings/letter-contact/<letter_contact_id>/delete",
    methods=["GET"],
    endpoint="service_confirm_delete_letter_contact",
)
@user_has_permissions("manage_service")
def service_edit_letter_contact(service_id, letter_contact_id):
    letter_contact_block = current_service.get_letter_contact_block(letter_contact_id)
    form = ServiceLetterContactBlockForm(letter_contact_block=letter_contact_block["contact_block"])
    if request.method == "GET":
        form.is_default.data = letter_contact_block["is_default"]
    if form.validate_on_submit():
        current_service.edit_letter_contact_block(
            id=letter_contact_id,
            contact_block=form.letter_contact_block.data.replace("\r", "") or None,
            is_default=letter_contact_block["is_default"] or form.is_default.data,
        )
        return redirect(url_for(".service_letter_contact_details", service_id=service_id))

    if request.endpoint == "main.service_confirm_delete_letter_contact":
        flash(_("Are you sure you want to delete this contact block?"), "delete")
    return render_template(
        "views/service-settings/letter-contact/edit.html",
        form=form,
        letter_contact_id=letter_contact_block["id"],
    )


@main.route("/services/<service_id>/service-settings/letter-contact/make-blank-default")
@user_has_permissions("manage_service")
def service_make_blank_default_letter_contact(service_id):
    current_service.remove_default_letter_contact_block()
    return redirect(url_for(".service_letter_contact_details", service_id=service_id))


@main.route("/services/<service_id>/service-settings/letter-contact/<letter_contact_id>/delete", methods=["POST"])
@user_has_permissions("manage_service")
def service_delete_letter_contact(service_id, letter_contact_id):
    service_api_client.delete_letter_contact(
        service_id=current_service.id,
        letter_contact_id=letter_contact_id,
    )
    return redirect(url_for(".service_letter_contact_details", service_id=current_service.id))


@main.route("/services/<service_id>/service-settings/sms-sender", methods=["GET"])
@user_is_platform_admin
def service_sms_senders(service_id):
    return render_template(
        "views/service-settings/sms-senders.html",
    )


@main.route("/services/<service_id>/service-settings/sms-sender/add", methods=["GET", "POST"])
@user_is_platform_admin
def service_add_sms_sender(service_id):
    form = ServiceSmsSenderForm()
    first_sms_sender = current_service.count_sms_senders == 0
    if form.validate_on_submit():
        service_api_client.add_sms_sender(
            current_service.id,
            sms_sender=form.sms_sender.data.replace("\r", "") or None,
            is_default=first_sms_sender if first_sms_sender else form.is_default.data,
        )
        return redirect(url_for(".service_sms_senders", service_id=service_id))
    return render_template(
        "views/service-settings/sms-sender/add.html",
        form=form,
        first_sms_sender=first_sms_sender,
    )


@main.route(
    "/services/<service_id>/service-settings/sms-sender/<sms_sender_id>/edit",
    methods=["GET", "POST"],
    endpoint="service_edit_sms_sender",
)
@main.route(
    "/services/<service_id>/service-settings/sms-sender/<sms_sender_id>/delete",
    methods=["GET"],
    endpoint="service_confirm_delete_sms_sender",
)
@user_is_platform_admin
def service_edit_sms_sender(service_id, sms_sender_id):
    sms_sender = current_service.get_sms_sender(sms_sender_id)
    is_inbound_number = sms_sender["inbound_number_id"]
    if is_inbound_number:
        form = ServiceEditInboundNumberForm(is_default=sms_sender["is_default"])
    else:
        form = ServiceSmsSenderForm(**sms_sender)

    if form.validate_on_submit():
        service_api_client.update_sms_sender(
            current_service.id,
            sms_sender_id=sms_sender_id,
            sms_sender=(sms_sender["sms_sender"] if is_inbound_number else form.sms_sender.data.replace("\r", "")),
            is_default=True if sms_sender["is_default"] else form.is_default.data,
        )
        return redirect(url_for(".service_sms_senders", service_id=service_id))

    form.is_default.data = sms_sender["is_default"]
    if request.endpoint == "main.service_confirm_delete_sms_sender":
        flash(_("Are you sure you want to delete this text message sender?"), "delete")
    return render_template(
        "views/service-settings/sms-sender/edit.html",
        form=form,
        sms_sender=sms_sender,
        inbound_number=is_inbound_number,
        sms_sender_id=sms_sender_id,
    )


@main.route(
    "/services/<service_id>/service-settings/sms-sender/<sms_sender_id>/delete",
    methods=["POST"],
)
@user_has_permissions("manage_service")
def service_delete_sms_sender(service_id, sms_sender_id):
    service_api_client.delete_sms_sender(
        service_id=current_service.id,
        sms_sender_id=sms_sender_id,
    )
    return redirect(url_for(".service_sms_senders", service_id=service_id))


@main.route(
    "/services/<service_id>/service-settings/set-letter-contact-block",
    methods=["GET", "POST"],
)
@user_has_permissions("manage_service")
def service_set_letter_contact_block(service_id):
    if not current_service.has_permission("letter"):
        abort(403)

    form = ServiceLetterContactBlockForm(letter_contact_block=current_service.letter_contact_block)
    if form.validate_on_submit():
        current_service.update(letter_contact_block=form.letter_contact_block.data.replace("\r", "") or None)
        if request.args.get("from_template"):
            return redirect(
                url_for(
                    ".view_template",
                    service_id=service_id,
                    template_id=request.args.get("from_template"),
                )
            )
        return redirect(url_for(".service_settings", service_id=service_id))
    return render_template("views/service-settings/set-letter-contact-block.html", form=form)


@main.route("/services/<service_id>/service-settings/set-message-limit", methods=["GET", "POST"])
@user_is_platform_admin
def set_message_limit(service_id):
    form = MessageLimit(message_limit=current_service.message_limit)

    if form.validate_on_submit():
        service_api_client.update_message_limit(service_id, form.message_limit.data)
        if current_service.live:
            flash(_("An email has been sent to service users"), "default_with_tick")
        return redirect(url_for(".service_settings", service_id=service_id))

    return render_template("views/service-settings/set-message-limit.html", form=form, heading=_("Daily email limit"))


@main.route("/services/<service_id>/service-settings/set-sms-message-limit", methods=["GET", "POST"])
@user_is_platform_admin
def set_sms_message_limit(service_id):
    form = SMSMessageLimit(message_limit=current_service.sms_daily_limit)

    if form.validate_on_submit():
        service_api_client.update_sms_message_limit(service_id, form.message_limit.data)
        if current_service.live:
            flash(_("An email has been sent to service users"), "default_with_tick")
        return redirect(url_for(".service_settings", service_id=service_id))

    return render_template(
        "views/service-settings/set-message-limit.html",
        form=form,
        heading=_("Daily text message limit"),
    )


@main.route("/service/<service_id>/service_settings/set-sms-annual-limit", methods=["GET", "POST"])
@user_is_platform_admin
def set_sms_annual_limit(service_id):
    form = SMSAnnualMessageLimit(message_limit=current_service.sms_annual_limit)

    if form.validate_on_submit():
        service_api_client.update_sms_annual_limit(service_id, form.message_limit.data)
        if current_service.live:
            flash(_("An email has been sent to service users"), "default_with_tick")
        return redirect(url_for(".service_settings", service_id=service_id))

    return render_template(
        "views/service-settings/set-message-limit.html",
        form=form,
        heading=_("Annual text message limit"),
    )


@main.route("/service/<service_id>/service_settings/set-email-annual.html", methods=["GET", "POST"])
@user_is_platform_admin
def set_email_annual_limit(service_id):
    form = EmailAnnualMessageLimit(message_limit=current_service.email_annual_limit)

    if form.validate_on_submit():
        service_api_client.update_email_annual_limit(service_id, form.message_limit.data)
        if current_service.live:
            flash(_("An email has been sent to service users"), "default_with_tick")
        return redirect(url_for(".service_settings", service_id=service_id))

    return render_template(
        "views/service-settings/set-message-limit.html",
        form=form,
        heading=_("Annual email limit"),
    )


@main.route("/services/<service_id>/service-settings/set-free-sms-allowance", methods=["GET", "POST"])
@user_is_platform_admin
def set_free_sms_allowance(service_id):
    form = FreeSMSAllowance(free_sms_allowance=current_service.free_sms_fragment_limit)

    if form.validate_on_submit():
        billing_api_client.create_or_update_free_sms_fragment_limit(service_id, form.free_sms_allowance.data)

        return redirect(url_for(".service_settings", service_id=service_id))

    return render_template(
        "views/service-settings/set-free-sms-allowance.html",
        form=form,
    )


@main.route(
    "/services/<service_id>/service-settings/set-email-branding",
    methods=["GET", "POST"],
)
@user_is_platform_admin
def service_set_email_branding(service_id):
    organisation_id = current_service.organisation_id
    email_branding = email_branding_client.get_all_email_branding(organisation_id=organisation_id)
    # As the user is a platform admin, we want the user to be able to get the no branding option
    no_branding = email_branding_client.get_email_branding(current_app.config["NO_BRANDING_ID"])
    if no_branding and "email_branding" in no_branding:
        email_branding.append(no_branding["email_branding"])

    current_branding = current_service.email_branding_id
    if current_branding is None:
        current_branding = (
            FieldWithLanguageOptions.FRENCH_OPTION_VALUE
            if current_service.default_branding_is_french is True
            else FieldWithLanguageOptions.ENGLISH_OPTION_VALUE
        )

    form = SetEmailBranding(
        all_branding_options=get_branding_as_value_and_label(email_branding),
        current_branding=current_branding,
    )

    if form.validate_on_submit():
        return redirect(
            url_for(
                ".service_preview_email_branding",
                service_id=service_id,
                branding_style=form.branding_style.data,
            )
        )

    return render_template(
        "views/service-settings/set-email-branding.html",
        form=form,
        search_form=SearchByNameForm(),
    )


@main.route(
    "/services/<service_id>/service-settings/preview-email-branding",
    methods=["GET", "POST"],
)
@user_is_platform_admin
def service_preview_email_branding(service_id):
    branding_style = request.args.get("branding_style", None)

    form = PreviewBranding(branding_style=branding_style)

    default_branding_is_french = None

    if form.branding_style.data == FieldWithLanguageOptions.ENGLISH_OPTION_VALUE:
        default_branding_is_french = False
    elif form.branding_style.data == FieldWithLanguageOptions.FRENCH_OPTION_VALUE:
        default_branding_is_french = True

    if form.validate_on_submit():
        if default_branding_is_french is not None:
            current_service.update(
                email_branding=None,
                default_branding_is_french=default_branding_is_french,
            )
        else:
            current_service.update(email_branding=form.branding_style.data)
        return redirect(url_for(".service_settings", service_id=service_id))

    return render_template(
        "views/service-settings/preview-email-branding.html",
        form=form,
        service_id=service_id,
        action=url_for("main.service_preview_email_branding", service_id=service_id),
    )


@main.route(
    "/services/<service_id>/service-settings/set-letter-branding",
    methods=["GET", "POST"],
)
@user_is_platform_admin
def service_set_letter_branding(service_id):
    letter_branding = letter_branding_client.get_all_letter_branding()

    form = SetLetterBranding(
        all_branding_options=get_branding_as_value_and_label(letter_branding),
        current_branding=current_service.letter_branding_id,
    )

    if form.validate_on_submit():
        return redirect(
            url_for(
                ".service_preview_letter_branding",
                service_id=service_id,
                branding_style=form.branding_style.data,
            )
        )

    return render_template(
        "views/service-settings/set-letter-branding.html",
        form=form,
        search_form=SearchByNameForm(),
    )


@main.route(
    "/services/<service_id>/service-settings/preview-letter-branding",
    methods=["GET", "POST"],
)
@user_is_platform_admin
def service_preview_letter_branding(service_id):
    branding_style = request.args.get("branding_style")

    form = PreviewBranding(branding_style=branding_style)

    if form.validate_on_submit():
        current_service.update(letter_branding=form.branding_style.data)
        return redirect(url_for(".service_settings", service_id=service_id))

    return render_template(
        "views/service-settings/preview-letter-branding.html",
        form=form,
        service_id=service_id,
        action=url_for("main.service_preview_letter_branding", service_id=service_id),
    )


@main.route(
    "/services/<service_id>/service-settings/request-letter-branding",
    methods=["GET", "POST"],
)
@user_has_permissions("manage_service", "manage_templates")
def request_letter_branding(service_id):
    return render_template(
        "views/service-settings/request-letter-branding.html",
        from_template=request.args.get("from_template"),
    )


@main.route(
    "/services/<service_id>/service-settings/link-service-to-organisation",
    methods=["GET", "POST"],
)
@user_is_platform_admin
def link_service_to_organisation(service_id):
    all_organisations = organisations_client.get_organisations()
    current_linked_organisation = organisations_client.get_service_organisation(service_id).get("id", None)

    form = LinkOrganisationsForm(
        choices=convert_dictionary_to_wtforms_choices_format(all_organisations, "id", "name"),
        organisations=current_linked_organisation,
    )

    if form.validate_on_submit():
        if form.organisations.data != current_linked_organisation:
            organisations_client.update_service_organisation(service_id, form.organisations.data)
        return redirect(url_for(".service_settings", service_id=service_id))

    return render_template(
        "views/service-settings/link-service-to-organisation.html",
        has_organisations=all_organisations,
        form=form,
        search_form=SearchByNameForm(),
    )


@main.route("/services/<service_id>/branding", methods=["GET"])
@user_has_permissions("manage_service")
def view_branding_settings(service_id):
    def _get_current_branding():
        """
        Get the current branding information for the service.

        This function retrieves the current branding information for the service from the service table.
        It checks if the default branding is set to French and constructs the branding image path accordingly.
        If the current branding is not set, it uses the default branding image path based on the default language.

        Returns:
            dict: A dictionary containing the branding image path and branding name.
                - branding_image_path (str): The URL of the branding image.
                - branding_name (str): The name of the branding.
        """
        current_branding = current_service.email_branding_id
        cdn_url = get_logo_cdn_domain()
        default_en_filename = "https://{}/gc-logo-en.png".format(cdn_url)
        default_fr_filename = "https://{}/gc-logo-fr.png".format(cdn_url)

        if current_branding is None:
            branding_image_path = default_fr_filename if current_service.default_branding_is_french else default_en_filename
        else:
            branding_image_path = "https://{}/{}".format(cdn_url, current_service.email_branding["logo"])

        return {"branding_image_path": branding_image_path, "branding_name": current_service.email_branding_name}

    branding = _get_current_branding()

    return render_template(
        "views/service-settings/branding/branding-settings.html",
        branding=branding,
        current_service=current_service,
        template=get_preview_template(),
    )


@main.route("/services/<service_id>/branding-request/email", methods=["GET", "POST"])
@user_has_permissions("manage_service")
def branding_request(service_id):
    current_branding = current_service.email_branding_id
    cdn_url = get_logo_cdn_domain()
    default_en_filename = "https://{}/gov-canada-en.svg".format(cdn_url)
    default_fr_filename = "https://{}/gov-canada-fr.svg".format(cdn_url)

    choices = [
        ("__FIP-EN__", _("English-first") + "||" + default_en_filename),
        ("__FIP-FR__", _("French-first") + "||" + default_fr_filename),
    ]
    if current_branding is None:
        current_branding = (
            FieldWithLanguageOptions.FRENCH_OPTION_VALUE
            if current_service.default_branding_is_french is True
            else FieldWithLanguageOptions.ENGLISH_OPTION_VALUE
        )
        branding_style = current_branding
    else:
        current_branding_filename = "https://{}/{}".format(cdn_url, current_service.email_branding["logo"])
        branding_style = "custom"
        choices.append(
            (
                "custom",
                _("Custom {} logo").format(current_service.name) + "||" + current_branding_filename,
            )
        )

    form = SelectLogoForm(
        label=_("Type of logo"),
        choices=choices,
        branding_style=branding_style,
    )
    upload_filename = None
    if form.validate_on_submit():
        file_submitted = form.file.data
        if file_submitted:
            upload_filename = upload_email_logo(
                file_submitted.filename,
                file_submitted,
                current_app.config["AWS_REGION"],
                user_id=session["user_id"],
            )
            current_user.send_branding_request(
                current_service.id,
                current_service.name,
                current_service.organisation_id,
                current_service.organisation.name,
                upload_filename,
            )

        default_branding_is_french = None
        branding_choice = form.branding_style.data
        if branding_choice == "custom" or file_submitted:
            default_branding_is_french = None
        else:
            default_branding_is_french = branding_choice == FieldWithLanguageOptions.FRENCH_OPTION_VALUE

        if default_branding_is_french is not None:
            current_service.update(
                email_branding=None,
                default_branding_is_french=default_branding_is_french,
            )
            flash(_("Setting updated"), "default_with_tick")
            return redirect(url_for(".service_settings", service_id=service_id))

    return render_template(
        "views/service-settings/branding/manage-email-branding.html",
        form=form,
        using_custom_branding=current_service.email_branding_id is not None,
        cdn_url=cdn_url,
        upload_filename=upload_filename,
    )


@main.route("/services/<service_id>/data-retention", methods=["GET"])
@user_is_platform_admin
def data_retention(service_id):
    return render_template(
        "views/service-settings/data-retention.html",
    )


@main.route("/services/<service_id>/data-retention/add", methods=["GET", "POST"])
@user_is_platform_admin
def add_data_retention(service_id):
    form = ServiceDataRetentionForm()
    if form.validate_on_submit():
        service_api_client.create_service_data_retention(service_id, form.notification_type.data, form.days_of_retention.data)
        return redirect(url_for(".data_retention", service_id=service_id))
    return render_template("views/service-settings/data-retention/add.html", form=form)


@main.route(
    "/services/<service_id>/data-retention/<data_retention_id>/edit",
    methods=["GET", "POST"],
)
@user_is_platform_admin
def edit_data_retention(service_id, data_retention_id):
    data_retention_item = current_service.get_data_retention_item(data_retention_id)
    form = ServiceDataRetentionEditForm(days_of_retention=data_retention_item["days_of_retention"])
    if form.validate_on_submit():
        service_api_client.update_service_data_retention(service_id, data_retention_id, form.days_of_retention.data)
        return redirect(url_for(".data_retention", service_id=service_id))
    return render_template(
        "views/service-settings/data-retention/edit.html",
        form=form,
        data_retention_id=data_retention_id,
        notification_type=data_retention_item["notification_type"],
    )


@main.route(
    "/services/<service_id>/service-settings/suspend-callback",
    methods=["GET", "POST"],
)
@user_is_platform_admin
def suspend_callback(service_id):
    title = _("Suspend Callback")
    form = ServiceOnOffSettingForm(name=title)
    if current_service.service_callback_api:
        callback_api = service_api_client.get_service_callback_api(current_service.id, current_service.service_callback_api[0])
        form = ServiceOnOffSettingForm(name=title, enabled=callback_api["is_suspended"])

        if form.validate_on_submit():
            try:
                service_api_client.suspend_service_callback_api(service_id, current_user.id, suspend_unsuspend=form.enabled.data)
            except Exception as e:
                raise "Error suspending callback: {}".format(e)
            return redirect(url_for(".service_settings", service_id=service_id))

        return render_template(
            "views/service-settings/set-service-setting.html",
            title=_("Suspend Callback"),
            form=form,
        )
    return render_template(
        "views/service-settings/set-service-setting.html",
        title=_("Suspend Callback"),
        form=form,
    )


def get_branding_as_value_and_label(email_branding):
    return [(branding["id"], branding["name"]) for branding in email_branding]


def convert_dictionary_to_wtforms_choices_format(dictionary, value, label):
    return [(item[value], item[label]) for item in dictionary]


def check_contact_details_type(contact_details):
    if contact_details.startswith("http"):
        return "url"
    elif "@" in contact_details:
        return "email_address"
    else:
        return "phone_number"
