/// <reference types="cypress" />

import config from "../../../../config";
import {
  CallbacksPage as Page,
  ApiIntegrationPage as ApiPage,
} from "../../../Notify/Admin/Pages/all";
import { Admin } from "../../../Notify/NotifyAPI";

describe(
  "Delivery Receipt callbacks",
  { env: { CALLBACK_ID: "e9e1b31b-514f-47a3-a74f-01d345e423a7" } },
  () => {
    // Clean up the DB + cache before each test so our session is always clean for each test
    beforeEach(() => {
      Admin.DeleteDeliveryReceiptCallback({
        serviceId: config.Services.Cypress,
        callbackApiId: Cypress.env("CALLBACK_ID"),
      });
      Admin.ClearCache({ pattern: `service-${config.Services.Cypress}` });

      // stop the recurring dashboard fetch requests
      cy.intercept("GET", "**/dashboard.json", {});
      cy.login(Cypress.env("NOTIFY_USER"), Cypress.env("NOTIFY_PASSWORD"));
    });

    it("Hides test response time and delete buttons with no configured callback", () => {
      cy.visit(`/services/${config.Services.Cypress}/api`);
      ApiPage.Callbacks();
      Page.Components.UrlField().should("be.visible");
      Page.Components.BearerTokenField().should("be.visible");
      Page.Components.SaveButton().should("be.visible");
      Page.Components.TestResponseTimeButton().should("not.exist");
      Page.Components.DeleteButton().should("not.exist");
    });

    it("Shows test response time and delete buttons with a configured callback", () => {
      Admin.CreateDeliveryReceiptCallback({
        id: Cypress.env("CALLBACK_ID"),
        url: "https://example.com",
        bearerToken: "bestBearerToken",
      }).then(() => {
        cy.visit(`/services/${config.Services.Cypress}/api`);
        ApiPage.Callbacks();
        Page.Components.UrlField().should("be.visible");
        Page.Components.BearerTokenField().should("be.visible");
        Page.Components.SaveButton().should("be.visible");
        Page.Components.TestResponseTimeButton().should("be.visible");
        Page.Components.DeleteButton().should("be.visible");
      });
    });

    it("Validates that https is present in the url and bearer token is at least 10 characters", () => {
      cy.visit(`/services/${config.Services.Cypress}/api`);
      ApiPage.Callbacks();
      Page.FillForm("http://example.com", "1234");
      Page.SaveForm();
      cy.contains("Enter a URL that starts with https://");
      cy.contains("Must be at least 10 characters");
    });

    it("Hides footer actions on delete confirmation interstitial", () => {
      Admin.CreateDeliveryReceiptCallback({
        id: Cypress.env("CALLBACK_ID"),
        service_id: config.Services.Cypress,
        url: "https://example.com",
        bearerToken: "bestBearerToken",
      }).then(() => {
        cy.visit(`/services/${config.Services.Cypress}/api`);
        ApiPage.Callbacks();
        Page.Delete();
        Page.Components.SaveButton().should("not.exist");
        Page.Components.TestResponseTimeButton().should("not.exist");
        Page.Components.DeleteButton().should("not.exist");
      });
    });
  },
);
