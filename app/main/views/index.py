import re
from datetime import datetime

from flask import (
    abort,
    current_app,
    g,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_babel import _
from flask_login import current_user
from notifications_utils.international_billing_rates import INTERNATIONAL_BILLING_RATES
from notifications_utils.template import HTMLEmailTemplate, LetterImageTemplate

from app import email_branding_client, get_current_locale, letter_branding_client
from app.articles import (
    _get_alt_locale,
    get_lang_url,
    get_preview_url,
    set_active_nav_item,
)
from app.articles.menu import get_nav_items
from app.articles.pages import (
    get_page_by_id,
    get_page_by_slug,
    get_page_by_slug_with_cache,
)
from app.articles.routing import gca_url_for
from app.main import main
from app.main.forms import (
    FieldWithLanguageOptions,
    FieldWithNoneOption,
    SearchByNameForm,
)
from app.utils import (
    Spreadsheet,
    documentation_url,
    get_latest_stats,
    get_logo_cdn_domain,
    user_is_logged_in,
)


@main.route("/")
def index():
    if current_user and current_user.is_authenticated:
        return redirect(url_for("main.choose_account"))

    path = "home" if get_current_locale(current_app) == "en" else "accueil"
    return page_content(path=path)


@main.route("/robots.txt")
def robots():
    robot_rules = [
        "User-agent: *",
        "Disallow: /sign-in",
        "Disallow: /contact",
        "Disallow: /register",
    ]
    return ("\n".join(robot_rules)), 200, {"Content-Type": "text/plain"}


@main.route("/.well-known/security.txt")
def security_txt():
    security_policy = gca_url_for("security", _external=True)
    security_info = [
        f'Contact: mailto:{current_app.config["SECURITY_EMAIL"]}',
        "Preferred-Languages: en, fr",
        f"Policy: {security_policy}",
        "Hiring: https://digital.canada.ca/join-our-team/",
        "Hiring: https://numerique.canada.ca/rejoindre-notre-equipe/",
    ]
    return ("\n".join(security_info)), 200, {"Content-Type": "text/plain"}


@main.route("/error/<int:status_code>")
def error(status_code):
    if status_code >= 500:
        abort(404)
    abort(status_code)


@main.route("/verify-mobile")
@user_is_logged_in
def verify_mobile():
    return render_template("views/verify-mobile.html")


@main.route("/pricing")
def pricing():
    return render_template(
        "views/pricing/index.html",
        sms_rate=0.0158,
        international_sms_rates=sorted(
            [(cc, country["names"], country["billable_units"]) for cc, country in INTERNATIONAL_BILLING_RATES.items()],
            key=lambda x: x[0],
        ),
        search_form=SearchByNameForm(),
    )


@main.route("/design-patterns-content-guidance")
def design_content():
    return render_template("views/design-patterns-content-guidance.html")


@main.route("/_email")
def email_template():
    branding_type = "fip_english"
    branding_style = request.args.get("branding_style", None)

    if (
        branding_style == FieldWithLanguageOptions.ENGLISH_OPTION_VALUE
        or branding_style == FieldWithLanguageOptions.FRENCH_OPTION_VALUE
    ):
        if branding_style == FieldWithLanguageOptions.FRENCH_OPTION_VALUE:
            branding_type = "fip_french"
        branding_style = None

    if branding_style is not None:
        email_branding = email_branding_client.get_email_branding(branding_style)["email_branding"]
        branding_type = email_branding["brand_type"]

    if branding_type == "fip_english":
        brand_text = None
        brand_colour = None
        brand_logo = None
        fip_banner_english = True
        fip_banner_french = False
        logo_with_background_colour = False
        brand_name = None
        alt_text_en = "The canada wordmark is displayed at the bottom right."
        alt_text_fr = "Le mot-symbole canada est affiché en bas à droite."
    elif branding_type == "fip_french":
        brand_text = None
        brand_colour = None
        brand_logo = None
        fip_banner_english = False
        fip_banner_french = True
        logo_with_background_colour = False
        brand_name = None
        alt_text_en = "The canada wordmark is displayed at the bottom right."
        alt_text_fr = "Le mot-symbole canada est affiché en bas à droite."
    else:
        colour = email_branding["colour"]
        brand_text = email_branding["text"]
        brand_colour = colour
        brand_logo = "https://{}/{}".format(get_logo_cdn_domain(), email_branding["logo"]) if email_branding["logo"] else None
        fip_banner_english = branding_type in ["fip_english", "both_english"]
        fip_banner_french = branding_type in ["fip_french", "both_french"]
        logo_with_background_colour = branding_type == "custom_logo_with_background_colour"
        brand_name = email_branding["name"]
        alt_text_en = email_branding["alt_text_en"]
        alt_text_fr = email_branding["alt_text_fr"]

    template = {
        "subject": "foo",
        "content": "# Email preview\n{}\n{}".format(
            _("An example email showing the {} at the top left.").format(brand_name),
            _("The canada wordmark is displayed at the bottom right."),
        ),
    }

    if not bool(request.args):
        resp = make_response(render_template("views/email-branding/_preview.html", template=str(HTMLEmailTemplate(template))))
    else:
        resp = make_response(
            render_template(
                "views/email-branding/_preview.html",
                template=str(
                    HTMLEmailTemplate(
                        template,
                        fip_banner_english=fip_banner_english,
                        fip_banner_french=fip_banner_french,
                        brand_text=brand_text,
                        brand_colour=brand_colour,
                        brand_logo=brand_logo,
                        logo_with_background_colour=logo_with_background_colour,
                        brand_name=brand_name,
                        alt_text_en=alt_text_en,
                        alt_text_fr=alt_text_fr,
                    )
                ),
            )
        )

    resp.headers["X-Frame-Options"] = "SAMEORIGIN"
    return resp


@main.route("/_letter")
def letter_template():
    branding_style = request.args.get("branding_style")

    if branding_style == FieldWithNoneOption.NONE_OPTION_VALUE:
        branding_style = None

    if branding_style:
        filename = letter_branding_client.get_letter_branding(branding_style)["filename"]
    else:
        filename = "no-branding"

    template = {"subject": "", "content": ""}
    image_url = url_for("main.letter_branding_preview_image", filename=filename)

    template_image = str(
        LetterImageTemplate(
            template,
            image_url=image_url,
            page_count=1,
        )
    )

    resp = make_response(render_template("views/service-settings/letter-preview.html", template=template_image))

    resp.headers["X-Frame-Options"] = "SAMEORIGIN"
    return resp


@main.route("/documentation")
def documentation():
    return redirect(documentation_url(), code=301)


@main.route("/callbacks")
def callbacks():
    return redirect(documentation_url("callbacks"), code=301)


@main.route("/roadmap", endpoint="roadmap")
def roadmap():
    return render_template("views/roadmap.html")


@main.route("/email", endpoint="email")
def features_email():
    return render_template("views/emails.html")


@main.route("/sms", endpoint="sms")
def features_sms():
    return render_template("views/text-messages.html")


@main.route("/letters", endpoint="letters")
def features_letters():
    return render_template("views/letters.html")


@main.route("/welcome", endpoint="welcome")
def welcome():
    # fake a form field
    class FakeFormField(object):
        pass

    template_content = FakeFormField()
    template_content.id = "testing"

    return render_template(
        "views/welcome.html", default_limit=current_app.config["DEFAULT_SERVICE_LIMIT"], template_content=template_content
    )


@main.route("/activity", endpoint="activity")
def activity():
    return render_template("views/activity.html", **get_latest_stats(get_current_locale(current_app), filter_heartbeats=True))


@main.route("/activity/download", endpoint="activity_download")
def activity_download():
    stats = get_latest_stats(get_current_locale(current_app))["monthly_stats"]

    csv_data = [["date", "sms_count", "email_count", "total"]]
    for date, row in stats.items():
        csv_data.append([row["year_month"], row["sms"], row["email"], row["total"]])

    return (
        Spreadsheet.from_rows(csv_data).as_csv_data,
        200,
        {
            "Content-Type": "text/csv; charset=utf-8",
            "Content-Disposition": 'inline; filename="{} activity.csv"'.format(
                datetime.utcnow().strftime("%Y-%m-%d"),
            ),
        },
    )


# --- Internal Redirects --- #
@main.route("/features/roadmap", endpoint="redirect_roadmap")
@main.route("/features/email", endpoint="redirect_email")
@main.route("/features/sms", endpoint="redirect_sms")
@main.route("/features/letters", endpoint="redirect_letters")
def old_page_redirects():
    return redirect(url_for(request.endpoint.replace("redirect_", "")), code=301)


# --- GCA Redirects --- #
@main.route("/a11y", endpoint="accessibility")
@main.route("/why-notify", endpoint="whynotify")
@main.route("/personalise", endpoint="personalisation_guide")
@main.route("/format", endpoint="formatting_guide")
@main.route("/messages-status", endpoint="message_delivery_status")
@main.route("/pourquoi-gc-notification", endpoint="whynotify")
def gca_redirects():
    return redirect(gca_url_for(request.endpoint.replace("main.", "")), code=301)


"""Dynamic routes handling for GCArticles API-driven pages"""


@main.route("/preview")
def preview_content():
    if not request.args.get("id"):
        abort(404)

    """User must be authenticated"""
    if not current_user.is_authenticated:
        abort(404)

    """Append the page_id to the request endpoint"""
    page_id = request.args.get("id")
    endpoint = f"wp/v2/pages/{page_id}"

    """'g' sets a global variable for this request for use in the template"""
    g.preview_url = get_preview_url(page_id)

    response = get_page_by_id(endpoint)

    return _render_articles_page(response)


@main.route("/<path:path>")
def page_content(path=""):
    endpoint = "wp/v2/pages"
    lang = get_current_locale(current_app)

    params = {"slug": path, "lang": lang}

    """If user is authenticated, don't cache it"""
    if current_user.is_authenticated:
        response = get_page_by_slug(endpoint, params=params)
    else:
        response = get_page_by_slug_with_cache(endpoint, params=params)

    if not response:
        return _try_alternate_language(endpoint, params)

    if isinstance(response, list):
        response = response[0]

    return _render_articles_page(response)


def _render_articles_page(response):
    title = response["title"]["rendered"]
    slug_en = response["slug_en"]
    html_content = response["content"]["rendered"]
    page_id = request.args.get("id")

    nav_items = get_nav_items()
    set_active_nav_item(nav_items, request.path)

    return render_template(
        "views/page-content.html",
        title=title,
        html_content=html_content,
        nav_items=nav_items,
        slug=slug_en,
        lang_url=get_lang_url(response, bool(page_id)),
        stats=get_latest_stats(get_current_locale(current_app), filter_heartbeats=True) if slug_en == "home" else None,
        isHome=True if slug_en == "home" else None,
    )


def _try_alternate_language(endpoint, params):
    """
    If response was empty, it's possible the logged-in user's current language
    doesn't match the requested page language, so let's try again.
    """
    slug = params.get("slug")

    """try again, with same slug but new language"""
    params["lang"] = _get_alt_locale(params.get("lang"))
    response = get_page_by_slug(endpoint, params=params)

    if isinstance(response, list):
        response = response[0]

    """if we get a response for the other language, redirect"""
    if response:
        if re.match(r"^[A-Za-z0-9_\-]+$", slug):
            return redirect(f"/set-lang?from=/{slug}")

    abort(404)
