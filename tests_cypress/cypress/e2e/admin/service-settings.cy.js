/// <reference types="cypress" />

import config from "../../../config";
import { ServiceSettingsPage } from "../../Notify/Admin/Pages/all";

describe("Service Settings", () => {
  beforeEach(() => {
    // stop the recurring dashboard fetch requests
    cy.intercept("GET", "**/dashboard.json", {});

    cy.login();

    cy.visit(
      config.Hostnames.Admin +
        `/services/${config.Services.Cypress}/service-settings`,
    );
  });

  it("Loads service settings page", () => {
    cy.get("h1").contains("Settings").should("be.visible");
  });

  it("Loads branding settings page", () => {
    ServiceSettingsPage.ClickChangeEmailBrandingLink();
    cy.get("h1").contains("Email logo").should("be.visible");
  });
});

describe("Platform Admin Service Settings", () => {
  beforeEach(() => {
    // stop the recurring dashboard fetch requests
    cy.intercept("GET", "**/dashboard.json", {});
    cy.login();
    cy.visit(
      config.Hostnames.Admin +
        `/services/${config.Services.Cypress}/service-settings`,
    );
  });

  it("Saves and displays new email annual limit", () => {
    ServiceSettingsPage.ClickChangeEmailAnnualLimitLink();
    cy.get("h1").contains("Annual email limit").should("be.visible");
    ServiceSettingsPage.SetMessageLimit(250000);
    ServiceSettingsPage.Submit();
    ServiceSettingsPage.Components.EmailAnnualLimit().contains(
      "250,000 emails",
    );
    ServiceSettingsPage.Components.MessageBanner().contains(
      "An email has been sent to service users",
    );
  });

  it("Saves and displays new sms annual limit", () => {
    ServiceSettingsPage.ClickChangeSmsAnnualLimitLink();
    cy.get("h1").contains("Annual text message limit").should("be.visible");
    ServiceSettingsPage.SetMessageLimit(10000);
    ServiceSettingsPage.Submit();
    ServiceSettingsPage.Components.SmsAnnualLimit().contains(
      "10,000 text messages",
    );
    ServiceSettingsPage.Components.MessageBanner().contains(
      "An email has been sent to service users",
    );
  });
});
