import config from "../../../config";
import Page from "../../Notify/Admin/Pages/GoLiveFormPage";

function CompletePage1() {
  // complete page 1
  Page.Components.DeptName().type("Department of Testing");
  Page.Components.MainUseCase().check();
  Page.Components.OtherUseCase().type("Testing purposes");
  Page.Components.IntendedRecipientsInternal().check();
  Page.GoNext();
}

describe("Go Live Form", () => {
  beforeEach(() => {
    // login and go to the form
    cy.login(Cypress.env("NOTIFY_USER"), Cypress.env("NOTIFY_PASSWORD"));
    cy.visit(
      `/services/${config.Services.Cypress}/service-settings/request-to-go-live/use-case`,
    );

    // if we are already on step 2 (it saves your progress), go back to the start
    cy.get("body").then(($body) => {
      if ($body.text().includes("Step 2 of 2")) {
        Page.GoBack();
      }
    });

    // ensure we are at the start of the form
    cy.get("h1").should("contain", "About your service");
  });

  it("Passes a11y", () => {
    // a11y scan page 1
    cy.a11yScan();

    CompletePage1();

    // ensure we are at page 2
    cy.get("h1").should("contain", "About your notifications");

    // a11y scan page 2
    cy.a11yScan();
  });

  it("Forces user to fill required fields fields", () => {
    // clear all fields on page 1
    Page.Components.DeptName().clear();
    Page.Components.MainUseCase().uncheck();
    Page.Components.OtherUseCase().clear();
    Page.Components.IntendedRecipientsInternal().uncheck();

    // Submit and ensure there are three elements with the class 'error-message'
    Page.GoNext();
    cy.get(".error-message").should("have.length", 3);

    CompletePage1();

    Page.GoNext();

    // ensure we are at page 2
    cy.get("h1").should("contain", "About your notifications");

    // clear all fields
    Page.SetEmailDailyVolume("");
    Page.SetEmailYearlyVolume("");
    Page.SetSMSDailyVolume("");
    Page.SetSMSYearlyVolume("");

    // Submit and ensure there are four elements with the class 'error-message'
    Page.GoNext();
    cy.get(".error-message").should("have.length", 4);

    // Fill out the "other" fields and ensure validation on the specify boxes
    Page.SetEmailDailyVolume("more_email");
    Page.SetEmailYearlyVolume("above_limit");
    Page.SetSMSDailyVolume("more_sms");
    Page.SetSMSYearlyVolume("above_limit");
    Page.Components.MoreEmailsDaily().clear();
    Page.Components.MoreSMSDaily().clear();

    // Submit and ensure there are 2 elements with the class 'error-message'
    Page.GoNext();
    cy.get(".error-message").should("have.length", 2);

    // Finish off the form
    Page.Components.MoreEmailsDaily().type("1000000");
    Page.Components.MoreSMSDaily().type("1000000");
    Page.GoNext();

    // ensure we get out of the form
    cy.get("h1").should("contain", "Request to go live");
  });
});
