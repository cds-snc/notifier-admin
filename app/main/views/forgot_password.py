from flask import abort, flash, render_template, session
from flask_babel import _
from notifications_python_client.errors import HTTPError

from app import user_api_client
from app.main import main
from app.main.forms import ForgotPasswordForm
from app.models.user import User


@main.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        try:
            user_api_client.send_reset_password_url(form.email_address.data)
        except HTTPError as e:
            if e.status_code == 400 and "user blocked" in str(e.response.content):
                flash(
                    _(
                        "You cannot reset your password as your account has been blocked. "
                        + "Please email us at assistance+notification@cds-snc.ca"
                    )
                )
                abort(400)
            elif e.status_code == 404:
                return render_template("views/password-reset-sent.html")
            else:
                raise e
        return render_template("views/password-reset-sent.html")

    return render_template("views/forgot-password.html", form=form)


@main.route("/forced-password-reset", methods=["GET"])
def forced_password_reset():
    email_address = session.pop("reset_email_address", None)
    if email_address and User.from_email_address_or_none(email_address):
        user_api_client.send_reset_password_url(email_address)
    return render_template("views/forced-password-reset.html")
