// Parts of the page a user can interact with
let Components = {
    // page 1
    DeptName: () => cy.get('#department_org_name'),
    Purpose: () => cy.get('#purpose'),
    IntendedRecipientsInternal: () => cy.getByTestId('internal'),
    NextPageButton: () => cy.get('button[type="submit"]'),
    BackLink: () => cy.get("a[class='back-link']"),

    // page 2
    EmailDailyVolume: () => cy.get("input[name='daily_email_volume']"),
    MoreEmailsDaily: () => cy.get("#how_many_more_email"),
    EmailYearlyVolume: () => cy.get("[name='annual_email_volume']"),
    SMSDailyVolume: () => cy.get("[name='daily_sms_volume']"),
    MoreSMSDaily: () => cy.get("#how_many_more_sms"),
    SMSYearlyVolume: () => cy.get("[name='annual_sms_volume']"),
};

// Actions users can take on the page
let Actions = {
    SetEmailDailyVolume: (volume) => {
        if (volume === '') {
            Components.EmailDailyVolume().invoke('prop', 'checked', false);
        } else {
            Components.EmailDailyVolume().check(volume);
        }
    },
    SetEmailYearlyVolume: (volume) => {
        if (volume === '') {
            Components.EmailYearlyVolume().invoke('prop', 'checked', false);
        } else {
            Components.EmailYearlyVolume().check(volume);
        }
    },
    SetSMSDailyVolume: (volume) => {
        if (volume === '') {
            Components.SMSDailyVolume().invoke('prop', 'checked', false);
        } else {
            Components.SMSDailyVolume().check(volume);
        }
    },
    SetSMSYearlyVolume: (volume) => {
        if (volume === '') {
            Components.SMSYearlyVolume().invoke('prop', 'checked', false);
        } else {
            Components.SMSYearlyVolume().check(volume);
        }
    },
    GoNext: () => {
        Components.NextPageButton().click();
    },
    GoBack: () => {
        Components.BackLink().click();
    }
};

let GoLiveForm = {
    Components,
    ...Actions
};

export default GoLiveForm;
