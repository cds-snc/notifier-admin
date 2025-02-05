/// <reference types="cypress" />

import config from "../../../../config";
import {
  EditBrandingPage,
  BrandingSettingsPage,
} from "../../../Notify/Admin/Pages/all";

describe("Edit Branding", () => {
  beforeEach(() => {
    // stop the recurring dashboard fetch requests
    cy.intercept("GET", "**/dashboard.json", {});

    cy.login();

    cy.visit(`/services/${config.Services.Cypress}/edit-branding`);
  });

  it("Loads branding settings page", () => {
    cy.visit(`/services/${config.Services.Cypress}/branding`);
    cy.get("h1").contains("Email logo").should("be.visible");
  });

  it("Shows images of the default EN and FR branding", () => {
    EditBrandingPage.Components.BrandFieldset().within(() => {
      cy.get("img")
        .first()
        .should("have.attr", "src")
        .then((src) => {
          expect(src).to.include("gc-logo-en.png");
        });
      cy.get("img")
        .last()
        .should("have.attr", "src")
        .then((src) => {
          expect(src).to.include("gc-logo-fr.png");
        });
    });
  });

  it("Loads edit-branding when choose logo is clicked", () => {
    cy.visit(`/services/${config.Services.Cypress}/branding`);
    BrandingSettingsPage.ChooseDifferentLogo();
    cy.get("h1").contains("Change your logo").should("be.visible");
  });

  it("Cannot submit when no selection was made", () => {
    EditBrandingPage.Submit();
    EditBrandingPage.Components.ErrorMessage().should("be.visible");
  });

  it("Saves English-first logo when selected", () => {
    EditBrandingPage.SelectDefaultBranding("en");
    EditBrandingPage.Submit();
    BrandingSettingsPage.Components.StatusBanner()
      .should("be.visible")
      .and("contain", "Setting updated");
    BrandingSettingsPage.Components.TemplatePreview()
      .first()
      .should(
        "have.attr",
        "alt",
        "Government of Canada / Gouvernement du Canada",
      );
  });

  it("Saves French-first logo when selected", () => {
    EditBrandingPage.SelectDefaultBranding("fr");
    EditBrandingPage.Submit();
    BrandingSettingsPage.Components.StatusBanner()
      .should("be.visible")
      .and("contain", "Setting updated");
    BrandingSettingsPage.Components.TemplatePreview()
      .first()
      .should(
        "have.attr",
        "alt",
        "Gouvernement du Canada / Government of Canada",
      );
  });

  it("Navigates to branding pool when select another logo from test link is clicked", () => {
    EditBrandingPage.ClickBrandPool();
    cy.contains("h1", "Select another logo").should("be.visible");
  });

  it("Navigates to edit branding when go back is clicked from the branding pool page", () => {
    EditBrandingPage.ClickBrandPool();
    BrandingSettingsPage.GoBack();
    cy.get("h1").contains("Change your logo").should("be.visible");
  });
});
