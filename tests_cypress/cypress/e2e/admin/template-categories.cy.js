/// <reference types="cypress" />

import config from "../../../config";
import { TemplatesPage as Page } from "../../Notify/Admin/Pages/all";

describe("Template categories", () => {
  beforeEach(() => {
    cy.login();
    cy.visit(`/services/${config.Services.Cypress}/templates`);
  });

  const templates = [
    {
      type: "email",
      name: "SMOKE_TEST_EMAIL",
    },
    {
      type: "sms",
      name: "SMOKE_TEST_SMS",
    },
  ];
  const categories = {
    OTHER: "Other",
    AUTH: "Authentication",
    AUTOREPLY: "General communication",
  };

  templates.forEach((template) => {
    context(`Template categories - ${template.type}`, () => {
      it("Passes a11y checks", () => {
        Page.SelectTemplate(template.name);
        cy.a11yScan(false, {
          a11y: true,
          htmlValidate: true,
          deadLinks: false,
          mimeTypes: false,
          axeConfig: false,
        });

        Page.EditCurrentTemplate();
        cy.a11yScan(false, {
          a11y: true,
          htmlValidate: true,
          deadLinks: false,
          mimeTypes: false,
          axeConfig: false,
        });

        Page.ExpandTemplateCategories();
        cy.a11yScan(false, {
          a11y: true,
          htmlValidate: true,
          deadLinks: false,
          mimeTypes: false,
          axeConfig: false,
        });
      });

      it("Shows collapsed or expanded when editing a template", () => {
        Page.SelectTemplate(template.name);
        Page.EditCurrentTemplate();
        Page.Components.TemplateCategoryButtonContainer().should("be.visible");
        Page.Components.SelectedTemplateCategoryCollapsed().should(
          "not.have.text",
          "",
        );
        Page.Components.TemplateCategoryRadiosContainer().should(
          "not.be.visible",
        );

        Page.ExpandTemplateCategories();
        Page.Components.TemplateCategories().should("be.visible");
      });

      it("Template can be saved when category is collapsed", () => {
        Page.SelectTemplate(template.name);
        Page.EditCurrentTemplate();
        Page.SaveTemplate();
      });

      it("Category shows as full list when creating a new template", () => {
        Page.CreateTemplate();
        Page.SelectTemplateType(template.type);
        Page.Continue();

        Page.Components.TemplateCategories().should("be.visible");
      });

      it("Template category must be provided for template to be saved", () => {
        Page.CreateTemplate();
        Page.SelectTemplateType(template.type);
        Page.Continue();

        Page.SaveTemplate(true);
        Page.Components.TemplateCategories()
          .find(".error-message")
          .should("be.visible");
      });

      it("Can be updated", () => {
        Page.SelectTemplate(template.name);
        Page.EditCurrentTemplate();
        Page.ExpandTemplateCategories();
        Page.SelectTemplateCategory(categories.AUTOREPLY);
        Page.SaveTemplate();

        // ensure update happened
        Page.EditCurrentTemplate();
        Page.ExpandTemplateCategories();
        Page.Components.SelectedTemplateCategory()
          .find("label")
          .contains(categories.AUTOREPLY)
          .should("be.visible");

        // re-set it
        cy.visit(`/services/${config.Services.Cypress}/templates`);
        Page.SelectTemplate(template.name);
        Page.EditCurrentTemplate();
        Page.ExpandTemplateCategories();
        Page.SelectTemplateCategory(categories.AUTH);
        Page.SaveTemplate();

        // ensure update happened
        Page.EditCurrentTemplate();
        Page.ExpandTemplateCategories();
        Page.Components.SelectedTemplateCategory()
          .find("label")
          .contains(categories.AUTH)
          .should("be.visible");
      });

      it("Can be set when creating a new template", () => {
        Page.CreateTemplate();
        Page.SelectTemplateType(template.type);
        Page.Continue();
        Page.SelectTemplateCategory(categories.AUTOREPLY);

        Page.Components.SelectedTemplateCategory()
          .find("label")
          .contains(categories.AUTOREPLY)
          .should("be.visible");
      });

      it("Template can be saved after being previewed", () => {
        Page.SelectTemplate(template.name);
        Page.EditCurrentTemplate();
        Page.ExpandTemplateCategories();
        Page.SelectTemplateCategory(categories.AUTOREPLY);
        Page.PreviewTemplate();
        Page.SaveTemplate();
      });

      it("Template can be created after being previewed", () => {
        Page.CreateTemplate();
        Page.SelectTemplateType(template.type);
        Page.Continue();

        const randomString = Math.random().toString(36).substring(2, 15);
        const subject = template.type === "email" ? "Subject" : null;
        const name = `Testing template ${randomString}`;
        Page.FillTemplateForm(name, subject, "content", categories.AUTOREPLY);
        Page.PreviewTemplate();
        Page.SaveTemplate();

        // remove the template
        cy.visit(`/services/${config.Services.Cypress}/templates`);
        Page.SelectTemplate(name);
        Page.DeleteTemplate();
      });

      context("Other/specify", () => {
        it("Category label must be provided when “other” template category selected in order to save template ", () => {
          // Start with the authentication category
          Page.SelectTemplate(template.name);
          Page.EditCurrentTemplate();
          Page.ExpandTemplateCategories();
          Page.SelectTemplateCategory(categories.AUTH);
          Page.SaveTemplate();

          Page.EditCurrentTemplate();
          Page.ExpandTemplateCategories();
          Page.SelectTemplateCategory(categories.OTHER);
          Page.SaveTemplate(true);

          Page.Components.TemplateCategories()
            .find(".error-message")
            .should("be.visible");
        });
        it("If category is already set to Other in the db, no specify field should be shown/required", () => {
          // Start with the authentication category
          Page.SelectTemplate(template.name);
          Page.EditCurrentTemplate();
          Page.ExpandTemplateCategories();
          Page.SelectTemplateCategory(categories.AUTH);
          Page.SaveTemplate();

          Page.EditCurrentTemplate();
          Page.ExpandTemplateCategories();
          Page.SelectTemplateCategory(categories.OTHER);
          Page.Components.TemplateCategoryOther().type("testing");
          Page.SaveTemplate();

          // Do it again without specifying the other field, it should still save
          Page.EditCurrentTemplate();
          Page.ExpandTemplateCategories();
          Page.SelectTemplateCategory(categories.OTHER);
          Page.SaveTemplate();
        });
      });
    });
  });
});
