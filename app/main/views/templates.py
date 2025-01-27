import json
from datetime import datetime, timedelta
from string import ascii_uppercase

from dateutil.parser import parse
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
from markupsafe import Markup
from notifications_python_client.errors import HTTPError
from notifications_utils import TEMPLATE_NAME_CHAR_COUNT_LIMIT
from notifications_utils.formatters import nl2br
from notifications_utils.recipients import first_column_headings

from app import (
    current_service,
    get_current_locale,
    service_api_client,
    template_api_prefill_client,
    template_category_api_client,
    template_folder_api_client,
    template_statistics_client,
)
from app.extensions import redis_client
from app.main import main
from app.main.forms import (
    TC_PRIORITY_VALUE,
    AddEmailRecipientsForm,
    AddSMSRecipientsForm,
    CreateTemplateForm,
    EmailTemplateFormWithCategory,
    LetterTemplateFormWithCategory,
    LetterTemplatePostageForm,
    SearchByNameForm,
    SetTemplateSenderForm,
    SMSTemplateFormWithCategory,
    TemplateAndFoldersSelectionForm,
    TemplateCategoryForm,
    TemplateFolderForm,
)
from app.main.views.send import get_example_csv_rows, get_sender_details
from app.models.enum.template_categories import DefaultTemplateCategories
from app.models.service import Service
from app.models.template_list import (
    TEMPLATE_TYPES_NO_LETTER,
    TemplateList,
    TemplateLists,
)
from app.notify_client.notification_counts_client import notification_counts_client
from app.template_previews import TemplatePreview, get_page_count_for_letter
from app.utils import (
    email_or_sms_not_enabled,
    get_template,
    should_skip_template_page,
    user_has_permissions,
    user_is_platform_admin,
)

# Todo: Remove this once the process_types in the backend are updated to use low/med/high
category_mapping = {
    "bulk": "Bulk",
    "normal": "Normal",
    "priority": "Priority",
}

form_objects_with_category = {
    "email": EmailTemplateFormWithCategory,
    "sms": SMSTemplateFormWithCategory,
    "letter": LetterTemplateFormWithCategory,
}


def get_email_preview_template(template, template_id, service_id):
    if template_id and service_id:
        letter_preview_url = url_for(
            ".view_letter_template_preview",
            service_id=service_id,
            template_id=template_id,
            filetype="png",
        )
    else:
        letter_preview_url = None

    email_preview_template = get_template(
        template,
        current_service,
        letter_preview_url=letter_preview_url,
        show_recipient=True,
        page_count=get_page_count_for_letter(template),
    )

    return email_preview_template


def set_preview_data(data, service_id, template_id=None):
    key = f"template-preview:{service_id}:{template_id}"
    redis_client.set(key=key, value=json.dumps(data), ex=int(timedelta(days=1).total_seconds()))


def get_preview_data(service_id, template_id=None):
    key = f"template-preview:{service_id}:{template_id}"
    data = redis_client.get(key)
    if data:
        return json.loads(data)
    else:
        return dict()


def delete_preview_data(service_id, template_id=None):
    key = f"template-preview:{service_id}:{template_id}"
    redis_client.delete(key)


def get_char_limit_error_msg():
    return _("Too many characters")


def get_limit_stats(notification_type):
    # get the limit stats for the current service
    limit_stats = notification_counts_client.get_limit_stats(current_service)

    # transform the stats into a format that can be used in the template
    limit_stats = {
        "dailyLimit": limit_stats[notification_type]["daily"]["limit"],
        "dailyUsed": limit_stats[notification_type]["daily"]["sent"],
        "dailyRemaining": limit_stats[notification_type]["daily"]["remaining"],
        "yearlyLimit": limit_stats[notification_type]["annual"]["limit"],
        "yearlyUsed": limit_stats[notification_type]["annual"]["sent"],
        "yearlyRemaining": limit_stats[notification_type]["annual"]["remaining"],
        "notification_type": notification_type,
        "heading": _("Ready to send?"),
    }

    # determine ready to send heading
    if limit_stats["yearlyRemaining"] == 0:
        limit_stats["heading"] = _("Sending paused until annual limit resets")
    elif limit_stats["dailyRemaining"] == 0:
        limit_stats["heading"] = _("Sending paused until 7pm ET. You can schedule more messages to send later.")

    return limit_stats


@main.route("/services/<service_id>/templates/<uuid:template_id>")
@user_has_permissions()
def view_template(service_id, template_id):
    delete_preview_data(service_id, template_id)
    template = current_service.get_template(template_id)
    template_folder = current_service.get_template_folder(template["folder"])

    user_has_template_permission = current_user.has_template_folder_permission(template_folder)

    if should_skip_template_page(template["template_type"]):
        return redirect(url_for(".send_one_off", service_id=service_id, template_id=template_id))

    return render_template(
        "views/templates/template.html",
        template=get_email_preview_template(template, template_id, service_id),
        template_postage=template["postage"],
        user_has_template_permission=user_has_template_permission,
        **get_limit_stats(template["template_type"]),
    )


