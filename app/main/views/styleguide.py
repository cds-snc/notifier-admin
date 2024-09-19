from flask import abort, current_app, flash, render_template, redirect, request, url_for
from flask_wtf import FlaskForm as Form
from flask_babel import _
from notifications_utils.template import Template
from wtforms import FileField, PasswordField, StringField, TextAreaField, validators

from app import (get_current_locale, template_category_api_client)
from app.main import main
from app.main.forms import EmailTemplateFormWithCategory
from app.models.enum.template_categories import DefaultTemplateCategories



@main.route("/_styleguide")
def styleguide():
    if not current_app.config["SHOW_STYLEGUIDE"]:
        abort(404)

    class FormExamples(Form):
        username = StringField("Username")
        password = PasswordField("Password", [validators.input_required()])
        code = StringField("Enter code")
        message = TextAreaField("Message")
        file_upload = FileField("Upload a CSV file to add your recipients’ details")

    sms = "Your vehicle tax for ((registration number)) is due on ((date)). Renew online at www.gov.uk/vehicle-tax"

    form = FormExamples()
    form.message.data = sms
    form.validate()

    template = Template({"content": sms})

    return render_template("views/styleguide.html", form=form, template=template)


@main.route("/_categories", methods=["GET", "POST"])
def categories():
    if not current_app.config["SHOW_STYLEGUIDE"]:
        abort(404)

    form = EmailTemplateFormWithCategory()
    categories = template_category_api_client.get_all_template_categories()

    other_category = {DefaultTemplateCategories.LOW.value: form.template_category_other}
    
    name_col = "name_en" if get_current_locale(current_app) == "en" else "name_fr"
    desc_col = "description_en" if get_current_locale(current_app) == "en" else "description_fr"
    categories = sorted(categories, key=lambda x: x[name_col])
    form.template_category_id.choices = [(cat["id"], cat[name_col]) for cat in categories if not cat.get("hidden", False)]
    
    form.template_category_id.choices.append((DefaultTemplateCategories.LOW.value, _("Other")))
    template_category_hints = {cat["id"]: cat[desc_col] for cat in categories}
    
    form.name.data = "name"
    form.subject.data = "subject"
    form.template_content.data = "content"

    if form.validate_on_submit():
        flash(_("Category saved"), "default_with_tick")

    return render_template(
        "views/categories.html", 
        form=form, 
        template_category_hints=template_category_hints, 
        other_category=other_category, 
        heading=_("Category"),
        template_category_mode=None,
        )
