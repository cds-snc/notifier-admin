import TouPrompt from "../../Notify/Admin/Pages/TouPrompt";

describe("TOU Prompt", () => {
  it("should display the prompt when logged in", () => {
    cy.login(false);
    cy.visit("/");

    TouPrompt.Components.Prompt().should("be.visible");
    // ensure the heading element has the autofocus attribute
    TouPrompt.Components.Heading().should("have.attr", "autofocus");
  });

  it("should not display the prompt after being dismissed", () => {
    cy.login(false);
    cy.visit("/");

    TouPrompt.Components.Prompt().should("be.visible");
    TouPrompt.AgreeToTerms();
    TouPrompt.Components.Prompt().should("not.exist");

    cy.visit("/activity");
    TouPrompt.Components.Prompt().should("not.exist");
  });

  it("should not display the prompt when not logged in", () => {
    cy.visit("/");

    TouPrompt.Components.Prompt().should("not.exist");
  });

  it("should not be displayed on any GCA page when logged in or out", () => {
    cy.visit("/features");
    TouPrompt.Components.Prompt().should("not.exist");

    cy.visit("/security");
    TouPrompt.Components.Prompt().should("not.exist");

    cy.login(false);

    cy.visit("/features");
    TouPrompt.Components.Prompt().should("not.exist");

    cy.visit("/security");
    TouPrompt.Components.Prompt().should("not.exist");
  });

  it("should display the prompt again when navigating to the page before prompt is dismissed", () => {
    cy.login(false);
    cy.visit("/");
    TouPrompt.Components.Prompt().should("be.visible");

    cy.visit("/accounts");
    TouPrompt.Components.Prompt().should("be.visible");
  });
});
