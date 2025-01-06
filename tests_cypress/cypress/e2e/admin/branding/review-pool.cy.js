/// <reference types="cypress" />

import config from "../../../../config";

import {
  ReviewPoolPage,
  EditBrandingPage,
} from "../../../Notify/Admin/Pages/all";

describe("Review Pool", () => {
  beforeEach(() => {
    cy.login();
    cy.visit(`/services/${config.Services.Cypress}/review-pool`);
  });
  context("General page functionality", () => {
    it("Loads review pool page", () => {
      cy.contains("h1", "Select another logo").should("be.visible");
    });

    it("Loads request branding page when [request a new logo] link is clicked", () => {
      ReviewPoolPage.ClickRequestNewLogoLink();
      cy.get("h1").contains("Request a new logo").should("be.visible");
    });

    it("Returns to edit branding page when back link is clicked", () => {
      cy.visit(`/services/${config.Services.Cypress}/edit-branding`);
      EditBrandingPage.ClickBrandPool();
      ReviewPoolPage.ClickBackLink();
      cy.get("h1").contains("Change your logo").should("be.visible");
    });
  });

  // TODO: implement an api method to clear the cache and use it in these tests
  //   context("Service's org has no custom branding", () => {
  //     // TODO: Move this functionality into the ClearCachePage as an action
  //     //       or perhaps make it a cy.command that we just pass the cache
  //     //       we want to clear to?
  //     before(() => {
  //       // Make sure we're logged out
  //       cy.clearCookie(ADMIN_COOKIE);
  //       // Link the test service to the org without branding
  //       Admin.LinkOrganisationToService({
  //         orgId: config.Organisations.NO_CUSTOM_BRANDING_ORG_ID,
  //         serviceId: config.Services.Cypress,
  //       });
  //       // Login as admin
  //       cy.login(
  //         Cypress.env("NOTIFY_ADMIN_USER"),
  //         Cypress.env("NOTIFY_PASSWORD"),
  //       );
  //       cy.visit("/platform-admin/clear-cache");
  //       // Clear the Service cache via the admin panel
  //       ClearCachePage.SelectCacheToClear("service");
  //       ClearCachePage.ClickClearCacheButton();
  //       // Logout and log back in as regular test user and nav to the review-pool page
  //       cy.clearCookie(ADMIN_COOKIE);
  //       cy.login(Cypress.env("NOTIFY_USER"), Cypress.env("NOTIFY_PASSWORD"));
  //       cy.visit(
  //         config.Hostnames.Admin +
  //           `/services/${config.Services.Cypress}/review-pool`,
  //       );
  //     });

  //     it("Displays a banner indicating there is no custom branding associated with their organisation and a link to request custom branding", () => {
  //       ReviewPoolPage.Components.EmptyListContainer().should("be.visible");
  //       cy.contains("a", "Request a new logo").should("be.visible");
  //     });
  //   });

  //   context("Service's org has custom branding", () => {
  //     before(() => {
  //       // Make sure we're logged out
  //       cy.clearCookie(ADMIN_COOKIE);
  //       // Link the test service to the org without branding
  //       Admin.LinkOrganisationToService({
  //         orgId: config.Organisations.DEFAULT_ORG_ID,
  //         serviceId: config.Services.Cypress,
  //       });
  //       // Login as admin
  //       cy.login(
  //         Cypress.env("NOTIFY_ADMIN_USER"),
  //         Cypress.env("NOTIFY_PASSWORD"),
  //       );
  //       cy.visit("/platform-admin/clear-cache");
  //       // Clear the Service cache via the admin panel
  //       ClearCachePage.SelectCacheToClear("service");
  //       ClearCachePage.ClickClearCacheButton();
  //       // Logout and log back in as regular test user and nav to the review-pool page
  //       cy.clearCookie(ADMIN_COOKIE);
  //       cy.login(Cypress.env("NOTIFY_USER"), Cypress.env("NOTIFY_PASSWORD"));
  //     });

  //     beforeEach(() => {
  //       cy.visit(
  //         config.Hostnames.Admin +
  //           `/services/${config.Services.Cypress}/review-pool`,
  //       );
  //     });

  //     it("Displays a list of available logos", () => {
  //       // In a full E2E test, we would check for exactly the number of logos
  //       // associated with the service's org
  //       ReviewPoolPage.Components.AvailableLogoRadios().should("exist");
  //     });

  //     it("Saves the selected custom logo", () => {
  //       ReviewPoolPage.SelectLogoRadio();
  //       ReviewPoolPage.ClickPreviewButton();
  //       cy.contains("h1", "Logo preview").should("be.visible");
  //       PreviewBrandingPage.ClickSaveBranding();
  //       BrandingSettings.Components.StatusBanner().should("be.visible");
  //     });
  //   });
});
