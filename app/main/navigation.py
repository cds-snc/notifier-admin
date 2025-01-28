from flask import current_app, url_for
from flask_babel import _
from flask_login import current_user

from app import current_service, get_current_locale
from app.articles.routing import gca_url_for
from app.utils import documentation_url


def get_footer():
    lang = get_current_locale(current_app)
    return [
        {
            "id": "about",
            "name": _("About"),
            "links": {
                _("Why GC Notify"): gca_url_for("whynotify"),
                _("Features"): gca_url_for("features"),
                _("New features"): gca_url_for("new_features"),
                _("Activity on GC Notify"): url_for("main.activity"),
            },
        },
        {
            "id": "usage",
            "name": _("Using GC Notify"),
            "links": {
                _("API documentation"): documentation_url(),
                _("Guidance"): gca_url_for("guidance"),
                _("Sitemap"): url_for("main.sitemap"),
                _("Service level objectives"): gca_url_for("service-level-objectives"),
            },
        },
        {
            "id": "support",
            "name": _("Support"),
            "links": {
                _("Contact us"): url_for("main.contact"),
                _("System status"): current_app.config["SYSTEM_STATUS_URL"] + ("/#fr" if lang == "fr" else ""),
            },
        },
    ]


def get_sub_footer():
    return {
        _("Privacy"): gca_url_for("privacy"),
        _("Security"): gca_url_for("security"),
        _("Accessibility"): gca_url_for("accessibility"),
        _("Terms of use"): gca_url_for("terms"),
        _("Service level agreement"): gca_url_for("service-level-agreement"),
    }


def get_public_nav():
    return [
        {"name": _("Home"), "url": url_for("main.index")},
        {"name": _("Why GC Notify"), "url": gca_url_for("whynotify")},
        {"name": _("Features"), "url": gca_url_for("features")},
        {"name": _("API documentation"), "url": documentation_url()},
        {"name": _("Contact us"), "url": url_for("main.contact")},
    ]


def get_user_nav():
    nav_items = []

    if current_user.platform_admin:
        nav_items.append({"name": _("Admin panel"), "url": url_for("main.live_services")})

    if current_user.has_permissions():
        nav_items.append({"name": _("Dashboard"), "url": url_for("main.service_dashboard", service_id=current_service.id)})
        nav_items.append({"name": _("Templates"), "url": url_for("main.choose_template", service_id=current_service.id)})
    else:
        nav_items.append({"name": _("Your services"), "url": url_for("main.choose_account")})

    if current_user.has_permissions("manage_api_keys"):
        nav_items.append({"name": _("API integration"), "url": url_for("main.api_integration", service_id=current_service.id)})

    if current_user.has_permissions():
        nav_items.append({"name": _("Team members"), "url": url_for("main.manage_users", service_id=current_service.id)})

    if current_user.has_permissions("manage_api_keys"):
        nav_items.append({"name": _("Settings"), "url": url_for("main.service_settings", service_id=current_service.id)})

    return nav_items


def get_main_nav():
    nav = get_public_nav()
    if current_user.is_authenticated:
        nav = get_user_nav()

    return nav


def get_account_nav():
    nav = [
        {"name": _("Your services"), "url": url_for("main.choose_account")},
        {"name": _("Your profile"), "url": url_for("main.user_profile")},
        {"name": _("Sign out"), "url": url_for("main.sign_out")},
    ]

    # Admin panel if admin
    if current_user.is_authenticated:
        if current_user.platform_admin:
            nav.insert(0, {"name": _("Admin panel"), "url": url_for("main.live_services")})

    return nav