@main.route("/services/<service_id>/templates/<uuid:template_id>/preview", methods=["GET", "POST"])
@main.route("/services/<service_id>/templates/preview", methods=["GET", "POST"])
@user_has_permissions()
def preview_template(service_id, template_id=None):
    template = get_preview_data(service_id, template_id)
    if not template:
        # template == {} if the user has not yet clicked the preview link
        template = current_service.get_template_with_user_permission_or_403(template_id, current_user)

    if request.method == "POST":
        if request.form["button_pressed"] == "edit":
            if template["id"]:
                return redirect(url_for(".edit_service_template", service_id=current_service.id, template_id=template_id))
            else:
                return redirect(
                    url_for(
                        ".add_service_template",
                        service_id=current_service.id,
                        template_type=template["template_type"],
                        template_folder_id=template["folder"],
                    )
                )

        else:
            try:
                if template.get("id"):
                    service_api_client.update_service_template(
                        str(template_id),
                        template["name"],
                        template["template_type"],
                        template["content"],
                        service_id,
                        template["subject"],
                        None if template["process_type"] == TC_PRIORITY_VALUE else template["process_type"],
                        template["template_category_id"],
                        template["text_direction_rtl"],
                    )
                else:
                    new_template = service_api_client.create_service_template(
                        template["name"],
                        template["template_type"],
                        template["content"],
                        service_id,
                        template["subject"],
                        None if template["process_type"] == TC_PRIORITY_VALUE else template["process_type"],
                        template["folder"],
                        template["template_category_id"],
                    )
                    template_id = new_template["data"]["id"]

                flash(_("'{}' template saved").format(template["name"]), "default_with_tick")
                return redirect(
                    url_for(
                        ".view_template",
                        service_id=service_id,
                        template_id=template_id,
                    )
                )
            except HTTPError as e:
                if e.status_code == 400:
                    if "content" in e.message and any(["character count greater than" in x for x in e.message["content"]]):
                        error_message = get_char_limit_error_msg()
                        flash(error_message)
                    elif "name" in e.message and any(["Template name must be less than" in x for x in e.message["name"]]):
                        error_message = (_("Template name must be less than {char_limit} characters")).format(
                            char_limit=TEMPLATE_NAME_CHAR_COUNT_LIMIT + 1
                        )
                        flash(error_message)
                    else:
                        raise e
                else:
                    raise e

    if should_skip_template_page(template["template_type"]):
        return redirect(url_for(".send_one_off", service_id=service_id, template_id=template["id"]))

    if template["id"]:
        back_link = url_for(".edit_service_template", service_id=current_service.id, template_id=template["id"])
    else:
        back_link = url_for(
            ".add_service_template",
            service_id=current_service.id,
            template_type=template["template_type"],
            template_folder_id=template["folder"],
        )
    return render_template(
        "views/templates/preview_template.html",
        template=get_email_preview_template(template, template["id"], service_id),
        back_link=back_link,
    )


@main.route("/services/<service_id>/start-tour/<uuid:template_id>")
@user_has_permissions("view_activity")
def start_tour(service_id, template_id):
    template = current_service.get_template(template_id)

    if template["template_type"] != "email":
        abort(404)

    return render_template(
        "views/templates/start-tour.html",
        template=get_template(
            template,
            current_service,
            show_recipient=True,
        ),
        help="1",
    )


@main.route("/services/<service_id>/templates", methods=["GET", "POST"])
@main.route(
    "/services/<service_id>/templates/folders/<template_folder_id>",
    methods=["GET", "POST"],
)
@main.route("/services/<service_id>/templates/<template_type>", methods=["GET", "POST"])
@main.route(
    "/services/<service_id>/templates/<template_type>/folders/<template_folder_id>",
    methods=["GET", "POST"],
)
@user_has_permissions()
def choose_template(service_id, template_type="all", template_folder_id=None):
    template_folder = current_service.get_template_folder(template_folder_id)

    user_has_template_folder_permission = current_user.has_template_folder_permission(template_folder)

    template_list = TemplateList(current_service, template_type, template_folder_id, current_user)

    templates_and_folders_form = TemplateAndFoldersSelectionForm(
        all_template_folders=current_service.get_user_template_folders(current_user),
        template_list=template_list,
        template_type=template_type,
        allow_adding_letter_template=current_service.has_permission("letter"),
        allow_adding_copy_of_template=(current_service.all_templates or len(current_user.service_ids) > 1),
    )

    option_hints = {template_folder_id if template_folder_id is not None else "__NONE__": _l("Current folder")}

    if request.method == "POST" and templates_and_folders_form.validate_on_submit():
        if not current_user.has_permissions("manage_templates"):
            abort(403)
        try:
            return process_folder_management_form(templates_and_folders_form, template_folder_id)
        except HTTPError as e:
            flash(e.message)

    if "templates_and_folders" in templates_and_folders_form.errors:
        flash(_("Select at least one template or folder"))

    initial_state = request.args.get("initial_state")
    if request.method == "GET" and initial_state:
        templates_and_folders_form.op = initial_state

    sending_view = request.args.get("view") == "sending"

    template_category_name_col = "name_en" if get_current_locale(current_app) == "en" else "name_fr"

    # Get the full list of template categories, any hidden ones will be called 'Other'
    template_categories = [
        template.template_category[template_category_name_col] if not template.template_category.get("hidden") else _("Other")
        for template in template_list
        if template.template_category
    ]

    # Remove duplicates while preserving order
    template_categories = sorted(set(template_categories))

    return render_template(
        "views/templates/choose.html",
        current_template_folder_id=template_folder_id,
        current_template_folder=current_service.get_template_folder_path(template_folder_id)[-1],
        template_folder_path=current_service.get_template_folder_path(template_folder_id),
        template_list=template_list,
        template_types=list(TEMPLATE_TYPES_NO_LETTER.values()),
        template_categories=template_categories,
        template_category_name_col=template_category_name_col,
        show_search_box=current_service.count_of_templates_and_folders > 7,
        show_template_nav=(current_service.has_multiple_template_types and (len(current_service.all_templates) > 2)),
        sending_view=sending_view,
        template_nav_items=get_template_nav_items(template_folder_id, sending_view),
        template_type=template_type,
        search_form=SearchByNameForm(),
        templates_and_folders_form=templates_and_folders_form,
        move_to_children=templates_and_folders_form.move_to.children(),
        user_has_template_folder_permission=user_has_template_folder_permission,
        option_hints=option_hints,
    )


