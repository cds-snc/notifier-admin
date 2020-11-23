from flask import Blueprint

main = Blueprint('main', __name__)

from app.main.views import (  # noqa isort:skip
    add_service,
    agreement,
    api_keys,
    choose_account,
    code_not_received,
    contact,
    dashboard,
    email_branding,
    find_services,
    find_users,
    forgot_password,
    inbound_number,
    index,
    invites,
    jobs,
    letter_branding,
    manage_users,
    new_password,
    notifications,
    organisations,
    platform_admin,
    providers,
    register,
    send,
    service_settings,
    set_lang,
    sign_in,
    sign_out,
    smtp,
    styleguide,
    templates,
    two_factor,
    uploads,
    user_profile,
    verify,
)
