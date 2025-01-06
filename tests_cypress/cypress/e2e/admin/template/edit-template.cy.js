/// <reference types="cypress" />

import config from "../../../../config";
import { TemplatesPage as Page } from "../../../Notify/Admin/Pages/all";
import { Admin } from "../../../Notify/NotifyAPI";

const categories = {
  OTHER: "Other",
  AUTH: "Authentication",
  AUTOREPLY: "Automatic reply",
  TEST: "Test",
};

describe("Edit template", () => {
  context.skip("FF OFF", () => {
    // Override the process_type -> new process type should be saved for an existing template
    it("Should allow platform admin to override process type", () => {
      // login as admin
      cy.loginAsPlatformAdmin();
      cy.visit(`/services/${config.Services.Cypress}/templates`);

      // set template priority to use TC
      Page.SelectTemplateById(
        config.Services.Cypress,
        config.Templates.SMOKE_TEST_SMS,
      );
      Page.EditCurrentTemplate();
      Page.SetTemplatePriority("bulk");
      Page.SaveTemplate();

      // use api to check that it was set
      Admin.GetTemplate({
        templateId: config.Templates.SMOKE_TEST_SMS,
        serviceId: config.Services.Cypress,
      }).then((response) => {
        console.log("response", response);
        expect(response.body.data.process_type_column).to.equal("bulk");
      });

      // set template priority to normal
      Page.EditCurrentTemplate();
      Page.SetTemplatePriority("normal");
      Page.SaveTemplate();

      // use api to check that it was overridden
      Admin.GetTemplate({
        templateId: config.Templates.SMOKE_TEST_SMS,
        serviceId: config.Services.Cypress,
      }).then((response) => {
        console.log("response", response);
        expect(response.body.data.process_type_column).to.equal("normal");
      });

      // set template priority to priority
      Page.EditCurrentTemplate();
      Page.SetTemplatePriority("priority");
      Page.SaveTemplate();

      // use api to check that it was overridden
      Admin.GetTemplate({
        templateId: config.Templates.SMOKE_TEST_SMS,
        serviceId: config.Services.Cypress,
      }).then((response) => {
        console.log("response", response);
        expect(response.body.data.process_type_column).to.equal("priority");
      });
    });

    it("Should save bulk template as regular user still as bulk template", () => {
      // login as admin
      const template_name = "Test Template";

      // seed data
      cy.login();
      cy.visit(`/services/${config.Services.Cypress}/templates`);
      Page.CreateTemplate();
      Page.SelectTemplateType("email");
      Page.Continue();
      Page.FillTemplateForm(
        template_name,
        "Test Subject",
        "Test Content",
        false,
        false,
      );
      Page.SaveTemplate();

      cy.url().then((url) => {
        let templateId = url.split("/templates/")[1];

        // update category
        cy.visit(`/services/${config.Services.Cypress}/templates`);
        Page.SelectTemplate(template_name);
        Page.EditCurrentTemplate();
        Page.Components.TemplateSubject().type("a");
        Page.SaveTemplate();

        Admin.GetTemplate({
          templateId: templateId,
          serviceId: config.Services.Cypress,
        }).then((response) => {
          let template = response.body.data;
          expect(template.process_type_column).to.equal("bulk");
          Admin.DeleteTemplate({
            templateId: templateId,
            serviceId: config.Services.Cypress,
          });
        });
      });
    });
  });

  context("FF ON", () => {
    // Override the process_type -> new process type should be saved for an existing template
    it("Should allow platform admin to override process type", () => {
      // Admin user 1.
      // login as admin
      cy.loginAsPlatformAdmin();
      cy.visit(`/services/${config.Services.Cypress}/templates`);

      // set template priority to use TC
      Page.SelectTemplateById(
        config.Services.Cypress,
        config.Templates.SMOKE_TEST_EMAIL,
      );
      Page.EditCurrentTemplate();
      Page.Components.TemplateSubject().type("a");
      Page.SetTemplatePriority("bulk");
      Page.SaveTemplate();

      // use api to check that it was set
      Admin.GetTemplate({
        templateId: config.Templates.SMOKE_TEST_EMAIL,
        serviceId: config.Services.Cypress,
      }).then((response) => {
        expect(response.body.data.process_type_column).to.equal("bulk");
      });
    });

    it("Should set process_type to null and use category's process_type when non-admin changes a template's category", () => {
      cy.login();
      cy.visit(`/services/${config.Services.Cypress}/templates`);

      // Seed data with a template before we start with the test.
      Page.SeedTemplate(
        "Test Name",
        "Test Subject",
        "Test Content",
        categories.TEST,
        null,
      ).then((templateId) => {
        Page.EditCurrentTemplate();
        Page.ExpandTemplateCategories();
        Page.SelectTemplateCategory(categories.AUTH);
        Page.SaveTemplate();

        Admin.GetTemplate({
          templateId: templateId,
          serviceId: config.Services.Cypress,
        }).then((response) => {
          let template = response.body.data;
          expect(template.process_type_column).to.be.a("null");
          expect(template.template_category_id).to.not.be.a("null");
          expect(template.process_type).to.be.equal("priority"); // Computed process_type will be Auth's process type = priority
          Admin.DeleteTemplate({
            templateId: templateId,
            serviceId: config.Services.Cypress,
          });
        });
      });
    });

    it("Should override process_type when a template has a category and user is admin", () => {
      cy.loginAsPlatformAdmin();
      cy.visit(`/services/${config.Services.Cypress}/templates`);

      // Seed data with a template before we start with the test.
      Page.SeedTemplate(
        "Test Name",
        "Test Subject",
        "Test Content",
        categories.TEST,
        null,
      ).then((templateId) => {
        Page.EditCurrentTemplate();
        Page.SetTemplatePriority("priority");
        Page.SaveTemplate();

        Admin.GetTemplate({
          templateId: templateId,
          serviceId: config.Services.Cypress,
        }).then((response) => {
          let template = response.body.data;
          expect(template.process_type_column).to.not.be.a("priority");
          expect(template.template_category_id).to.not.be.a("null");
          expect(template.process_type).to.be.equal("priority"); // Computed process_type will be Auth's process type = priority
          Admin.DeleteTemplate({
            templateId: templateId,
            serviceId: config.Services.Cypress,
          });
        });
      });
    });

    it("Should set the process type to null when a category is changed and user is admin", () => {
      cy.loginAsPlatformAdmin();
      cy.visit(`/services/${config.Services.Cypress}/templates`);

      // seed data with a template before we start with the test.
      Page.SeedTemplate(
        "Test Name",
        "Test Subject",
        "Test Content",
        categories.TEST,
        null,
      ).then((templateId) => {
        Page.EditCurrentTemplate();
        Page.ExpandTemplateCategories();
        Page.SelectTemplateCategory(categories.AUTH);
        Page.SaveTemplate();

        Admin.GetTemplate({
          templateId: templateId,
          serviceId: config.Services.Cypress,
        }).then((response) => {
          let template = response.body.data;
          expect(template.process_type_column).to.be.a("null");
          expect(template.template_category_id).to.not.be.a("null");
          expect(template.process_type).to.be.equal("priority"); // Computed process_type will be Auth's process type = priority
          Admin.DeleteTemplate({
            templateId: templateId,
            serviceId: config.Services.Cypress,
          });
        });
      });
    });
  });
});