def process_folder_management_form(form, current_folder_id):
    current_service.get_template_folder_with_user_permission_or_403(current_folder_id, current_user)
    new_folder_id = None

    if form.is_add_folder_op:
        new_folder_id = template_folder_api_client.create_template_folder(
            current_service.id, name=form.get_folder_name(), parent_id=current_folder_id
        )

    if form.is_move_op:
        # if we've just made a folder, we also want to move there
        move_to_id = new_folder_id or form.move_to.data

        current_service.move_to_folder(ids_to_move=form.templates_and_folders.data, move_to=move_to_id)

    return redirect(request.url)


def get_template_nav_label(value):
    return {
        "all": _l("All"),
        "sms": _l("Text message"),
        "email": _l("Email"),
        "letter": _l("Letter"),
    }[value]


def get_template_nav_items(template_folder_id, sending_view):
    return [
        (
            get_template_nav_label(key),
            key,
            url_for(
                ".choose_template",
                service_id=current_service.id,
                template_type=key,
                template_folder_id=template_folder_id,
                view="sending" if sending_view else None,
            ),
            "",
        )
        for key in ["all"] + current_service.available_template_types
    ]


@main.route("/services/<service_id>/templates/<template_id>.<filetype>")
@user_has_permissions()
def view_letter_template_preview(service_id, template_id, filetype):
    if filetype not in ("pdf", "png"):
        abort(404)

    db_template = current_service.get_template(template_id)

    return TemplatePreview.from_database_object(db_template, filetype, page=request.args.get("page"))


@main.route("/templates/letter-preview-image/<filename>")
@user_is_platform_admin
def letter_branding_preview_image(filename):
    template = {
        "subject": "An example letter",
        "content": (
            "Lorem Ipsum is simply dummy text of the printing and typesetting "
            "industry.\n\nLorem Ipsum has been the industry’s standard dummy "
            "text ever since the 1500s, when an unknown printer took a galley "
            "of type and scrambled it to make a type specimen book.\n\n"
            "# History\n\nIt has survived not only\n\n"
            "* five centuries\n"
            "* but also the leap into electronic typesetting\n\n"
            "It was popularised in the 1960s with the release of Letraset "
            "sheets containing Lorem Ipsum passages, and more recently with "
            "desktop publishing software like Aldus PageMaker including "
            "versions of Lorem Ipsum.\n\n"
            "The point of using Lorem Ipsum is that it has a more-or-less "
            "normal distribution of letters, as opposed to using ‘Content "
            "here, content here’, making it look like readable English."
        ),
    }
    filename = None if filename == "no-branding" else filename

    return TemplatePreview.from_example_template(template, filename)


def _view_template_version(service_id, template_id, version, letters_as_pdf=False):
    return dict(
        template=get_template(
            current_service.get_template(template_id, version=version),
            current_service,
            letter_preview_url=(
                url_for(
                    ".view_template_version_preview",
                    service_id=service_id,
                    template_id=template_id,
                    version=version,
                    filetype="png",
                )
                if not letters_as_pdf
                else None
            ),
        )
    )


@main.route("/services/<service_id>/templates/<template_id>/version/<int:version>")
@user_has_permissions()
def view_template_version(service_id, template_id, version):
    return render_template(
        "views/templates/template_history.html",
        **_view_template_version(service_id=service_id, template_id=template_id, version=version),
    )


@main.route("/services/<service_id>/templates/<template_id>/version/<int:version>.<filetype>")
@user_has_permissions()
def view_template_version_preview(service_id, template_id, version, filetype):
    db_template = current_service.get_template(template_id, version=version)
    return TemplatePreview.from_database_object(db_template, filetype)


def _add_template_by_type(template_type, template_folder_id):
    if template_type == "copy-existing":
        return redirect(
            url_for(
                ".choose_template_to_copy",
                service_id=current_service.id,
            )
        )

    if template_type == "letter":
        blank_letter = service_api_client.create_service_template(
            "New letter template",
            "letter",
            "Body",
            current_service.id,
            "Main heading",
            "normal",
            template_folder_id,
        )
        return redirect(
            url_for(
                ".view_template",
                service_id=current_service.id,
                template_id=blank_letter["data"]["id"],
            )
        )

    if email_or_sms_not_enabled(template_type, current_service.permissions):
        return redirect(
            url_for(
                ".action_blocked",
                service_id=current_service.id,
                notification_type=template_type,
                return_to="add_new_template",
                template_id="0",
            )
        )
    else:
        return redirect(
            url_for(
                ".add_service_template",
                service_id=current_service.id,
                template_type=template_type,
                template_folder_id=template_folder_id,
            )
        )


@main.route("/services/<service_id>/templates/create", methods=["GET", "POST"])
@main.route("/services/<service_id>/templates/folders/<template_folder_id>/create", methods=["GET", "POST"])
@main.route("/services/<service_id>/templates/<template_type>/create", methods=["GET", "POST"])
@main.route("/services/<service_id>/templates/<template_type>/folders/<template_folder_id>/create", methods=["GET", "POST"])
@user_has_permissions("manage_templates")
def create_template(service_id, template_type="all", template_folder_id=None):
    delete_preview_data(service_id)
    form = CreateTemplateForm()

    if request.method == "POST" and form.validate_on_submit():
        try:
            return _add_template_by_type(
                form.what_type.data,
                template_folder_id,
            )
        except HTTPError as e:
            flash(e.message)
    return render_template(
        "views/templates/create.html",
        service_id=service_id,
        template_folder_id=template_folder_id,
        template_type=template_type,
        form=form,
        disabled_options={},
        option_hints={},
    )


