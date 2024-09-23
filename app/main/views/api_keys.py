from flask import Markup, abort, flash, g, redirect, render_template, request, url_for
from flask_babel import lazy_gettext as _l
from flask_login import current_user

from app import (
    api_key_api_client,
    current_service,
    notification_api_client,
    service_api_client,
)
from app.main import main
from app.main.forms import (
    CreateKeyForm,
    Safelist,
    ServiceDeliveryStatusCallbackForm,
    ServiceReceiveMessagesCallbackForm,
)
from app.notify_client.api_key_api_client import (
    KEY_TYPE_NORMAL,
    KEY_TYPE_TEAM,
    KEY_TYPE_TEST,
)
from app.utils import documentation_url, email_safe, user_has_permissions

dummy_bearer_token = "bearer_token_set"


@main.route("/services/<service_id>/api")
@user_has_permissions("manage_api_keys")
def api_integration(service_id):
    callbacks_link = ".api_callbacks" if current_service.has_permission(
        "inbound_sms") else ".delivery_status_callback"
    return render_template(
        "views/api/index.html",
        callbacks_link=callbacks_link,
        api_notifications=notification_api_client.get_api_notifications_for_service(
            service_id),
    )


@main.route("/services/<service_id>/api/documentation")
@user_has_permissions("manage_api_keys")
def api_documentation(service_id):
    return redirect(documentation_url(), code=301)


@main.route("/services/<service_id>/api/safelist", methods=["GET", "POST"])
@user_has_permissions("manage_api_keys")
def safelist(service_id):
    form = Safelist()
    if form.validate_on_submit():
        service_api_client.update_safelist(
            service_id,
            {
                "email_addresses": list(filter(None, form.email_addresses.data)),
                "phone_numbers": list(filter(None, form.phone_numbers.data)),
            },
        )
        flash(_l("Safelist updated"), "default_with_tick")
        return redirect(url_for(".api_integration", service_id=service_id))
    if not form.errors:
        form.populate(**service_api_client.get_safelist(service_id))
    return render_template("views/api/safelist.html", form=form)


@main.route("/services/<service_id>/api/keys")
@user_has_permissions("manage_api_keys")
def api_keys(service_id):
    for item in current_service.api_keys:
        results = api_key_api_client.get_api_key_statistics(key_id=item["id"])
        item["email_sends"] = results["email_sends"]
        item["sms_sends"] = results["sms_sends"]
        item["total_sends"] = results["total_sends"]
        item["last_send"] = results["last_send"]
    return render_template(
        "views/api/keys.html",
    )


@main.route("/services/<service_id>/api/keys/create", methods=["GET", "POST"])
@user_has_permissions("manage_api_keys", restrict_admin_usage=True)
def create_api_key(service_id):
    form = CreateKeyForm(current_service.api_keys)
    form.key_type.choices = [
        (KEY_TYPE_NORMAL, _l("Live – sends to anyone")),
        (KEY_TYPE_TEAM, _l("Team and safelist – limits who you can send to")),
        (KEY_TYPE_TEST, _l("Test – pretends to send messages")),
    ]
    disabled_options, option_hints = [], {}
    if current_service.trial_mode:
        disabled_options = [KEY_TYPE_NORMAL]
        option_hints[KEY_TYPE_NORMAL] = Markup(
            _l("Not available because your service is in trial mode."))
    if current_service.has_permission("letter"):
        option_hints[KEY_TYPE_TEAM] = ""
    if form.validate_on_submit():
        if form.key_type.data in disabled_options:
            abort(400)
        keydata = api_key_api_client.create_api_key(
            service_id=service_id,
            key_name=form.key_name.data,
            key_type=form.key_type.data,
        )
        return render_template(
            "views/api/keys/show.html",
            secret=keydata["key"],
            service_id=service_id,
            key_name=email_safe(keydata["key_name"], whitespace="_"),
        )
    return render_template(
        "views/api/keys/create.html",
        form=form,
        disabled_options=disabled_options,
        option_hints=option_hints,
    )


