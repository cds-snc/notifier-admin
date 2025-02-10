from flask import (
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_babel import lazy_gettext as _l
from flask_login import current_user
from notifications_python_client.errors import HTTPError

from app import current_service, service_api_client
from app.event_handlers import (
    create_email_change_event,
    create_mobile_number_change_event,
)
from app.main import main
from app.main.forms import (
    ChangeEmailForm,
    ChangeMobileNumberForm,
    ChangeNonGovEmailForm,
    InviteUserForm,
    PermissionsForm,
    SearchUsersForm,
)
from app.models.roles_and_permissions import permissions
from app.models.user import InvitedUser, User
from app.utils import is_gov_user, redact_mobile_number, user_has_permissions


@main.route("/services/<service_id>/users")
@user_has_permissions(allow_org_user=True)
def manage_users(service_id):
    return render_template(
        "views/manage-users.html",
        users=current_service.team_members,
        has_team_members=current_service.has_team_members,
        current_user=current_user,
        show_search_box=(len(current_service.team_members) > 7),
        form=SearchUsersForm(),
        permissions=permissions,
        leave_service=request.args.get("leave_service"),
    )


@main.route("/services/<service_id>/users/invite", methods=["GET", "POST"])
@user_has_permissions("manage_service")
def invite_user(service_id):
    form = InviteUserForm(
        invalid_email_address=current_user.email_address,
        all_template_folders=current_service.all_template_folders,
        folder_permissions=[f["id"] for f in current_service.all_template_folders],
    )

    service_has_email_auth = current_service.has_permission("email_auth")
    if not service_has_email_auth:
        form.login_authentication.data = "sms_auth"

    current_app.logger.info("User {} attempting to invite user to service {}".format(current_user.id, service_id))
    if form.validate_on_submit():
        email_address = form.email_address.data
        invited_user = InvitedUser.create(
            current_user.id,
            service_id,
            email_address,
            form.permissions,
            form.login_authentication.data,
            form.folder_permissions.data,
        )

        flash(
            "{} {}".format(_l("Invite sent to"), invited_user.email_address),
            "default_with_tick",
        )
        return redirect(url_for(".manage_users", service_id=service_id))

    return render_template(
        "views/invite-user.html",
        form=form,
        service_has_email_auth=service_has_email_auth,
        mobile_number=True,
    )


@main.route("/services/<service_id>/users/<user_id>", methods=["GET", "POST"])
@user_has_permissions("manage_service")
def edit_user_permissions(service_id, user_id):
    service_has_email_auth = current_service.has_permission("email_auth")
    user = current_service.get_team_member(user_id)

    mobile_number = None
    if user.mobile_number:
        mobile_number = redact_mobile_number(user.mobile_number, " ")

    current_app.logger.info(
        "User {} is changing permissions for user: {} for service: {}".format(current_user.id, user.id, current_service.id)
    )
    form = PermissionsForm.from_user(
        user,
        service_id,
        folder_permissions=(
            None
            if user.platform_admin
            else [f["id"] for f in current_service.all_template_folders if user.has_template_folder_permission(f)]
        ),
        all_template_folders=None if user.platform_admin else current_service.all_template_folders,
    )

    if form.validate_on_submit():
        user.set_permissions(
            service_id,
            permissions=form.permissions,
            folder_permissions=form.folder_permissions.data,
        )
        if service_has_email_auth:
            user.update(auth_type=form.login_authentication.data)
        return redirect(url_for(".manage_users", service_id=service_id))

    return render_template(
        "views/edit-user-permissions.html",
        user=user,
        form=form,
        service_has_email_auth=service_has_email_auth,
        mobile_number=mobile_number,
        delete=request.args.get("delete"),
    )


@main.route("/services/<service_id>/users/<user_id>/delete", methods=["POST"])
@user_has_permissions("manage_service")
def remove_user_from_service(service_id, user_id):
    try:
        current_app.logger.info(
            "User {} is removing user: {} from service: {}".format(current_user.id, user_id, current_service.id)
        )
        service_api_client.remove_user_from_service(service_id, user_id)
    except HTTPError as e:
        msg = "You cannot remove the only user for a service"
        if e.status_code == 400 and msg in e.message:
            flash(_l(msg), "info")
            return redirect(url_for(".manage_users", service_id=service_id))
        elif e.status_code == 400 and "SERVICE_CANNOT_HAVE_LT_2_MEMBERS" in e.message:
            flash(
                [
                    _l("You cannot leave this team at this time"),
                    _l(
                        "“{}” has only 2 team members, the minimum for a live service. You’ll be able to leave once someone else accepts an invitation to join the team for this service."
                    ).format(current_service.name),
                ],
                "info",
            )
            return redirect(url_for(".manage_users", service_id=service_id))
        elif e.status_code == 400 and "SERVICE_NEEDS_USER_W_MANAGE_SETTINGS_PERM" in e.message:
            flash(
                [
                    _l("You cannot leave this team at this time"),
                    _l(
                        "You're the only team member of “{}” with permission to “Manage settings and team”. To leave this service, you must first give another team member this permission."
                    ).format(current_service.name),
                ],
                "info",
            )
            return redirect(url_for(".manage_users", service_id=service_id))
        else:
            abort(500, e)

    if current_user.id == user_id:
        # the user has removed themselves from the service
        # redirect to the "your services" page
        return redirect(url_for("main.choose_account"))
    return redirect(url_for(".manage_users", service_id=service_id))


@main.route("/services/<service_id>/users/<uuid:user_id>/edit-email", methods=["GET", "POST"])
@user_has_permissions("manage_service")
def edit_user_email(service_id, user_id):
    user = current_service.get_team_member(user_id)
    user_email = user.email_address

    current_app.logger.info(
        "User {} is changing email for user: {} for service: {}".format(current_user.id, user.id, current_service.id)
    )

    if is_gov_user(user_email):
        form = ChangeEmailForm(User.already_registered, email_address=user_email)
    else:
        form = ChangeNonGovEmailForm(User.already_registered, email_address=user_email)

    if request.form.get("email_address", "").strip() == user_email:
        return redirect(url_for(".manage_users", service_id=current_service.id))

    if form.validate_on_submit():
        session["team_member_email_change"] = form.email_address.data

        return redirect(url_for(".confirm_edit_user_email", user_id=user.id, service_id=service_id))

    return render_template(
        "views/manage-users/edit-user-email.html",
        user=user,
        form=form,
        service_id=service_id,
    )


@main.route(
    "/services/<service_id>/users/<uuid:user_id>/edit-email/confirm",
    methods=["GET", "POST"],
)
@user_has_permissions("manage_service")
def confirm_edit_user_email(service_id, user_id):
    user = current_service.get_team_member(user_id)
    if "team_member_email_change" in session:
        new_email = session["team_member_email_change"]
    else:
        return redirect(url_for(".edit_user_email", service_id=service_id, user_id=user_id))
    if request.method == "POST":
        try:
            user.update(email_address=new_email, updated_by=current_user.id)
        except HTTPError as e:
            abort(500, e)
        else:
            create_email_change_event(user.id, current_user.id, user.email_address, new_email)
        finally:
            session.pop("team_member_email_change", None)

        return redirect(url_for(".manage_users", service_id=service_id))
    return render_template(
        "views/manage-users/confirm-edit-user-email.html",
        user=user,
        service_id=service_id,
        new_email=new_email,
    )


@main.route(
    "/services/<service_id>/users/<uuid:user_id>/edit-mobile-number",
    methods=["GET", "POST"],
)
@user_has_permissions("manage_service")
def edit_user_mobile_number(service_id, user_id):
    user = current_service.get_team_member(user_id)
    user_mobile_number = redact_mobile_number(user.mobile_number)

    current_app.logger.info(
        "User {} is changing mobile number for user: {} for service: {}".format(current_user.id, user.id, current_service.id)
    )

    form = ChangeMobileNumberForm(mobile_number=user_mobile_number)
    if form.mobile_number.data == user_mobile_number and request.method == "POST":
        return redirect(url_for(".manage_users", service_id=service_id))
    if form.validate_on_submit():
        session["team_member_mobile_change"] = form.mobile_number.data

        return redirect(
            url_for(
                ".confirm_edit_user_mobile_number",
                user_id=user.id,
                service_id=service_id,
            )
        )
    return render_template(
        "views/manage-users/edit-user-mobile.html",
        user=user,
        form=form,
        service_id=service_id,
    )


@main.route(
    "/services/<service_id>/users/<uuid:user_id>/edit-mobile-number/confirm",
    methods=["GET", "POST"],
)
@user_has_permissions("manage_service")
def confirm_edit_user_mobile_number(service_id, user_id):
    user = current_service.get_team_member(user_id)
    if "team_member_mobile_change" in session:
        new_number = session["team_member_mobile_change"]
    else:
        return redirect(url_for(".edit_user_mobile_number", service_id=service_id, user_id=user_id))
    if request.method == "POST":
        try:
            user.update(mobile_number=new_number, updated_by=current_user.id)
        except HTTPError as e:
            abort(500, e)
        else:
            create_mobile_number_change_event(user.id, current_user.id, user.mobile_number, new_number)
        finally:
            session.pop("team_member_mobile_change", None)

        return redirect(url_for(".manage_users", service_id=service_id))

    return render_template(
        "views/manage-users/confirm-edit-user-mobile-number.html",
        user=user,
        service_id=service_id,
        new_mobile_number=new_number,
    )


@main.route("/services/<service_id>/cancel-invited-user/<uuid:invited_user_id>", methods=["GET"])
@user_has_permissions("manage_service")
def cancel_invited_user(service_id, invited_user_id):
    current_service.cancel_invite(invited_user_id)

    return redirect(url_for("main.manage_users", service_id=service_id))
