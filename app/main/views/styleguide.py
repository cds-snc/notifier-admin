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
    template = {
        "id": "fable_test",
        "data": """# 🚀 Get started with our platform

Are you ready to revolutionize government processes? Introducing your all-in-one platform for streamlined government services. We understand the unique challenges faced by public institutions, and our platform is here to empower your agency with innovative solutions.

***

## 🌐 What our platform Offers

- **Centralized Citizen Services**: Simplify citizen engagement with a centralized platform for information, applications, and feedback.
- **Effortless Collaboration**: Foster seamless communication and collaboration among government departments to enhance overall efficiency.
- **Data Security**: Rest easy knowing that your sensitive data is protected by state-of-the-art security features.

***

## 📚 Learn more

To get started working with your team:

- Register an account
- Create your team
- Invite your teammates

Visit [our website](https://www.example.com) to learn more
""",
    }

    return render_template("views/rte.html", template=template)