@main.route("/services/<service_id>/templates/copy")
@main.route("/services/<service_id>/templates/all/copy")
@main.route("/services/<service_id>/templates/email/copy")
@main.route("/services/<service_id>/templates/sms/copy")
@main.route("/services/<service_id>/templates/copy/from-folder/<uuid:from_folder>")
@main.route("/services/<service_id>/templates/copy/from-service/<uuid:from_service>")
@main.route("/services/<service_id>/templates/copy/from-service/<uuid:from_service>/from-folder/<uuid:from_folder>")
@main.route("/services/<service_id>/templates/all/folders/<uuid:from_folder>/copy")
# @user_has_permissions("manage_templates")
def choose_template_to_copy(
    service_id,
    from_service=None,
    from_folder=None,
):
    example_service = Service(service_api_client.get_service(service_id="66a4ae1b-653f-4699-8675-fe86e6b147e7")["data"])
    if from_folder and from_service is None:
        from_service = service_id

    if from_service:
        current_user.belongs_to_service_or_403(from_service)
        service = Service(service_api_client.get_service(from_service)["data"])

        return render_template(
            "views/templates/copy.html",
            services_templates_and_folders=TemplateList(service, template_folder_id=from_folder, user=current_user),
            template_folder_path=service.get_template_folder_path(from_folder),
            from_service=service,
            search_form=SearchByNameForm(),
            example_service=TemplateList(example_service),
        )

    else:
        return render_template(
            "views/templates/copy.html",
            services_templates_and_folders=TemplateLists(current_user),
            search_form=SearchByNameForm(),
            example_service=TemplateList(example_service),
        )


@main.route("/services/<service_id>/templates/copy/<uuid:template_id>", methods=["GET", "POST"])
@user_has_permissions("manage_templates")
def copy_template(service_id, template_id):
    from_service = request.args.get("from_service")

    current_user.belongs_to_service_or_403(from_service)

    template = service_api_client.get_service_template(from_service, str(template_id))["data"]

    template_folder = template_folder_api_client.get_template_folder(from_service, template["folder"])
    if not current_user.has_template_folder_permission(template_folder):
        abort(403)

    if request.method == "POST":
        return add_service_template(
            service_id,
            template["template_type"],
            template_folder_id=template_folder.get("id"),
        )

    template["template_content"] = template["content"]
    template["name"] = _get_template_copy_name(template, current_service.all_templates)

    form, other_category, template_category_hints = _get_categories_and_prepare_form(template, template["template_type"])
    return render_template(
        f"views/edit-{template['template_type']}-template.html",
        form=form,
        template=template,
        heading=_l("Copy email template") if template["template_type"] == "email" else _l("Copy text message template"),
        service_id=service_id,
        services=current_user.service_ids,
        template_category_hints=template_category_hints,
        other_category=other_category,
    )


def _get_template_copy_name(template, existing_templates):
    template_names = [existing["name"] for existing in existing_templates]

    for index in reversed(range(1, 10)):
        if "{} (copy {})".format(template["name"], index) in template_names:
            return "{} (copy {})".format(template["name"], index + 1)

    if "{} (copy)".format(template["name"]) in template_names:
        return "{} (copy 2)".format(template["name"])

    return "{} (copy)".format(template["name"])


@main.route("/services/<service_id>/templates/action-blocked/<notification_type>/<return_to>/<template_id>")
@user_has_permissions("manage_templates")
def action_blocked(service_id, notification_type, return_to, template_id):
    if notification_type == "sms":
        notification_type = "text messages"
    elif notification_type == "email":
        notification_type = "emails"

    return render_template(
        "views/templates/action_blocked.html",
        service_id=service_id,
        notification_type=notification_type,
        return_to=return_to,
        template_id=template_id,
    )


@main.route(
    "/services/<service_id>/templates/folders/<template_folder_id>/manage",
    methods=["GET", "POST"],
)
@user_has_permissions("manage_templates")
def manage_template_folder(service_id, template_folder_id):
    template_folder = current_service.get_template_folder_with_user_permission_or_403(template_folder_id, current_user)
    form = TemplateFolderForm(
        name=template_folder["name"],
        users_with_permission=template_folder.get("users_with_permission", None),
        all_service_users=[user for user in current_service.active_users if user.id != current_user.id],
    )
    if form.validate_on_submit():
        if current_user.has_permissions("manage_service") and form.users_with_permission.all_service_users:
            users_with_permission = form.users_with_permission.data + [current_user.id]
        else:
            users_with_permission = None
        template_folder_api_client.update_template_folder(
            current_service.id,
            template_folder_id,
            name=form.name.data,
            users_with_permission=users_with_permission,
        )
        return redirect(
            url_for(
                ".choose_template",
                service_id=service_id,
                template_folder_id=template_folder_id,
            )
        )

    return render_template(
        "views/templates/manage-template-folder.html",
        form=form,
        current_template_folder=current_service.get_template_folder_path(template_folder_id)[-1],
        template_folder_path=current_service.get_template_folder_path(template_folder_id),
        current_service_id=current_service.id,
        template_folder_id=template_folder_id,
        template_type="all",
    )


@main.route(
    "/services/<service_id>/templates/folders/<template_folder_id>/delete",
    methods=["GET", "POST"],
)
@user_has_permissions("manage_templates")
def delete_template_folder(service_id, template_folder_id):
    template_folder = current_service.get_template_folder_with_user_permission_or_403(template_folder_id, current_user)

    if len(current_service.get_template_folders_and_templates(template_type="all", template_folder_id=template_folder_id)) > 0:
        flash(_l("You must empty this folder before you can delete it"), "info")
        return redirect(
            url_for(
                ".choose_template",
                service_id=service_id,
                template_type="all",
                template_folder_id=template_folder_id,
            )
        )

    if request.method == "POST":
        try:
            template_folder_api_client.delete_template_folder(current_service.id, template_folder_id)

            return redirect(
                url_for(
                    ".choose_template",
                    service_id=service_id,
                    template_folder_id=template_folder["parent_id"],
                )
            )
        except HTTPError as e:
            msg = _l("Folder is not empty")
            if e.status_code == 400 and msg in e.message:
                flash(_("You must empty this folder before you can delete it"), "info")
                return redirect(
                    url_for(
                        ".choose_template",
                        service_id=service_id,
                        template_type="all",
                        template_folder_id=template_folder_id,
                    )
                )
            else:
                abort(500, e)
    else:
        flash(
            "{} ‘{}’ {}".format(
                _l("Are you sure you want to delete the"),
                template_folder["name"],
                _l("folder?"),
            ),
            "delete",
        )
        return manage_template_folder(service_id, template_folder_id)


