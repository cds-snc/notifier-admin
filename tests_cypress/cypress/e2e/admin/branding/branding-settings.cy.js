/// <reference types="cypress" />

import config from "../../../../config";
import ServiceSettingsPage from "../../../Notify/Admin/Pages/ServiceSettingsPage";
import { EditBrandingPage } from "../../../Notify/Admin/Pages/all";

describe("Branding settings", () => {
  beforeEach(() => {
    // stop the recurring dashboard fetch requests
    cy.intercept("GET", "**/dashboard.json", {});

    cy.login();

    cy.visit(`/services/${config.Services.Cypress}/service-settings`);
  });

  it("Loads branding settings page", () => {
    ServiceSettingsPage.ClickChangeEmailBrandingLink();
    cy.get("h1").contains("Email logo").should("be.visible");
  });

  // Broken currently
  it("returns to service settings page when back link is clicked", () => {
    ServiceSettingsPage.ClickChangeEmailBrandingLink();
    EditBrandingPage.ClickBackLink();
    cy.get("h1").contains("Settings").should("be.visible");
  });
});
