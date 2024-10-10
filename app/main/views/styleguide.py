from flask import abort, current_app, render_template
from flask_wtf import FlaskForm as Form
from notifications_utils.template import Template
from wtforms import FileField, PasswordField, StringField, TextAreaField, validators

from app.main import main


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


@main.route("/_rte")
def rte():
    from app import get_current_locale

    lang = get_current_locale(current_app)
    template_content = "Annual newsletter\n\nWe hope this newsletter finds you well! As we dive into the new year, we want to ensure you're up to speed with the latest happenings. Here's a quick recap!\n\nThings You May Have Missed:\n\nThing 1\n\nThing 2\n\nSteps to Sign Up:\n\nVisit our website \n\nLook for the Newsletter Sign-Up section on the homepage.\n\nEnter your email address in the provided field.\n\nClick Subscribe to start receiving our regular updates directly in your inbox.\n\nMore Information:\n\nFor more details on our products, services, or any other inquiries, feel free to reach out to our dedicated support team at [support-email] or visit our FAQ page [FAQ-link]. We value your feedback and are here to assist you in any way we can."

    if lang == "fr":
        template_content = "Infolettre annuelle\n\nNous espérons que cette infolettre vous trouvera en bonne santé! Voici un aperçu des derniers événements pour que vous soyez à jour. \n\nCe que vous avez peut-être manqué:\n\nChose 1\n\nChose 2\n\nPour vous inscrire:\n\nVisitez notre site Web\n\nTrouvez le lien d’inscription à l’infolettre sur la page d’accueil\n\nEntrez votre adresse courriel\n\nCliquez sur S’inscrire pour recevoir les mises à jour dans votre boîte de façon régulière\n\nPlus d’information\n\nPour plus d'informations sur nos produits, services ou tout autre question, n’hésitez pas à contacter notre équipe d’assistance au [courriel d’assistance] ou visiter notre FAQ [lien FAQ]. Nous apprécions vos commentaires et sommes toujours à votre disposition pour vous aider."

    template = {
        "id": "fable_test",
        "data": template_content,
    }

    return render_template("views/rte.html", template=template)