@main.route("/services/templates/<template_id>/get-data", methods=["POST"])
def get_template_data(template_id):
    data = template_api_prefill_client.get_template(template_id)
    return jsonify({"result": data})


@main.route("/services/<service_id>/templates/add-<template_type>", methods=["GET", "POST"])
@main.route(
    "/services/<service_id>/templates/folders/<template_folder_id>/add-<template_type>",
    methods=["GET", "POST"],
)
@user_has_permissions("manage_templates")
def add_service_template(service_id, template_type, template_folder_id=None):  # noqa: C901
    if template_type not in ["sms", "email", "letter"]:
        abort(404)
    if not current_service.has_permission("letter") and template_type == "letter":
        abort(403)

    template = get_preview_data(service_id)

    form, other_category, template_category_hints = _get_categories_and_prepare_form(template, template_type)

    if form.validate_on_submit():
        if form.process_type.data != TC_PRIORITY_VALUE:
            abort_403_if_not_admin_user()
        subject = form.subject.data if hasattr(form, "subject") else None
        if request.form.get("button_pressed") == "preview":
            preview_template_data = {
                "name": form.name.data,
                "content": form.template_content.data,
                "template_content": form.template_content.data,
                "subject": subject,
                "template_type": template_type,
                "id": None,
                "process_type": form.process_type.data,
                "folder": template_folder_id,
                "template_category_id": form.template_category_id.data,
                "text_direction_rtl": form.text_direction_rtl.data,
            }
            set_preview_data(preview_template_data, service_id)
            return redirect(
                url_for(
                    ".preview_template",
                    service_id=service_id,
                )
            )
        try:
            new_template = service_api_client.create_service_template(
                form.name.data,
                template_type,
                form.template_content.data,
                service_id,
                subject,
                None if form.process_type.data == TC_PRIORITY_VALUE else form.process_type.data,
                template_folder_id,
                form.template_category_id.data,
            )
            # Send the information in form's template_category_other field to Freshdesk
            if form.template_category_other.data:
                is_english = get_current_locale(current_app) == "en"
                try:
                    current_user.send_new_template_category_request(
                        current_user.id,
                        current_service.id,
                        form.template_category_other.data if is_english else None,
                        form.template_category_other.data if not is_english else None,
                        new_template["data"]["id"],
                    )
                except HTTPError as e:
                    current_app.logger.error(
                        f"Failed to send new template category request to Freshdesk: {e} for template {new_template['data']['id']}, data is {form.template_category_other.data}"
                    )
                except AttributeError as e:
                    current_app.logger.error(
                        f"Failed to send new template category request to Freshdesk: {e} for template {new_template['data']['id']}, data is {form.template_category_other.data}"
                    )
        except HTTPError as e:
            if (
                e.status_code == 400
                and "content" in e.message
                and any(["character count greater than" in x for x in e.message["content"]])
            ):
                error_message = get_char_limit_error_msg()
                form.template_content.errors.extend([error_message])
            elif "name" in e.message and any(["Template name must be less than" in x for x in e.message["name"]]):
                error_message = (_("Template name must be less than {char_limit} characters")).format(
                    char_limit=TEMPLATE_NAME_CHAR_COUNT_LIMIT + 1
                )
                form.name.errors.extend([error_message])
            else:
                raise e
        else:
            flash(_("'{}' template saved").format(form.name.data), "default_with_tick")

            return redirect(
                url_for(
                    ".view_template",
                    service_id=service_id,
                    template_id=new_template["data"]["id"],
                )
            )

    if email_or_sms_not_enabled(template_type, current_service.permissions):
        return redirect(
            url_for(
                ".action_blocked",
                service_id=service_id,
                notification_type=template_type,
                template_folder_id=template_folder_id,
                return_to="templates",
                template_id="0",
            )
        )
    else:
        return render_template(
            f"views/edit-{template_type}-template.html",
            form=form,
            template_type=template_type,
            template_folder_id=template_folder_id,
            service_id=service_id,
            heading=_l("Create reusable template"),
            template_category_hints=template_category_hints,
            other_category=other_category,
            template_category_mode="expand",
        )


def abort_403_if_not_admin_user():
    if not current_user.platform_admin:
        abort(403)


def _get_categories_and_prepare_form(template, template_type):
    categories = template_category_api_client.get_all_template_categories()

    form = form_objects_with_category[template_type](**template)

    # alphabetize choices
    name_col = "name_en" if get_current_locale(current_app) == "en" else "name_fr"
    desc_col = "description_en" if get_current_locale(current_app) == "en" else "description_fr"
    categories = sorted(categories, key=lambda x: x[name_col])
    form.template_category_id.choices = [(cat["id"], cat[name_col]) for cat in categories if not cat.get("hidden", False)]

    # add "other" category to choices, default to the low priority template category
    # if the template is already in one of the default categories, then dont show the other
    if template.get("template_category") and template["template_category"].get("hidden"):
        other_category = None
        form.template_category_other.validators = []
        form.template_category_id.choices.append((form.template_category_id.data, _("Other")))
    else:
        other_category = {DefaultTemplateCategories.LOW.value: form.template_category_other}
        form.template_category_id.choices.append((DefaultTemplateCategories.LOW.value, _("Other")))

    template_category_hints = {cat["id"]: cat[desc_col] for cat in categories}

    return form, other_category, template_category_hints


