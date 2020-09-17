from flask import redirect, render_template, request, url_for

from app import user_api_client
from app.main import main
from app.main.forms import ContactNotifyTeam


@main.route('/contact', methods=['GET', 'POST'])
def contact():
    form = ContactNotifyTeam()

    # catch with the honeypot field
    if(form.phone.data):
        return redirect(url_for('.thanks', auto="true"))

    if form.validate_on_submit():
        # send email here
        user_api_client.send_contact_email(form.name.data, form.email_address.data, form.feedback.data, form.support_type.data)

        return redirect(url_for('.thanks'))

    if request.method == 'POST':
        return render_template('views/contact/thanks.html', form=form)

    return render_template('views/contact/form.html', form=form)


@main.route('/support/ask-question-give-feedback', endpoint='redirect_contact')
def redirect_contect():
    return redirect(url_for('main.contact'), code=301)
