// Parts of the page a user can interact with
let Components = {
    Prompt: () => cy.getByTestId('tou-prompt'),
    ErrorMessage: () => cy.getByTestId('tou-error-message'),
    DismissButton: () => cy.getByTestId('tou-agree-button'),
    Heading: () => cy.getByTestId('tou-heading'),
    Terms: () => cy.getByTestId('tou-terms'),
};

// Actions users can take on the page
let Actions = {
    AgreeToTerms: () => {
        TouPrompt.Components.Terms().scrollTo('bottom', { ensureScrollable: false });
        Components.DismissButton().click();
        // depending on how many services a user has, the app either goes to the /accounts page 
        // or to a specific service page - either means success
        cy.url().should('match', /\/(accounts|services)/); 
        cy.get('h1').should('not.contain', 'Before you continue');

    },
};

let TouPrompt = {
    Components,
    ...Actions
};

export default TouPrompt;