@main.route("/services/<service_id>/templates/<template_id>/edit", methods=["GET", "POST"])
@user_has_permissions("manage_templates")
def edit_service_template(service_id, template_id):
    template = current_service.get_template_with_user_permission_or_403(template_id, current_user)
    new_template_data = get_preview_data(service_id, template_id)

    if new_template_data.get("content"):
        template["content"] = new_template_data["content"]
        template["name"] = new_template_data["name"]
        template["subject"] = new_template_data["subject"]
        template["text_direction_rtl"] = new_template_data["text_direction_rtl"]

    template["template_content"] = template["content"]

    if template.get("process_type_column") is None:
        template["process_type"] = TC_PRIORITY_VALUE

    form, other_category, template_category_hints = _get_categories_and_prepare_form(template, template["template_type"])

    if form.validate_on_submit():
        if form.process_type.data != template["process_type"]:
            abort_403_if_not_admin_user()

        subject = form.subject.data if hasattr(form, "subject") else None

        new_template_data = {
            "name": form.name.data,
            "content": form.template_content.data,
            "subject": subject,
            "template_type": template["template_type"],
            "id": template["id"],
            "process_type": form.process_type.data,
            "reply_to_text": template["reply_to_text"],
            "folder": template["folder"],
            "template_category_id": form.template_category_id.data,
            "text_direction_rtl": form.text_direction_rtl.data,
        }
        set_preview_data(new_template_data, service_id, template_id)

        new_template = get_template(new_template_data, current_service)
        template_change = get_template(template, current_service).compare_to(new_template)
        if template_change.placeholders_added and not request.form.get("confirm"):
            example_column_headings = first_column_headings[new_template.template_type] + list(new_template.placeholders)
            return render_template(
                "views/templates/breaking-change.html",
                template_change=template_change,
                new_template=new_template,
                column_headings=list(ascii_uppercase[: len(example_column_headings)]),
                example_rows=[
                    example_column_headings,
                    get_example_csv_rows(new_template),
                    get_example_csv_rows(new_template),
                ],
                form=form,
            )
        else:
            if request.form.get("button_pressed") == "preview":
                return redirect(
                    url_for(
                        ".preview_template",
                        service_id=service_id,
                        template_id=template_id,
                    )
                )
            else:
                try:
                    service_api_client.update_service_template(
                        template_id,
                        form.name.data,
                        template["template_type"],
                        form.template_content.data,
                        service_id,
                        subject,
                        None if form.process_type.data == TC_PRIORITY_VALUE else form.process_type.data,
                        form.template_category_id.data,
                        form.text_direction_rtl.data,
                    )
                    # Send the information in form's template_category_other field to Freshdesk
                    # This code path is a little complex - We do not want to raise an error if the request to Freshdesk fails, only if template creation fails
                    if form.template_category_other.data:
                        is_english = get_current_locale(current_app) == "en"
                        try:
                            current_user.send_new_template_category_request(
                                current_user.id,
                                current_service.id,
                                form.template_category_other.data if is_english else None,
                                form.template_category_other.data if not is_english else None,
                                template_id,
                            )
                        except HTTPError as e:
                            current_app.logger.error(
                                f"Failed to send new template category request to Freshdesk: {e} for template {template_id}, data is {form.template_category_other.data}"
                            )
                    flash(_("'{}' template saved").format(form.name.data), "default_with_tick")
                    return redirect(
                        url_for(
                            ".view_template",
                            service_id=service_id,
                            template_id=template_id,
                        )
                    )

                except HTTPError as e:
                    if e.status_code == 400:
                        if "content" in e.message and any(["character count greater than" in x for x in e.message["content"]]):
                            error_message = get_char_limit_error_msg()
                            form.template_content.errors.extend([error_message])
                        elif "name" in e.message and any(["Template name must be less than" in x for x in e.message["name"]]):
                            error_message = (_("Template name must be less than {char_limit} characters")).format(
                                char_limit=TEMPLATE_NAME_CHAR_COUNT_LIMIT + 1
                            )
                            form.name.errors.extend([error_message])
                        else:
                            raise e
                    else:
                        raise e

    if email_or_sms_not_enabled(template["template_type"], current_service.permissions):
        return redirect(
            url_for(
                ".action_blocked",
                service_id=service_id,
                notification_type=template["template_type"],
                return_to="view_template",
                template_id=template_id,
            )
        )
    else:
        return render_template(
            f"views/edit-{template['template_type']}-template.html",
            form=form,
            template=template,
            heading=_l("Edit reusable template"),
            template_category_hints=template_category_hints,
            other_category=other_category,
            template_category_mode="expand" if request.method == "POST" else None,
        )


@main.route("/services/<service_id>/templates/<template_id>/delete", methods=["GET", "POST"])
@user_has_permissions("manage_templates")
def delete_service_template(service_id, template_id):
    template = current_service.get_template_with_user_permission_or_403(template_id, current_user)

    if request.method == "POST":
        service_api_client.delete_service_template(service_id, template_id)
        return redirect(
            url_for(
                ".choose_template",
                service_id=service_id,
                template_folder_id=template["folder"],
            )
        )

    try:
        last_used_notification = template_statistics_client.get_template_statistics_for_template(service_id, template["id"])

        last_used_text = ""
        if not last_used_notification:
            last_used_text = _l("more than seven days")
        else:
            last_used_date = parse(last_used_notification["created_at"]).replace(tzinfo=None)
            last_used_text = get_human_readable_delta(last_used_date, datetime.utcnow())

        message = "{} {} {}".format(_l("This template was last used"), last_used_text, _l("ago."))

    except HTTPError as e:
        if e.status_code == 404:
            message = None
        else:
            raise e

    flash(
        [
            "{} ‘{}’?".format(_l("Are you sure you want to delete"), template["name"]),
            message,
        ],
        "delete",
    )
    return render_template(
        "views/templates/template.html",
        template=get_email_preview_template(template, template["id"], service_id),
        user_has_template_permission=True,
        **get_limit_stats(template["template_type"]),
    )