@main.route("/services/<service_id>/api/keys/revoke/<key_id>", methods=["GET", "POST"])
@user_has_permissions("manage_api_keys")
def revoke_api_key(service_id, key_id):
    key_name = current_service.get_api_key(key_id)["name"]
    if request.method == "GET":
        flash(
            [
                "{} ‘{}’?".format(
                    _l("Are you sure you want to revoke"), key_name),
                _l("You will not be able to use this API key to connect to GC Notify"),
            ],
            "revoke this API key",
        )
        return render_template(
            "views/api/keys.html",
        )
    elif request.method == "POST":
        api_key_api_client.revoke_api_key(service_id=service_id, key_id=key_id)
        flash("‘{}’ {}".format(key_name, _l("was revoked")), "default_with_tick")
        return redirect(url_for(".api_keys", service_id=service_id))


def get_apis():
    callback_api = None
    inbound_api = None
    if current_service.service_callback_api:
        callback_api = service_api_client.get_service_callback_api(
            current_service.id, current_service.service_callback_api[0])
    if current_service.inbound_api:
        inbound_api = service_api_client.get_service_inbound_api(
            current_service.id, current_service.inbound_api[0])

    return (callback_api, inbound_api)


def check_token_against_dummy_bearer(token):
    if token != dummy_bearer_token:
        return token
    else:
        return ""


@main.route("/services/<service_id>/api/callbacks", methods=["GET"])
@user_has_permissions("manage_api_keys")
def api_callbacks(service_id):
    if not current_service.has_permission("inbound_sms"):
        return redirect(url_for(".delivery_status_callback", service_id=service_id))

    delivery_status_callback, received_text_messages_callback = get_apis()

    return render_template(
        "views/api/callbacks.html",
        received_text_messages_callback=received_text_messages_callback[
            "url"] if received_text_messages_callback else None,
        delivery_status_callback=delivery_status_callback["url"] if delivery_status_callback else None,
    )


def get_delivery_status_callback_details():
    if current_service.service_callback_api:
        return service_api_client.get_service_callback_api(current_service.id, current_service.service_callback_api[0])


@main.route("/services/<service_id>/api/callbacks/delivery-status-callback/delete", methods=["GET", "POST"])
@user_has_permissions("manage_api_keys")
def delete_delivery_status_callback(service_id):
    delivery_status_callback = get_delivery_status_callback_details()
    back_link = ".api_callbacks" if current_service.has_permission(
        "inbound_sms") else ".api_integration"
    url_hint_txt = "Must start with https://"

    if request.method == "POST":
        if delivery_status_callback:
            service_api_client.delete_service_callback_api(
                service_id,
                delivery_status_callback["id"],
            )

            flash(_l("Your Callback configuration has been deleted."),
                  "default_with_tick")
            return redirect(url_for(back_link, service_id=service_id))

        flash(["{}".format(
            _l("Are you sure you want to delete this callback configuration?"))], "delete")

    form = ServiceDeliveryStatusCallbackForm(
        url=delivery_status_callback.get(
            "url") if delivery_status_callback else "",
        bearer_token=dummy_bearer_token if delivery_status_callback else "",
    )

    return render_template(
        "views/api/callbacks/delivery-status-callback.html",
        back_link=".api_callbacks" if current_service.has_permission(
            "inbound_sms") else ".delivery_status_callback",
        hint_text=url_hint_txt,
        is_deleting=True,
        form=form,
    )


