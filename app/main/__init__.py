from flask import Blueprint

main = Blueprint("main", __name__)

from app.main.navigation import get_account_nav, get_footer, get_main_nav, get_sub_footer

from app.main.views import (  # noqa isort:skip
    add_service,
    api_keys,
    choose_account,
    code_not_received,
    contact,
    dashboard,
    email_branding,
    find_services,
    find_users,
    find_ids,
    forgot_password,
    inbound_number,
    index,
    invites,
    jobs,
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
    storybook,
    styleguide,
    templates,
    two_factor,
    uploads,
    user_profile,
    verify,
)


@main.context_processor
def navigation():
    return {
        "footer_navigation": get_footer(),
        "sub_footer_navigation": get_sub_footer(),
        "main_navigation": get_main_nav(),
        "account_navigation": get_account_nav(),
    }
