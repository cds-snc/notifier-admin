import config from "../../../../config";
import { TemplatesPage as Page } from "../../../Notify/Admin/Pages/all";

// TODO: dont hardcode these
const templates = {
  smoke_test_email: {
    name: "SMOKE_TEST_EMAIL",
    id: "5e26fae6-3565-44d5-bfed-b18680b6bd39",
  },
  smoke_test_email_attach: {
    name: "SMOKE_TEST_EMAIL_ATTACH",
    id: "bf85def8-01b4-4c72-98a8-86f2bc10f2a4",
  },
};

describe("Template text direction", () => {
  beforeEach(() => {
    cy.login();
    cy.visit(`/services/${config.Services.Cypress}/templates`);
  });

  it("Should align content to the right when clicked", () => {
    Page.SelectTemplate(templates.smoke_test_email.name);
    Page.EditCurrentTemplate();

    // ensure content doesnt have dir attribute
    Page.Components.TemplateContent().should("not.have.attr", "dir");

    Page.SetTextDirection(true);
    Page.Components.TemplateContent().should("have.attr", "dir", "rtl");
  });

  it("Should align to the right when previewed", () => {
    Page.SelectTemplate(templates.smoke_test_email.name);
    Page.EditCurrentTemplate();
    Page.SetTextDirection(true);
    Page.PreviewTemplate();

    // ensure there is a dir=rtl attribute somewhere in the page
    cy.get('[dir="rtl"]').should("exist");

    cy.go("back");
    Page.SetTextDirection(false);
    Page.PreviewTemplate();

    // ensure there is a dir=rtl attribute somewhere in the page
    cy.get('[dir="rtl"]').should("not.exist");
  });
});
