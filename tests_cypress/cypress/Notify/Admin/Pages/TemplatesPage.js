let CONSTANTS = {
    USE_CATEGORY_PRIORITY: "__use_tc",
};

// Parts of the page a user can interact with
let Components = {
    // Template list page
    CreateTemplateButton: () => cy.get('button').contains('Create template'),
    EditCurrentTemplateButton: () => cy.getByTestId('edit-template'),
    // create template 1st page
    TemplateTypeRadio: () => cy.getByTestId('template-type'),
    EmailRadio: () => cy.getByTestId('email'),
    SMSRadio: () => cy.getByTestId('sms'),
    ContinueButton: () => cy.contains('button', 'Continue'),
    // edit template page
    TemplateName: () => cy.getByTestId('template-name'),
    TemplateContent: () => cy.getByTestId('template-content'),
    TemplateSubject: () => cy.get('textarea[name=subject]'),
    FlashMessage: () => cy.get('.banner-default-with-tick'),
    TemplateCategoryButtonContainer: () => cy.getByTestId('tc_button_container'),
    TemplateCategoryRadiosContainer: () => cy.getByTestId('tc_radios'),
    TemplateCategories: () => cy.getByTestId('template-categories'),
    TemplateCategoryOther: () => cy.get('#template_category_other'),
    SaveTemplateButton: () => cy.get('button[type="submit"]').first(),
    PreviewTemplateButton: () => cy.get('button[type="submit"]').eq(1),
    SelectedTemplateCategory: () => Components.TemplateCategories().find('input:checked').parent(),
    SelectedTemplateCategoryCollapsed: () => Components.TemplateCategoryButtonContainer().find('p'),
    TCExpandBytton: () => cy.getByTestId('tc_expand_button'),
    TemplatePriority: () => cy.getByTestId('process_type'),
    DeleteTemplateButton: () => cy.contains('a', 'Delete this template'), 
    TextDirectionCheckbox: () => cy.getByTestId('template-rtl'),
    AddRecipientsButton: () => cy.getByTestId('add-recipients'),
    OneRecipientRadio: () => cy.getByTestId('one-recipient'),
};

// Actions users can take on the page
let Actions = {
    SelectTemplate: (template_name) => {
        cy.contains('a', template_name).first().click();
        cy.contains('h1', template_name).should('be.visible');
    },
    SelectTemplateById: (service_id, template_id) => {
        cy.get(`a[href="/services/${service_id}/templates/${template_id}"]`).click();
    },
    GotoAddRecipients: () => {
        Components.YesAddRecipients().click();
        //cy.contains('h1', 'Add recipients').should('be.visible');
    },
    EditCurrentTemplate: () => {
        Components.EditCurrentTemplateButton().click();
        cy.contains('h1', 'Edit reusable template').should('be.visible');
    },
    ExpandTemplateCategories: () => {
        Components.TCExpandBytton().click();
    },
    SaveTemplate: (expectFailure = false) => {
        Components.SaveTemplateButton().click();
        if (!expectFailure) {
            Components.FlashMessage().should('contain', 'template saved');
        }
    },
    PreviewTemplate: () => {
        Components.PreviewTemplateButton().click();
        cy.contains('h1', 'Previewing template').should('be.visible');
    },
    CreateTemplate: () => {
        Components.CreateTemplateButton().click();
        cy.contains('h1', 'Will you send the message by email or text?').should('be.visible');
    },
    SelectTemplateType: (type) => {
        // to lower case

        if (type.toLowerCase() === 'email') {
            Components.EmailRadio().click();
        }
        else if (type.toLowerCase() === 'sms') {
            Components.SMSRadio().click();
        }
    },
    Continue: () => {
        Components.ContinueButton().click()
        cy.contains('h1', 'Create reusable template').should('be.visible');
    },
    SelectTemplateCategory: (category) => {
        Components.TemplateCategories().contains('label', category).click();
    },
    SetTemplatePriority: (priority) => {
        cy.getByTestId(priority).click();
    },
    FillTemplateForm: (name, subject, content, category = null, priority = null) => {
        Components.TemplateName().type(name);
        if (subject) {
            Components.TemplateSubject().type(subject);
        }
        Components.TemplateContent().type(content);
        if (category) {
            Actions.SelectTemplateCategory(category);
        }
        if (priority) {
            Actions.SetTemplatePriority(priority);
        }
    },
    SeedTemplate: (name, subject, content, category = null, priority = null) => {
        Actions.CreateTemplate();
        Actions.SelectTemplateType("email");
        Actions.Continue();
        Actions.FillTemplateForm(
            name,
            subject,
            content,
            category,
            priority,
        );
        Actions.SaveTemplate();
        return cy.url().then((url) => {
            return url.split("/templates/")[1]
        })
    },
    DeleteTemplate: () => {
        Components.DeleteTemplateButton().click();
        cy.get('.banner-dangerous').contains('Are you sure').should('be.visible');
        cy.get('button[name="delete"]').click();
        cy.url().should('contain', '/templates');
    },
    SetTextDirection: (rtl) => {
        if (rtl) {
            Components.TextDirectionCheckbox().check();
        } else {
            Components.TextDirectionCheckbox().uncheck();
        }
    },
    AddRecipients: (email_address) => {
        Components.AddRecipientsButton().click();
        cy.contains('h1', 'Add recipients').should('be.visible');
        Components.OneRecipientRadio().click();
        Components.OneRecipientRadio().nextAll('input').first().type(email_address);
        Components.ContinueButton().click();
    }
}

let TemplatesPage = {
    CONSTANTS,
    Components,
    ...Actions
};

export default TemplatesPage;