@main.route(
    "/services/<service_id>/api/callbacks/delivery-status-callback",
    methods=["GET", "POST"],
)
@user_has_permissions("manage_api_keys")
def delivery_status_callback(service_id):
    delivery_status_callback = get_delivery_status_callback_details()
    back_link = ".api_callbacks" if current_service.has_permission(
        "inbound_sms") else ".api_integration"
    url_hint_txt = _l("Must start with https://")

    form = ServiceDeliveryStatusCallbackForm(
        url=delivery_status_callback.get(
            "url") if delivery_status_callback else "",
        bearer_token=dummy_bearer_token if delivery_status_callback else "",
    )

    if form.validate_on_submit():
        # As part of the ValidCallbackUrl validation, we ping their callback URL to check if it's up and set the response time in g
        response_time = "{:.2f}".format(g.callback_response_time)
        url_hostname = form.url.data.split("https://")[1]

        # Update existing callback
        if delivery_status_callback and form.url.data:
            if delivery_status_callback.get("url") != form.url.data or form.bearer_token.data != dummy_bearer_token:
                service_api_client.update_service_callback_api(
                    service_id,
                    url=form.url.data,
                    bearer_token=check_token_against_dummy_bearer(
                        form.bearer_token.data),
                    user_id=current_user.id,
                    callback_api_id=delivery_status_callback.get("id"),
                )

                # If the user is just testing their URL, don't send them back to the API Integration page
                if request.form.get("button_pressed") == "test_response_time":
                    flash(
                        _l("The service {} responded in {} seconds.").format(
                            url_hostname,
                            response_time,
                        ),
                        "default_with_tick",
                    )
                    return redirect(url_for("main.delivery_status_callback", service_id=service_id))

                flash(
                    _l("We’ve saved your callback configuration. {} responded in {} seconds.").format(
                        url_hostname,
                        response_time,
                    ),
                    "default_with_tick",
                )

                return redirect(url_for(back_link, service_id=service_id))
        # Create a new callback
        elif form.url.data:
            service_api_client.create_service_callback_api(
                service_id,
                url=form.url.data,
                bearer_token=form.bearer_token.data,
                user_id=current_user.id,
            )

            flash(
                _l("We’ve set up your callback configuration. {} responded in {} seconds.").format(
                    url_hostname,
                    response_time,
                ),
                "default_with_tick",
            )

            return redirect(url_for(back_link, service_id=service_id))
        else:
            # If no callback is set up and the user chooses to continue
            # having no callback (ie both fields empty) then there’s
            # nothing for us to do here
            pass

        if request.form.get("button_pressed") == "test_response_time" and g.callback_response_time >= 1:
            flash(
                _l("The service {} took longer than 1 second to respond.").format(
                    url_hostname,
                ),
                "error",
            )
            return redirect(url_for("main.delivery_status_callback", service_id=service_id))
        else:
            flash(
                _l("The service {} responded in {} seconds.").format(
                    url_hostname,
                    response_time,
                ),
                "default_with_tick",
            )
            return redirect(url_for("main.delivery_status_callback", service_id=service_id))

    return render_template(
        "views/api/callbacks/delivery-status-callback.html",
        has_callback_config=delivery_status_callback is not None,
        back_link=back_link,
        hint_text=url_hint_txt,
        form=form,
    )


def get_received_text_messages_callback():
    if current_service.inbound_api:
        return service_api_client.get_service_inbound_api(current_service.id, current_service.inbound_api[0])


