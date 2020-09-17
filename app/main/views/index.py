from flask import (
    abort,
    current_app,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user
from notifications_utils.international_billing_rates import (
    INTERNATIONAL_BILLING_RATES,
)
from notifications_utils.template import HTMLEmailTemplate, LetterImageTemplate

from app import (
    email_branding_client,
    get_current_locale,
    letter_branding_client,
    user_api_client,
)
from app.main import main
from app.main.forms import (
    ContactNotifyTeam,
    FieldWithLanguageOptions,
    FieldWithNoneOption,
    SearchByNameForm,
)
from app.main.views.sub_navigation_dictionaries import features_nav
from app.utils import get_latest_stats, get_logo_cdn_domain, user_is_logged_in


@main.route('/', methods=['GET', 'POST'])
def index():

    lang = get_current_locale(current_app)

    if current_user and current_user.is_authenticated:
        return redirect(url_for('main.choose_account'))

    form = ContactNotifyTeam()

    # catch with the honeypot field
    if(form.phone.data):
        return redirect(url_for('.feedback', ticket_type='thanks'))

    if form.validate_on_submit():
        # send email here
        user_api_client.send_contact_email(form.name.data, form.email_address.data, form.feedback.data, form.support_type.data)

        return redirect(url_for('.feedback', ticket_type='thanks'))

    stats = get_latest_stats(lang)

    if request.method == 'POST':
        return render_template(
            'views/signedout.html',
            form=form,
            scrollTo="true",
            stats=stats
        )

    return render_template(
        'views/signedout.html',
        form=form,
        scrollTo="false",
        stats=stats
    )


@main.route('/robots.txt')
def robots():
    return (
        'User-agent: *\n'
        'Disallow: /sign-in\n'
        'Disallow: /contact\n'
        'Disallow: /register\n'
    ), 200, {'Content-Type': 'text/plain'}


@main.route('/error/<int:status_code>')
def error(status_code):
    if status_code >= 500:
        abort(404)
    abort(status_code)


@main.route("/verify-mobile")
@user_is_logged_in
def verify_mobile():
    return render_template('views/verify-mobile.html')


@main.route('/cookies')
def cookies():
    abort(404)
    return render_template('views/cookies.html')


@main.route('/privacy')
def privacy():
    return render_template('views/privacy.html')


@main.route('/pricing')
def pricing():
    return render_template(
        'views/pricing/index.html',
        sms_rate=0.0158,
        international_sms_rates=sorted([
            (cc, country['names'], country['billable_units'])
            for cc, country in INTERNATIONAL_BILLING_RATES.items()
        ], key=lambda x: x[0]),
        search_form=SearchByNameForm(),
    )


@main.route('/design-patterns-content-guidance')
def design_content():
    return render_template('views/design-patterns-content-guidance.html')


@main.route('/_email')
def email_template():
    branding_type = 'fip_english'
    branding_style = request.args.get('branding_style', None)

    if (branding_style == FieldWithLanguageOptions.ENGLISH_OPTION_VALUE
       or branding_style == FieldWithLanguageOptions.FRENCH_OPTION_VALUE):
        if branding_style == FieldWithLanguageOptions.FRENCH_OPTION_VALUE:
            branding_type = 'fip_french'
        branding_style = None

    if branding_style is not None:
        email_branding = email_branding_client.get_email_branding(branding_style)['email_branding']
        branding_type = email_branding['brand_type']

    if branding_type == 'fip_english':
        brand_text = None
        brand_colour = None
        brand_logo = None
        fip_banner_english = True
        fip_banner_french = False
        logo_with_background_colour = False
        brand_name = None
    elif branding_type == 'fip_french':
        brand_text = None
        brand_colour = None
        brand_logo = None
        fip_banner_english = False
        fip_banner_french = True
        logo_with_background_colour = False
        brand_name = None
    else:
        colour = email_branding['colour']
        brand_text = email_branding['text']
        brand_colour = colour
        brand_logo = ('https://{}/{}'.format(get_logo_cdn_domain(), email_branding['logo'])
                      if email_branding['logo'] else None)
        fip_banner_english = branding_type in ['fip_english', 'both_english']
        fip_banner_french = branding_type in ['fip_french', 'both_french']
        logo_with_background_colour = branding_type == 'custom_logo_with_background_colour'
        brand_name = email_branding['name']

    template = {
        'subject': 'foo',
        'content': (
            'Lorem Ipsum is simply dummy text of the printing and typesetting '
            'industry.\n\nLorem Ipsum has been the industry’s standard dummy '
            'text ever since the 1500s, when an unknown printer took a galley '
            'of type and scrambled it to make a type specimen book. '
            '\n\n'
            '# History'
            '\n\n'
            'It has '
            'survived not only'
            '\n\n'
            '* five centuries'
            '\n'
            '* but also the leap into electronic typesetting'
            '\n\n'
            'It was '
            'popularised in the 1960s with the release of Letraset sheets '
            'containing Lorem Ipsum passages, and more recently with desktop '
            'publishing software like Aldus PageMaker including versions of '
            'Lorem Ipsum.'
            '\n\n'
            '^ It is a long established fact that a reader will be distracted '
            'by the readable content of a page when looking at its layout.'
            '\n\n'
            'The point of using Lorem Ipsum is that it has a more-or-less '
            'normal distribution of letters, as opposed to using ‘Content '
            'here, content here’, making it look like readable English.'
            '\n\n\n'
            '1. One'
            '\n'
            '2. Two'
            '\n'
            '10. Three'
            '\n\n'
            'This is an example of an email sent using Notification.'
            '\n\n'
            'https://www.notifications.service.gov.uk'
        )
    }

    if not bool(request.args):
        resp = make_response(str(HTMLEmailTemplate(template)))
    else:
        resp = make_response(str(HTMLEmailTemplate(
            template,
            fip_banner_english=fip_banner_english,
            fip_banner_french=fip_banner_french,
            brand_text=brand_text,
            brand_colour=brand_colour,
            brand_logo=brand_logo,
            logo_with_background_colour=logo_with_background_colour,
            brand_name=brand_name,
        )))

    resp.headers['X-Frame-Options'] = 'SAMEORIGIN'
    return resp


@main.route('/_letter')
def letter_template():
    branding_style = request.args.get('branding_style')

    if branding_style == FieldWithNoneOption.NONE_OPTION_VALUE:
        branding_style = None

    if branding_style:
        filename = letter_branding_client.get_letter_branding(branding_style)['filename']
    else:
        filename = 'no-branding'

    template = {'subject': '', 'content': ''}
    image_url = url_for('main.letter_branding_preview_image', filename=filename)

    template_image = str(LetterImageTemplate(
        template,
        image_url=image_url,
        page_count=1,
    ))

    resp = make_response(
        render_template('views/service-settings/letter-preview.html', template=template_image)
    )

    resp.headers['X-Frame-Options'] = 'SAMEORIGIN'
    return resp


@main.route('/documentation')
def documentation():
    return render_template('views/documentation.html')


# Only linked from authenticated pages. See #1025
@main.route('/callbacks')
@user_is_logged_in
def callbacks():
    return render_template('views/callbacks.html')


# --- Features page set --- #

@main.route('/features', endpoint='features')
def features():
    return render_template(
        'views/features.html',
        navigation_links=features_nav()
    )


@main.route('/roadmap', endpoint='roadmap')
def roadmap():
    return render_template(
        'views/roadmap.html',
        navigation_links=features_nav()
    )


@main.route('/email', endpoint='email')
def features_email():
    return render_template(
        'views/emails.html',
        navigation_links=features_nav()
    )


@main.route('/sms', endpoint='sms')
def features_sms():
    return render_template(
        'views/text-messages.html',
        navigation_links=features_nav()
    )


@main.route('/letters', endpoint='letters')
def features_letters():
    return render_template(
        'views/letters.html',
        navigation_links=features_nav()
    )


@main.route('/templates', endpoint='templates')
def features_templates():
    return render_template(
        'views/templates.html',
        navigation_links=features_nav()
    )


@main.route('/security', endpoint='security')
def security():
    return render_template(
        'views/security.html'
    )


@main.route('/terms', endpoint='terms')
def terms():
    return render_template(
        'views/terms-of-use.html'
    )


@main.route('/message-status', endpoint='message_status')
def message_status():
    return render_template(
        'views/message-status.html',
        navigation_links=features_nav()
    )


# --- Redirects --- #

@main.route('/features/roadmap', endpoint='redirect_roadmap')
@main.route('/features/email', endpoint='redirect_email')
@main.route('/features/sms', endpoint='redirect_sms')
@main.route('/features/letters', endpoint='redirect_letters')
@main.route('/features/templates', endpoint='redirect_templates')
@main.route('/features/security', endpoint='redirect_security')
@main.route('/features/terms', endpoint='redirect_terms')
@main.route('/features/messages-status', endpoint='redirect_message_status')
def old_page_redirects():
    return redirect(url_for(request.endpoint.replace('redirect_', '')), code=301)
