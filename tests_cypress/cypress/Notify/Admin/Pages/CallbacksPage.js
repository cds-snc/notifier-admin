let Components = {
    ChangeDeliveryReceiptsLink: () => cy.getByTestId('change-delivery-receipts'),
    ChangeReceivedTextMessagesLink: () => cy.getByTestId('change-received-text-messages'),
    UrlField: () => cy.getByTestId('url'),
    BearerTokenField: () => cy.getByTestId('bearer-token'),
    SaveButton: () => cy.getByTestId('save'),
    TestResponseTimeButton: () => cy.getByTestId('test-response-time'),
    DeleteButton: () => cy.getByTestId('delete'),
    ConfirmDeleteButton: () => cy.get('button[name="delete"]')
};

let Actions = {
    FillForm: (url, bearerToken) => {
        Components.UrlField().clear().type(url);
        Components.BearerTokenField().clear().type(bearerToken);
    },
    SaveForm: () => {
        Components.SaveButton().click();
    },
    TestResponseTime: () => {
        Components.TestResponseTimeButton().click();
    },
    Delete: () => {
        Components.DeleteButton().click();
    },
    ConfirmDelete: () => {
        Components.ConfirmDeleteButton().click();
    }
};

let CallbacksPage = {
    Components,
    ...Actions
}

export default CallbacksPage;