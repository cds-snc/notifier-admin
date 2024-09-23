let Components = {
    ApiKeysLink: () => cy.getByTestId('api-keys'),
    SafelistLink: () => cy.getByTestId('api-keys'),
    CallbacksLink: () => cy.getByTestId('callbacks'),
    RefreshLogLink: () => cy.getByTestId('refresh-log'),
};

let Actions = {
    ApiKeys: () => {
        Components.ApiKeysLink().click();
    },
    Safelist: () => {
        Components.SafelistLink().click();
    },
    Callbacks: () => {
        Components.CallbacksLink().click();
    },
    RefreshLog: () => {
        Components.RefreshLogLink().click();
    },
};

let ApiIntegrationPage = {
    Components,
    ...Actions
}

export default ApiIntegrationPage;