@main.route("/services/<service_id>/templates/<template_id>/redact", methods=["GET"])
@user_has_permissions("manage_templates")
def confirm_redact_template(service_id, template_id):
    template = current_service.get_template_with_user_permission_or_403(template_id, current_user)

    return render_template(
        "views/templates/template.html",
        template=get_email_preview_template(template, template["id"], service_id),
        user_has_template_permission=True,
        show_redaction_message=True,
        **get_limit_stats(template["template_type"]),
    )


@main.route("/services/<service_id>/templates/<template_id>/redact", methods=["POST"])
@user_has_permissions("manage_templates")
def redact_template(service_id, template_id):
    service_api_client.redact_service_template(service_id, template_id)

    flash(
        _("Personalised content will be hidden for messages sent with this template"),
        "default_with_tick",
    )

    return redirect(
        url_for(
            ".view_template",
            service_id=service_id,
            template_id=template_id,
        )
    )


@main.route("/services/<service_id>/templates/<template_id>/versions")
@user_has_permissions("view_activity")
def view_template_versions(service_id, template_id):
    return render_template(
        "views/templates/choose_history.html",
        versions=[
            get_template(
                template,
                current_service,
                letter_preview_url=url_for(
                    ".view_template_version_preview",
                    service_id=service_id,
                    template_id=template_id,
                    version=template["version"],
                    filetype="png",
                ),
            )
            for template in service_api_client.get_service_template_versions(service_id, template_id)["data"]
        ],
    )


@main.route(
    "/services/<service_id>/templates/<template_id>/set-template-sender",
    methods=["GET", "POST"],
)
@user_has_permissions("manage_templates")
def set_template_sender(service_id, template_id):
    template = current_service.get_template_with_user_permission_or_403(template_id, current_user)
    sender_details = get_template_sender_form_dict(service_id, template)
    no_senders = sender_details.get("no_senders", False)

    form = SetTemplateSenderForm(
        sender=sender_details["current_choice"],
        sender_choices=sender_details["value_and_label"],
    )
    option_hints = {sender_details["default_sender"]: "(Default)"}

    if form.validate_on_submit():
        service_api_client.update_service_template_sender(
            service_id,
            template_id,
            form.sender.data if form.sender.data else None,
        )
        return redirect(url_for(".view_template", service_id=service_id, template_id=template_id))

    return render_template(
        "views/templates/set-template-sender.html",
        form=form,
        template_id=template_id,
        no_senders=no_senders,
        option_hints=option_hints,
    )


@main.route(
    "/services/<service_id>/templates/<template_id>/edit-postage",
    methods=["GET", "POST"],
)
@user_has_permissions("manage_templates")
def edit_template_postage(service_id, template_id):
    template = current_service.get_template_with_user_permission_or_403(template_id, current_user)
    if template["template_type"] != "letter":
        abort(404)
    form = LetterTemplatePostageForm(**template)
    if form.validate_on_submit():
        postage = form.postage.data
        service_api_client.update_service_template_postage(service_id, template_id, postage)

        return redirect(url_for(".view_template", service_id=service_id, template_id=template_id))

    return render_template(
        "views/templates/edit-template-postage.html",
        form=form,
        service_id=service_id,
        template_id=template_id,
        template_postage=template["postage"],
    )


def get_template_sender_form_dict(service_id, template):
    context = {
        "email": {"field_name": "email_address"},
        "letter": {"field_name": "contact_block"},
        "sms": {"field_name": "sms_sender"},
    }[template["template_type"]]

    sender_format = context["field_name"]
    service_senders = get_sender_details(service_id, template["template_type"])
    context["default_sender"] = next((x["id"] for x in service_senders if x["is_default"]), "Not set")
    if not service_senders:
        context["no_senders"] = True

    context["value_and_label"] = [(sender["id"], Markup(nl2br(sender[sender_format]))) for sender in service_senders]
    # Add blank option to start of list
    context["value_and_label"].insert(0, ("", "Blank"))

    context["current_choice"] = template["service_letter_contact"] if template["service_letter_contact"] else ""
    return context


def get_human_readable_delta(from_time, until_time):
    delta = until_time - from_time
    if delta < timedelta(seconds=60):
        return "under a minute"
    elif delta < timedelta(hours=1):
        minutes = int(delta.seconds / 60)
        return "{} minute{}".format(minutes, "" if minutes == 1 else "s")
    elif delta < timedelta(days=1):
        hours = int(delta.seconds / 3600)
        return "{} hour{}".format(hours, "" if hours == 1 else "s")
    else:
        days = delta.days
        return "{} day{}".format(days, "" if days == 1 else "s")


