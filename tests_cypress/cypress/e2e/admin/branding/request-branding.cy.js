/// <reference types="cypress" />

import config from "../../../../config";
import { RequestBrandingPage } from "../../../Notify/Admin/Pages/all";

describe("Branding request", () => {
  // Login to notify before the test suite starts
  beforeEach(() => {
    // stop the recurring dashboard fetch requests
    cy.intercept("GET", "**/dashboard.json", {});
    cy.login();
    cy.visit(`/services/${config.Services.Cypress}/branding-request`);
  });

  it("Loads request branding page", () => {
    cy.contains("h1", "Request a new logo").should("be.visible");
  });
  it("Disallows submission when there is no data", () => {
    RequestBrandingPage.Submit();
    RequestBrandingPage.Components.BrandErrorMessage().should("be.visible");
    RequestBrandingPage.Components.LogoErrorMessage().should("be.visible");
  });

  it("Disallows submission when there is no image", () => {
    RequestBrandingPage.EnterBrandName("Test Brand");
    RequestBrandingPage.Submit();
    RequestBrandingPage.Components.LogoErrorMessage().should("be.visible");
  });

  it("Disallows submission when there is no brand name", () => {
    RequestBrandingPage.UploadBrandImage("cds2.png", "image/png");
    RequestBrandingPage.Submit();
    RequestBrandingPage.Components.BrandErrorMessage().should("be.visible");
  });

  it("Only allows pngs", () => {
    RequestBrandingPage.EnterBrandName("Test Brand");

    RequestBrandingPage.UploadBrandImage("cds2.jpg", "image/jpg");
    RequestBrandingPage.Submit();
    RequestBrandingPage.Components.LogoErrorMessage().should("be.visible");

    RequestBrandingPage.UploadBrandImage("example.json", "text/plain");
    RequestBrandingPage.Submit();
    RequestBrandingPage.Components.LogoErrorMessage().should("be.visible");

    RequestBrandingPage.UploadBrandImage("cds2.jpg", "image/png");
    RequestBrandingPage.Components.BrandPreview().should("be.visible");
  });

  it("Allows submission when all valid data provided", () => {
    RequestBrandingPage.UploadBrandImage("cds2.png", "image/png");
    RequestBrandingPage.EnterBrandName("Test Brand");
    RequestBrandingPage.Components.SubmitButton().should("be.enabled");
  });

  it("Displays branding preview", () => {
    RequestBrandingPage.UploadBrandImage("cds2.png", "image/png");
    RequestBrandingPage.Components.BrandPreview().should("be.visible");
  });

  // it('[NOT IMPLEMENTED] Rejects malicious files', () => {
  //     RequestBranding.EnterBrandName('Test Brand');
  //     RequestBranding.UploadMalciousFile();
  //     RequestBranding.Components.SubmitButton().should('be.disabled');
  // });
});