@main.route(
    "/services/<service_id>/api/callbacks/received-text-messages-callback",
    methods=["GET", "POST"],
)
@user_has_permissions("manage_api_keys")
def received_text_messages_callback(service_id):
    if not current_service.has_permission("inbound_sms"):
        return redirect(url_for(".api_integration", service_id=service_id))
    back_link = ".api_callbacks" if current_service.has_permission(
        "inbound_sms") else ".api_integration"

    received_text_messages_callback = get_received_text_messages_callback()
    form = ServiceReceiveMessagesCallbackForm(
        url=received_text_messages_callback.get(
            "url") if received_text_messages_callback else "",
        bearer_token=dummy_bearer_token if received_text_messages_callback else "",
    )
    url_hint_txt = _l("Must start with https://")

    if form.validate_on_submit():
        # As part of the ValidCallbackUrl validation, we ping their callback URL to check if it's up and set the response time in g
        response_time = "{:.2f}".format(g.callback_response_time)
        url_hostname = form.url.data.split("https://")[1]

        if received_text_messages_callback and form.url.data:
            if received_text_messages_callback.get("url") != form.url.data or form.bearer_token.data != dummy_bearer_token:
                service_api_client.update_service_inbound_api(
                    service_id,
                    url=form.url.data,
                    bearer_token=check_token_against_dummy_bearer(
                        form.bearer_token.data),
                    user_id=current_user.id,
                    inbound_api_id=received_text_messages_callback.get("id"),
                )

                # If the user is just testing their URL, don't send them back to the API Integration page
                if request.form.get("button_pressed") == "test_response_time":
                    flash(
                        _l("The service {} responded in {} seconds.").format(
                            url_hostname,
                            response_time,
                        ),
                        "default_with_tick",
                    )
                    return redirect(url_for("main.received_text_messages_callback", service_id=service_id))

                flash(
                    _l("We’ve saved your callback configuration. {} responded in {} seconds.").format(
                        url_hostname,
                        response_time,
                    ),
                    "default_with_tick",
                )

        elif received_text_messages_callback and not form.url.data:
            service_api_client.delete_service_inbound_api(
                service_id,
                received_text_messages_callback["id"],
            )
        elif form.url.data:
            service_api_client.create_service_inbound_api(
                service_id,
                url=form.url.data,
                bearer_token=form.bearer_token.data,
                user_id=current_user.id,
            )
            flash(
                _l("We’ve set up your callback configuration. {} responded in {} seconds.").format(
                    url_hostname,
                    response_time,
                ),
                "default_with_tick",
            )

            return redirect(url_for(back_link, service_id=service_id))

        if request.form.get("button_pressed") == "test_response_time" and g.callback_response_time >= 1:
            flash(
                _l("The service {} took longer than 1 second to respond.").format(
                    url_hostname,
                ),
                "error",
            )
            return redirect(url_for("main.received_text_messages_callback", service_id=service_id))
        else:
            flash(
                _l("The service {} responded in {} seconds.").format(
                    url_hostname,
                    response_time,
                ),
                "default_with_tick",
            )
            return redirect(url_for("main.received_text_messages_callback", service_id=service_id))

    return render_template(
        "views/api/callbacks/received-text-messages-callback.html",
        has_callback_config=received_text_messages_callback is not None,
        form=form,
        hint_text=url_hint_txt,
    )


@main.route("/services/<service_id>/api/callbacks/received-text-messages-callback/delete", methods=["GET", "POST"])
@user_has_permissions("manage_api_keys")
def delete_received_text_messages_callback(service_id):
    received_text_messages_callback = get_received_text_messages_callback()
    back_link = ".api_callbacks" if current_service.has_permission(
        "inbound_sms") else ".api_integration"
    url_hint_txt = "Must start with https://"

    if request.method == "POST":
        if received_text_messages_callback:
            service_api_client.delete_service_inbound_api(
                service_id,
                received_text_messages_callback["id"],
            )

            flash(_l("Your Callback configuration has been deleted."),
                  "default_with_tick")
            return redirect(url_for(back_link, service_id=service_id))

    flash(["{}".format(
        _l("Are you sure you want to delete this callback configuration?"))], "delete")

    form = ServiceReceiveMessagesCallbackForm(
        url=received_text_messages_callback.get(
            "url") if delivery_status_callback else "",
        bearer_token=dummy_bearer_token if received_text_messages_callback else "",
    )

    return render_template(
        "views/api/callbacks/delivery-status-callback.html",
        back_link=".api_callbacks" if current_service.has_permission(
            "inbound_sms") else ".delivery_status_callback",
        hint_text=url_hint_txt,
        is_deleting=True,
        form=form,
    )
