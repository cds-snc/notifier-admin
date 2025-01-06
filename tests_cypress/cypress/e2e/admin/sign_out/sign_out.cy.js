const REDIRECT_LOCATION = "/sign-in?timeout=true";
const SESSION_TIMEOUT_MS = 7 * 60 * 60 * 1000 + 55 * 60 * 1000; // 7 hours 55 minutes
const vistPageAndFastForwardTime = (page = "/") => {
  cy.clock();
  cy.visit(page);
  cy.tick(SESSION_TIMEOUT_MS);
};

describe("Sign out", () => {
  it("Does not redirect to session timeout page when logged out", () => {
    vistPageAndFastForwardTime();

    // asserts
    cy.url().should("not.include", REDIRECT_LOCATION);
  });

  it("Redirects to session timeout page when logged in (multiple pages)", () => {
    ["/home", "/features"].forEach((page) => {
      cy.login();
      vistPageAndFastForwardTime(page);

      // asserts
      cy.url().should("include", REDIRECT_LOCATION);
      cy.get("h1").should("contain", "You need to sign in again");
    });
  });

  it("Displays banner on explicit logout", () => {
    cy.visit("/sign-out");

    // asserts
    cy.url().should("include", "/sign-in");
    cy.get(".banner-default-with-tick").should("be.visible");
  });

  it("Displays session timeout info on login page", () => {
    cy.visit("/sign-in");

    // asserts
    cy.getByTestId("session_timeout_info").should("be.visible");
  });
});
