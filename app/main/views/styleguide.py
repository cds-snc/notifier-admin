from flask import abort, current_app, render_template, request
from flask_wtf import FlaskForm as Form
import json
from notifications_utils.template import Template
from wtforms import FileField, PasswordField, StringField, TextAreaField, validators

from app.main import main
from app.main.forms import (
    CreateServiceStepCombinedOrganisationForm,
)

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

@main.route("/_fable_upload",  methods=["GET", "POST"])
def fable_test_1():
    class FormExamples(Form):
        file_upload = FileField("Upload file")
    form = FormExamples()
    
    uploaded = True if request.method == "POST" else False
    return render_template("views/fable_upload.html", form=form, uploaded=uploaded)

@main.route("/_fable_dropdown_pill",  methods=["GET", "POST"])
def fable_test_2():
    org_data = '[{"id": "001I9000004zOqhIAE", "name_eng": "Accessibility Standards Canada", "name_fra": "Normes daccessibilité Canada", "type": "GC Department", "notify_organisation_id": "9e901bb2-5345-4db5-8ad6-9026d5f6c4f0"}, {"id": "001I9000005DbtMIAS", "name_eng": "Administrative Tribunals Support Service of Canada", "name_fra": "Service canadien d’appui aux tribunaux administratifs", "type": "GC Department", "notify_organisation_id": null}, {"id": "001I9000004pwojIAA", "name_eng": "Agriculture and Agri Food Canada", "name_fra": "Agriculture et Agroalimentaire Canada", "type": "GC Department", "notify_organisation_id": "687fc7d7-59b4-4111-a04a-40a061906ecb"}, {"id": "001I9000004Vt5WIAS", "name_eng": "Atlantic Canada Opportunities Agency", "name_fra": "Agence de promotion économique du Canada atlantique", "type": "GC Department", "notify_organisation_id": null}, {"id": "001I900000505PuIAI", "name_eng": "Atomic Energy of Canada Ltd", "name_fra": "Énergie atomique du Canada limitée", "type": "Crown Corp", "notify_organisation_id": null}, {"id": "001I900000505QTIAY", "name_eng": "Business Development Bank of Canada", "name_fra": "Banque de développement du Canada", "type": "Crown Corp", "notify_organisation_id": null}, {"id": "001I9000004Vt5XIAS", "name_eng": "Canada Border Services Agency", "name_fra": "Agence des services frontaliers du Canada", "type": "GC Department", "notify_organisation_id": "42f9d2f7-3b79-4ee7-8b3e-26d9246f7252"}, {"id": "001I9000004Vt5YIAS", "name_eng": "Canada Economic Development for Quebec Regions", "name_fra": "Développement économique Canada pour les régions du Québec", "type": "GC Department", "notify_organisation_id": "00d617c6-c717-4c5a-a760-956204e7bfa2"}, {"id": "001I90000050b1vIAA", "name_eng": "Canada Employment Insurance Commission", "name_fra": "Commission de l’assurance-emploi du Canada", "type": "GC Department", "notify_organisation_id": null}, {"id": "001I9000005tFjAIAU", "name_eng": "Canada Energy Regulator", "name_fra": "Régie de lénergie du Canada", "type": "GC Department", "notify_organisation_id": null}, {"id": "001I9000005063XIAQ", "name_eng": "Canada Mortgage and Housing Corporation", "name_fra": "Société canadienne dhypothèques et de logement", "type": "Crown Corp", "notify_organisation_id": null}, {"id": "001I900000505hvIAA", "name_eng": "Canada Post", "name_fra": "Postes Canada", "type": "Crown Corp", "notify_organisation_id": null}, {"id": "001I9000004Vt5ZIAS", "name_eng": "Canada Revenue Agency", "name_fra": "Agence du revenu du Canada", "type": "GC Department", "notify_organisation_id": "130baa74-2f4a-4f8e-9fd7-6b94daf1b8f1"}, {"id": "001I9000004Vt5aIAC", "name_eng": "Canada School of Public Service", "name_fra": "École de la fonction publique du Canada", "type": "GC Department", "notify_organisation_id": "ff731c50-3691-4fae-8a4d-8f72be4181cd"}, {"id": "001I9000005064uIAA", "name_eng": "Canada Science and Technology Museum", "name_fra": "Musée des sciences et de la technologie du Canada", "type": "Crown Corp", "notify_organisation_id": null}, {"id": "001I90000050b2KIAQ", "name_eng": "Canadian Air Transport Security Authority", "name_fra": "L’Administration canadienne de la sûreté du transport aérien", "type": "Crown Corp", "notify_organisation_id": null}, {"id": "001I900000503ncIAA", "name_eng": "Canadian Centre for Occupational Health and Safety", "name_fra": "Centre canadien dhygiène et de sécurité au travail", "type": "GC Department", "notify_organisation_id": null}, {"id": "001I9000005064zIAA", "name_eng": "Canadian Dairy Commission", "name_fra": "Commission canadienne du lait", "type": "Crown Corp", "notify_organisation_id": null}, {"id": "001I9000004Vt5bIAC", "name_eng": "Canadian Food Inspection Agency", "name_fra": "Agence canadienne dinspection des aliments", "type": "GC Department", "notify_organisation_id": "37a89a3a-f516-496a-95e4-edfdcfc13732"}, {"id": "001I9000004Vt5cIAC", "name_eng": "Canadian Grain Commission", "name_fra": "Commission canadienne des grains", "type": "GC Department", "notify_organisation_id": "74e2b999-650e-453c-88b1-8f57d22c84a8"}, {"id": "001I9000004Vt5dIAC", "name_eng": "Canadian Heritage", "name_fra": "Patrimoine canadien", "type": "GC Department", "notify_organisation_id": "ed374cb8-4c01-41d1-9abf-315806824224"}, {"id": "001I9000004Vt5eIAC", "name_eng": "Canadian Human Rights Commission", "name_fra": "Commission canadienne des droits de la personne", "type": "GC Department", "notify_organisation_id": null}, {"id": "001I900000503mHIAQ", "name_eng": "Canadian Institutes of Health Research", "name_fra": "Instituts de recherche en santé du Canada", "type": "GC Department", "notify_organisation_id": null}, {"id": "001I90000050aK9IAI", "name_eng": "Canadian Intellectual Property Office", "name_fra": "Office de la propriété intellectuelle du Canada", "type": "GC Department", "notify_organisation_id": "86b7810d-78af-47e3-ab01-d655c43bd449"}, {"id": "001I9000005SgSOIA0", "name_eng": "Canadian International Trade Tribunal", "name_fra": "Tribunal canadien du commerce extérieur", "type": "GC Department", "notify_organisation_id": null}, {"id": "001I900000504boIAA", "name_eng": "Canadian Museum for Human Rights", "name_fra": "Musée canadien pour les droits de la personne", "type": "Crown Corp", "notify_organisation_id": null}, {"id": "001I90000050662IAA", "name_eng": "Canadian Museum of History", "name_fra": "Musée canadien de lhistoire", "type": "Crown Corp", "notify_organisation_id": null}, {"id": "001I9000005066MIAQ", "name_eng": "Canadian Museum of Immigration at Pier 21", "name_fra": "Musée canadien de l’immigration du Quai 21", "type": "Crown Corp", "notify_organisation_id": null}, {"id": "001I900000505NBIAY", "name_eng": "Canadian Museum of Nature", "name_fra": "Musée canadien de la nature", "type": "Crown Corp", "notify_organisation_id": null}, {"id": "001I9000004Vt5fIAC", "name_eng": "Canadian Northern Economic Development Agency", "name_fra": "Agence canadienne de développement économique du Nord", "type": "GC Department", "notify_organisation_id": null}, {"id": "001I9000004Vt5gIAC", "name_eng": "Canadian Nuclear Safety Commission", "name_fra": "Commission canadienne de sûreté nucléaire", "type": "GC Department", "notify_organisation_id": "2e5ee51e-993b-418c-ba36-cf487ecd1e27"}, {"id": "001I9000004Vt5hIAC", "name_eng": "Canadian Radio-television and Telecommunications Commission", "name_fra": "Conseil de la radiodiffusion et des télécommunications canadiennes", "type": "GC Department", "notify_organisation_id": null}, {"id": "001I90000050a3fIAA", "name_eng": "Canadian Security Intelligence Service", "name_fra": "Service canadien du renseignement de sécurité", "type": "GC Department", "notify_organisation_id": null}, {"id": "001I9000004Vt5iIAC", "name_eng": "Canadian Space Agency", "name_fra": "Agence spatiale canadienne", "type": "GC Department", "notify_organisation_id": null}, {"id": "001I900000503r9IAA", "name_eng": "Canadian Transportation Agency", "name_fra": "Office des transports du Canada", "type": "GC Department", "notify_organisation_id": "c5f5aee8-b508-47ad-9e77-7227f0a254a7"}, {"id": "001I9000004zLveIAE", "name_eng": "Communications Security Establishment Canada", "name_fra": "Centre de la sécurité des télécommunications Canada", "type": "GC Department", "notify_organisation_id": "1572a41d-0373-43a8-a0fe-32e7f6c44e04"}, {"id": "001I900000503tPIAQ", "name_eng": "Copyright Board Canada", "name_fra": "Commission du droit dauteur du Canada", "type": "GC Department", "notify_organisation_id": null}, {"id": "001I900000503m9IAA", "name_eng": "Correctional Service Canada", "name_fra": "Service correctionnel Canada", "type": "GC Department", "notify_organisation_id": "f8ff9966-68e3-436b-aaf1-a6b3ca924607"}, {"id": "001I9000004Vt5kIAC", "name_eng": "Courts Administration Service", "name_fra": "Service administratif des tribunaux judiciaires", "type": "GC Department", "notify_organisation_id": null}, {"id": "001I9000004Vt5xIAC", "name_eng": "Crown-Indigenous Relations and Northern Affairs Canada", "name_fra": "Relations Couronne-Autochtones et Affaires du Nord Canada", "type": "GC Department", "notify_organisation_id": "78e40414-165e-4d7c-804b-6163cdfcefaa"}, {"id": "001I9000005Ho3zIAC", "name_eng": "Department not listed", "name_fra": "Ministère n’est pas répertorié", "type": "GC Department", "notify_organisation_id": null}, {"id": "001I9000004Vt5lIAC", "name_eng": "Department of Finance Canada", "name_fra": "Ministère des Finances Canada", "type": "GC Department", "notify_organisation_id": null}, {"id": "001I9000004Vt5mIAC", "name_eng": "Department of Justice Canada", "name_fra": "Ministère de la Justice Canada", "type": "GC Department", "notify_organisation_id": "722a631f-bcfd-484c-9243-8c3e715f6334"}, {"id": "001I9000004Vt5nIAC", "name_eng": "Elections Canada", "name_fra": "Élections Canada", "type": "GC Department", "notify_organisation_id": "ba7a98ee-f508-4263-978c-7c228cf48e4d"}, {"id": "001I9000004Vt5oIAC", "name_eng": "Employment and Social Development Canada", "name_fra": "Emploi et Développement social Canada", "type": "GC Department", "notify_organisation_id": "5370de8a-a876-4ef0-ab3a-9436891f36b5"}, {"id": "001I9000004Vt5pIAC", "name_eng": "Environment and Climate Change Canada", "name_fra": "Environnement et Changement climatique Canada", "type": "GC Department", "notify_organisation_id": "f4602a8b-1cde-425c-9bd8-16cbc8ac6aae"}, {"id": "001I900000503nDIAQ", "name_eng": "Export Development Canada", "name_fra": "Exportation et développement Canada", "type": "Crown Corp", "notify_organisation_id": null}, {"id": "001I900000505P7IAI", "name_eng": "Farm Credit Canada", "name_fra": "Financement agricole Canada", "type": "Crown Corp", "notify_organisation_id": null}, {"id": "001I90000050b0nIAA", "name_eng": "Federal Economic Development Agency for Southern Ontario", "name_fra": "Agence fédérale de développement économique pour le Sud de lOntario", "type": "GC Department", "notify_organisation_id": null}, {"id": "001I900000503tyIAA", "name_eng": "Financial Consumer Agency of Canada", "name_fra": "Agence de la consommation en matière financière du Canada", "type": "GC Department", "notify_organisation_id": null}, {"id": "001I9000004Vt5rIAC", "name_eng": "Financial Transactions and Reports Analysis Centre of Canada", "name_fra": "Centre danalyse des opérations et déclarations financières du Canada", "type": "GC Department", "notify_organisation_id": "04fd35a1-7e6d-4ba9-8d27-ab0c87446ec4"}, {"id": "001I9000004Vt5sIAC", "name_eng": "Fisheries and Oceans Canada", "name_fra": "Pêches et Océans Canada", "type": "GC Department", "notify_organisation_id": "4983c8da-fe3d-488a-a974-0c5c442f33a5"}, {"id": "001I9000004Vt5tIAC", "name_eng": "Global Affairs Canada", "name_fra": "Affaires mondiales Canada", "type": "GC Department", "notify_organisation_id": "155a85be-1d5f-4189-abad-09f4f3744112"}, {"id": "001I9000004VrQNIA0", "name_eng": "Government of Alberta", "name_fra": "Gouvernement de lalberta", "type": "PTM", "notify_organisation_id": "fbcd0568-0481-48c6-8884-9bd8f40ecadf"}, {"id": "001I9000004cImXIAU", "name_eng": "Government of British Columbia (BC)", "name_fra": "Gouvernement de la Colombie-Britannique", "type": "PTM", "notify_organisation_id": "e12c6a14-c458-4203-910b-b8cc47a95b09"}, {"id": "001I90000050e4sIAA", "name_eng": "Government of Manitoba", "name_fra": "Gouvernement du Manitoba", "type": "PTM", "notify_organisation_id": null}, {"id": "001I90000050e4dIAA", "name_eng": "Government of New Brunswick", "name_fra": "Gouvernement du Nouveau-Brunswick", "type": "PTM", "notify_organisation_id": "5ef913fb-7abb-488a-8c2e-001a2228824f"}, {"id": "001I90000050dxBIAQ", "name_eng": "Government of Newfoundland and Labrador", "name_fra": "Gouvernement de Terre-Neuve-et-Labrador", "type": "PTM", "notify_organisation_id": null}, {"id": "001I90000050e4xIAA", "name_eng": "Government of Northwest Territories", "name_fra": "Gouvernement des Territoires du Nord-Ouest", "type": "PTM", "notify_organisation_id": null}, {"id": "001I9000004VzBNIA0", "name_eng": "Government of Nova Scotia", "name_fra": "Gouvernement de la Nouvelle-Écosse", "type": "PTM", "notify_organisation_id": "a4297403-29a5-400e-8be2-3689ed557937"}, {"id": "001I90000050e2EIAQ", "name_eng": "Government of Nunavut", "name_fra": "Gouvernement du Nunavut", "type": "PTM", "notify_organisation_id": null}, {"id": "001I90000050e3NIAQ", "name_eng": "Government of Ontario", "name_fra": "Gouvernement de l’Ontario", "type": "PTM", "notify_organisation_id": "c4be8612-85c3-454b-ace1-309352220cf5"}, {"id": "001I9000004yum3IAA", "name_eng": "Government of Prince Edward Island", "name_fra": "Gouvernement de lÎle-du-Prince-Édouard", "type": "PTM", "notify_organisation_id": null}, {"id": "001I9000004yvYcIAI", "name_eng": "Government of Quebec", "name_fra": "Gouvernement du Québec", "type": "PTM", "notify_organisation_id": null}, {"id": "001I90000050e5WIAQ", "name_eng": "Government of Saskatchewan", "name_fra": "Gouvernement de la Saskatchewan", "type": "PTM", "notify_organisation_id": null}, {"id": "001I90000050e2iIAA", "name_eng": "Government of Yukon", "name_fra": "Gouvernement du Yukon", "type": "PTM", "notify_organisation_id": null}, {"id": "001I9000004Vt5uIAC", "name_eng": "Health Canada", "name_fra": "Santé Canada", "type": "GC Department", "notify_organisation_id": "311528bc-ff51-44f4-a268-2eaae8b99efd"}, {"id": "001I9000004Vt5vIAC", "name_eng": "Immigration and Refugee Board of Canada", "name_fra": "Commission de limmigration et du statut de réfugié du Canada", "type": "GC Department", "notify_organisation_id": null}, {"id": "001I9000004Vt5wIAC", "name_eng": "Immigration, Refugees and Citizenship Canada", "name_fra": "Immigration, Réfugiés et Citoyenneté Canada", "type": "GC Department", "notify_organisation_id": "91dad410-47f4-4ca8-b852-951899200926"}, {"id": "001I9000005DbFCIA0", "name_eng": "Impact Assessment Agency of Canada", "name_fra": "Agence d’évaluation d’impact du Canada", "type": "GC Department", "notify_organisation_id": null}, {"id": "001I900000504eXIAQ", "name_eng": "Indigenous Services Canada", "name_fra": "Services aux Autochtones Canada", "type": "GC Department", "notify_organisation_id": "4cb53e9f-a612-4280-9e44-6015cd49c6c2"}, {"id": "001I9000005HqRoIAK", "name_eng": "Indigenous Services Canada & Crown-Indigenous Relations and Northern Affairs Canada", "name_fra": "Affaires autochtones et du Nord Canada", "type": "GC Department", "notify_organisation_id": null}, {"id": "001I9000004Vt5yIAC", "name_eng": "Infrastructure Canada", "name_fra": "Infrastructure Canada", "type": "GC Department", "notify_organisation_id": "5f48482e-c4d0-41a1-9337-0f64d157573a"}, {"id": "001I9000004Vt5zIAC", "name_eng": "Innovation, Science and Economic Development Canada", "name_fra": "Innovation, Sciences et Développement économique Canada", "type": "GC Department", "notify_organisation_id": "33503c98-2fa9-4ee8-91b0-12b68a26dcc1"}, {"id": "001I9000004Vt60IAC", "name_eng": "Library and Archives Canada", "name_fra": "Bibliothèque et Archives Canada", "type": "GC Department", "notify_organisation_id": "220f022c-ce53-4c2f-b941-401e78ce8bcf"}, {"id": "001I9000005PIWlIAO", "name_eng": "Military Grievances External Review Committee", "name_fra": "Comité externe d’examen des griefs militaires", "type": "GC Department", "notify_organisation_id": "00aaac61-cafd-4edd-9bcc-bea78342d92d"}, {"id": "001I9000004Vt61IAC", "name_eng": "National Defence", "name_fra": "Défense nationale et les Forces armées canadiennes", "type": "GC Department", "notify_organisation_id": "ae2e30e5-59fa-4e30-9af6-87d0cff6a909"}, {"id": "001I900000503gTIAQ", "name_eng": "National Film Board", "name_fra": "Loffice National Du Film Du Canada", "type": "GC Department", "notify_organisation_id": null}, {"id": "001I9000004Vt62IAC", "name_eng": "National Research Council Canada", "name_fra": "Conseil national de recherches Canada", "type": "GC Department", "notify_organisation_id": null}, {"id": "001I9000004Vt63IAC", "name_eng": "Natural Resources Canada", "name_fra": "Ressources naturelles Canada", "type": "GC Department", "notify_organisation_id": "e51e94b9-1146-4636-b4ca-cc39bd18615a"}, {"id": "001I9000004Vt64IAC", "name_eng": "Natural Sciences and Engineering Research Council of Canada", "name_fra": "Conseil de recherches en sciences naturelles et en génie du Canada", "type": "GC Department", "notify_organisation_id": "5a4093a5-ada9-4943-8263-972418eb4945"}, {"id": "001I900000503zhIAA", "name_eng": "Office of the Auditor General", "name_fra": "Le Bureau du vérificateur général du Canada", "type": "GC Department", "notify_organisation_id": null}, {"id": "001I900000503tVIAQ", "name_eng": "Office of the Chief Electoral Officer", "name_fra": "Bureau du directeur général des élections", "type": "GC Department", "notify_organisation_id": null}, {"id": "001I9000004Vt65IAC", "name_eng": "Office of the Commissioner of Lobbying of Canada", "name_fra": "Commissariat au lobbying du Canada", "type": "GC Department", "notify_organisation_id": null}, {"id": "001I9000004Vt66IAC", "name_eng": "Office of the Commissioner of Official Languages", "name_fra": "Commissariat aux langues officielles", "type": "GC Department", "notify_organisation_id": null}, {"id": "001I9000005DXSKIA4", "name_eng": "Office of the Superintendent of Financial Institutions", "name_fra": "Bureau du surintendant des institutions financières", "type": "GC Department", "notify_organisation_id": null}, {"id": "001I900000504b0IAA", "name_eng": "Offices of the Information and Privacy Commissioners of Canada", "name_fra": "Les Commissariats à l’information et à la protection de la vie privée du Canada", "type": "GC Department", "notify_organisation_id": null}, {"id": "001I90000050ZenIAE", "name_eng": "Pacific Economic Development Canada", "name_fra": "Développement économique Canada pour le Pacifique", "type": "GC Department", "notify_organisation_id": null}, {"id": "001I90000050XWsIAM", "name_eng": "Pacific Pilotage Authority Canada", "name_fra": "Administration de pilotage du Pacifique Canada", "type": "Crown Corp", "notify_organisation_id": null}, {"id": "001I9000004Vt67IAC", "name_eng": "Parks Canada", "name_fra": "Parcs Canada", "type": "GC Department", "notify_organisation_id": null}, {"id": "001I9000005DbCwIAK", "name_eng": "Parliament of Canada", "name_fra": "Parlement du Canada", "type": "GC Department", "notify_organisation_id": null}, {"id": "001I900000504ZTIAY", "name_eng": "Parole Board of Canada", "name_fra": "Commission des libérations conditionnelles du Canada", "type": "GC Department", "notify_organisation_id": null}, {"id": "001I9000005X2mZIAS", "name_eng": "Polar Knowledge Canada", "name_fra": "Savoir polaire Canada", "type": "GC Department", "notify_organisation_id": null}, {"id": "001I9000004Vt68IAC", "name_eng": "Prairies Economic Development Canada", "name_fra": "Développement économique Canada pour les Prairies", "type": "GC Department", "notify_organisation_id": null}, {"id": "001I9000004Vt69IAC", "name_eng": "Privy Council Office", "name_fra": "Bureau du Conseil privé", "type": "GC Department", "notify_organisation_id": null}, {"id": "001I9000004Vt6AIAS", "name_eng": "Public Health Agency of Canada", "name_fra": "Agence de la santé publique du Canada", "type": "GC Department", "notify_organisation_id": "6d5f3682-54ff-4aba-8405-96e71de45bb1"}, {"id": "001I9000004Vt6BIAS", "name_eng": "Public Prosecution Service of Canada", "name_fra": "Service des poursuites pénales du Canada", "type": "GC Department", "notify_organisation_id": null}, {"id": "001I9000004Vt6CIAS", "name_eng": "Public Safety Canada", "name_fra": "Sécurité publique Canada", "type": "GC Department", "notify_organisation_id": "bf791b97-e34c-4bc9-b571-63cc00a17fca"}, {"id": "001I9000004Vt6DIAS", "name_eng": "Public Service Commission of Canada", "name_fra": "Commission de la fonction publique du Canada", "type": "GC Department", "notify_organisation_id": "3357a618-cf88-4ec7-8058-e2ddacf49e07"}, {"id": "001I9000004Vt6EIAS", "name_eng": "Public Services and Procurement Canada", "name_fra": "Services publics et Approvisionnement Canada", "type": "GC Department", "notify_organisation_id": "d8509d9d-44a8-40bc-91d3-60417a636a38"}, {"id": "001I9000004Vt6FIAS", "name_eng": "Royal Canadian Mint", "name_fra": "Monnaie royale canadienne", "type": "GC Department", "notify_organisation_id": null}, {"id": "001I9000004Vt6GIAS", "name_eng": "Royal Canadian Mounted Police", "name_fra": "Gendarmerie royale du Canada", "type": "GC Department", "notify_organisation_id": "6022df15-563b-4ceb-b1e2-33ad17136286"}, {"id": "001I90000050aMNIAY", "name_eng": "Service Canada", "name_fra": "Service Canada", "type": "GC Department", "notify_organisation_id": "23462a82-9c9c-402c-b99b-27179e9d35d8"}, {"id": "001I9000004Vt6HIAS", "name_eng": "Shared Services Canada", "name_fra": "Services partagés Canada", "type": "GC Department", "notify_organisation_id": "b2ba3091-4e76-4190-9ac5-e3b2cfa6e0e4"}, {"id": "001I900000503tgIAA", "name_eng": "Social Sciences and Humanities Research Council", "name_fra": "Conseil de recherches en sciences humaines", "type": "GC Department", "notify_organisation_id": null}, {"id": "001I90000057LCEIA2", "name_eng": "Social Security Tribunal of Canada", "name_fra": "Tribunal de la sécurité sociale du Canada", "type": "GC Department", "notify_organisation_id": null}, {"id": "001I90000050b2ZIAQ", "name_eng": "Standards Council of Canada", "name_fra": "Conseil canadien des normes", "type": "Crown Corp", "notify_organisation_id": null}, {"id": "001I9000004Vt6IIAS", "name_eng": "Statistics Canada", "name_fra": "Statistique Canada", "type": "GC Department", "notify_organisation_id": "27a987ff-b754-4efc-8dfe-b79d62b622f5"}, {"id": "001I9000005X2DjIAK", "name_eng": "The National Battlefields Commission", "name_fra": "Commission des champs de bataille nationaux", "type": "GC Department", "notify_organisation_id": null}, {"id": "001I90000050aLkIAI", "name_eng": "The Office of the Procurement Ombudsman", "name_fra": "Le Bureau de lombudsman de lapprovisionnement", "type": "GC Department", "notify_organisation_id": "4029fa62-0a9f-4d7e-8c29-a8698d14ed92"}, {"id": "001I9000004Vt6JIAS", "name_eng": "Transport Canada", "name_fra": "Transports Canada", "type": "GC Department", "notify_organisation_id": "3371f506-4f80-42df-a741-1a3c93d186fb"}, {"id": "001I90000050YtsIAE", "name_eng": "Transportation Safety Board of Canada", "name_fra": "Bureau de la sécurité des transports du Canada", "type": "GC Department", "notify_organisation_id": null}, {"id": "001I9000004Vt6KIAS", "name_eng": "Treasury Board of Canada Secretariat", "name_fra": "Secrétariat du Conseil du Trésor du Canada", "type": "GC Department", "notify_organisation_id": "25237e37-3457-4d0c-9d8e-82f3b8e6bc0a"}, {"id": "001I9000004Vt6LIAS", "name_eng": "Veterans Affairs Canada", "name_fra": "Anciens combattants Canada", "type": "GC Department", "notify_organisation_id": "dcd62816-abee-4867-88d4-bee61253785b"}, {"id": "001I900000505KfIAI", "name_eng": "Veterans Review and Appeal Board", "name_fra": "Tribunal des anciens combattants révision et appel", "type": "GC Department", "notify_organisation_id": null}, {"id": "001I90000050aLyIAI", "name_eng": "VIA Rail Canada", "name_fra": "VIA Rail Canada", "type": "Crown Corp", "notify_organisation_id": null}, {"id": "001I9000004zOAzIAM", "name_eng": "Women and Gender Equality Canada", "name_fra": "Femmes et Égalité des genres Canada", "type": "GC Department", "notify_organisation_id": "efae94cf-1763-43a7-8ac3-f82cfa662f78"}]'
    
    counts = [('total', '', '#', 1337), ('in transit', 'sending', '#', 346), ('delivered', 'delivered', '#', 312), ('failed', 'failed', '#', 78)]
    CreateServiceStepCombinedOrganisationForm.parent_organisation_name.name ="my-name"
    
    english_org_data =  [item["name_eng"] for item in json.loads(org_data)]
    
    
    return render_template("views/fable_dropdown_pill.html", formy=CreateServiceStepCombinedOrganisationForm, counts=counts, org_data=english_org_data)