@main.route("/services/<service_id>/add-recipients/<template_id>", methods=["GET", "POST"])
@user_has_permissions("send_messages", restrict_admin_usage=True)
def add_recipients(service_id, template_id):
    template = current_service.get_template_with_user_permission_or_403(template_id, current_user)

    if template["template_type"] == "email":
        form = AddEmailRecipientsForm()
        option_hints = {
            "many_recipients": Markup(
                _l(
                    "Upload or create a spreadsheet. GC Notify can create columns with headings for the email address and any other variables."
                )
            ),
            "one_recipient": Markup(_l("Enter their email address.")),
        }
    else:
        form = AddSMSRecipientsForm()
        option_hints = {
            "many_recipients": Markup(
                _l(
                    "Upload or create a spreadsheet. GC Notify can create columns with headings for the phone numbers and any other variables."
                )
            ),
            "one_recipient": Markup(_l("Enter their phone number.")),
        }
    option_conditionals = {"one_recipient": form.placeholder_value}

    if request.method == "POST":
        try:
            if form.what_type.data == "many_recipients":
                return redirect(
                    url_for(
                        "main.send_messages",
                        service_id=service_id,
                        template_id=template_id,
                    )
                )
            elif form.validate_on_submit():
                session["placeholders"] = {}
                session["recipient"] = form.placeholder_value.data
                if template["template_type"] == "email":
                    session["placeholders"]["email address"] = form.placeholder_value.data
                    session["placeholders"]["adresse courriel"] = form.placeholder_value.data
                else:
                    session["placeholders"]["phone number"] = form.placeholder_value.data
                    session["placeholders"]["numéro de téléphone"] = form.placeholder_value.data
                return redirect(url_for(".send_one_off_step", service_id=service_id, template_id=template_id, step_index=1))
        except HTTPError as e:
            flash(e.message)

    return render_template(
        "views/templates/add-recipients.html",
        service_id=service_id,
        template_id=template_id,
        form=form,
        disabled_options={},
        option_hints=option_hints,
        option_conditionals=option_conditionals,
    )


@main.route("/template-categories", methods=["GET"])
@main.route("/template-categories/<template_category_id>", methods=["POST"])
@user_is_platform_admin
def template_categories():
    template_category_list = template_category_api_client.get_all_template_categories()

    # Todo: Remove this once the process_types in the backend are updated to use low/med/high
    # Maps bulk/normal/priority to low/med/high for display in the front end.
    for cat in template_category_list:
        if cat["sms_process_type"] in category_mapping:
            cat["sms_process_type"] = category_mapping[cat["sms_process_type"]]

        if cat["email_process_type"] in category_mapping:
            cat["email_process_type"] = category_mapping[cat["email_process_type"]]

    return render_template(
        "views/templates/template_categories.html", search_form=SearchByNameForm(), template_categories=template_category_list
    )


@main.route("/template-category/<template_category_id>/delete", methods=["GET", "POST"])
@user_is_platform_admin
def delete_template_category(template_category_id):
    template_category = template_category_api_client.get_template_category(template_category_id)

    if request.method == "POST":
        try:
            template_category_api_client.delete_template_category(template_category_id)
        except HTTPError:
            flash(
                [
                    _l("Cannot delete template category, ‘{}’, is associated with templates").format(
                        (template_category["name_en"] if session["userlang"] == "en" else template_category["name_fr"])
                    )
                ]
            )
        return redirect(url_for(".template_categories"))

    flash(
        [
            "{} ‘{}’?".format(
                _l("Are you sure you want to delete"),
                (template_category["name_en"] if session["userlang"] == "en" else template_category["name_fr"]),
            ),
        ],
        "delete",
    )

    form = TemplateCategoryForm(
        name_en=template_category["name_en"],
        name_fr=template_category["name_fr"],
        description_en=template_category["description_en"],
        description_fr=template_category["description_fr"],
        hidden=template_category["hidden"],
        email_process_type=template_category["email_process_type"],
        sms_process_type=template_category["sms_process_type"],
    )

    return render_template(
        "views/templates/template_category.html", search_form=SearchByNameForm(), template_category=template_category, form=form
    )


@main.route("/template-categories")
@main.route("/template-category/add", methods=["GET", "POST"])
@user_is_platform_admin
def add_template_category():
    form = TemplateCategoryForm()

    if form.validate_on_submit():
        template_category_api_client.create_template_category(
            name_en=form.data["name_en"],
            name_fr=form.data["name_fr"],
            description_en=form.data["description_en"],
            description_fr=form.data["description_fr"],
            hidden=form.data["hidden"],
            email_process_type=form.data["email_process_type"],
            sms_process_type=form.data["sms_process_type"],
            sms_sending_vehicle=form.data["sms_sending_vehicle"],
        )
        flash(
            _("Template category '{}' added.").format(
                form.data["name_en"] if session["userlang"] == "en" else form.data["name_fr"]
            ),
            "default_with_tick",
        )
        return redirect(url_for(".template_categories"))

    return render_template("views/templates/template_category.html", search_form=SearchByNameForm(), form=form)


@main.route("/template-category/<template_category_id>", methods=["GET", "POST"])
@user_is_platform_admin
def template_category(template_category_id):
    template_category = template_category_api_client.get_template_category(template_category_id)
    form = TemplateCategoryForm(
        name_en=template_category["name_en"],
        name_fr=template_category["name_fr"],
        description_en=template_category["description_en"],
        description_fr=template_category["description_fr"],
        hidden=template_category["hidden"],
        email_process_type=template_category["email_process_type"],
        sms_process_type=template_category["sms_process_type"],
        sms_sending_vehicle=template_category["sms_sending_vehicle"],
    )

    if form.validate_on_submit():
        template_category_api_client.update_template_category(
            template_category_id,
            name_en=form.data["name_en"],
            name_fr=form.data["name_fr"],
            description_en=form.data["description_en"],
            description_fr=form.data["description_fr"],
            hidden=form.data["hidden"],
            email_process_type=form.data["email_process_type"],
            sms_process_type=form.data["sms_process_type"],
            sms_sending_vehicle=form.data["sms_sending_vehicle"],
        )
        flash(
            _("Template category '{}' saved.").format(
                form.data["name_en"] if session["userlang"] == "en" else form.data["name_fr"]
            ),
            "default_with_tick",
        )
        return redirect(url_for(".template_categories"))

    return render_template(
        "views/templates/template_category.html", search_form=SearchByNameForm(), template_category=template_category, form=form
    )
