// Root element for scoping component interactions
const Root = (selector = '') => {
    if (typeof selector === 'number') {
        return cy.getByTestId('notice').eq(selector);
    }
    return cy.get(`[data-testid="notice"].notice-${selector}`);
};


// Parts of the component a user can interact with
let Components = {
    Root,
    Icon: (selector) => Root(selector).find('[data-testid="notice-icon"] svg'),
    IconText: (selector) => Root(selector).find('[data-testid="notice-icon-text"]'),
    Heading: (selector) => Root(selector).find('[data-testid="notice-heading"]'),
    Message: (selector) => Root(selector).find('[data-testid="notice-message"]'),
};

// Actions users can take on the component
let Actions = {
};

let Notice = {
    Components,
    ...Actions
};

export default Notice;
