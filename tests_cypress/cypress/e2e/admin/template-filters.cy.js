/// <reference types="cypress" />

import config from "../../../config";
import { TemplateFiltersPage as Page } from "../../Notify/Admin/Pages/all";

const types = {
  en: ["Email", "Text message"],
  fr: ["Courriel", "Message texte"],
};

const categories = {
  en: ["Test"],
  fr: ["Test"],
};

describe("Template filters", () => {
  beforeEach(() => {
    cy.login(Cypress.env("NOTIFY_USER"), Cypress.env("NOTIFY_PASSWORD"));
  });

  ["en", "fr"].forEach((lang) => {
    const url =
      lang == "en"
        ? `/services/${config.Services.Cypress}/templates`
        : `/set-lang?from=/services/${config.Services.Cypress}/templates`;
    context(`App language: ${lang.toUpperCase()}`, () => {
      it("should be collapsed and set to all by default", () => {
        cy.visit(url);

        // ensure the first type filter is active by default and no others are
        Page.Components.TypeFilter()
          .find("a")
          .first()
          .should("have.class", "active");
        Page.Components.TypeFilter()
          .find("a")
          .not(":first")
          .should("not.have.class", "active");

        // ensure the first category filter is active by default and no others are
        Page.Components.CategoryFilter()
          .find("a")
          .first()
          .should("have.class", "active");
        Page.Components.CategoryFilter()
          .find("a")
          .not(":first")
          .should("not.have.class", "active");

        Page.Components.Filter().should("not.have.attr", "open");
      });

      it("should toggle", () => {
        cy.visit(url);

        Page.ToggleFilters();
        Page.Components.Filter().should("have.attr", "open");

        Page.ToggleFilters();
        Page.Components.Filter().should("not.have.attr", "open");
      });

      context("Filtering by type", () => {
        types[lang].forEach((type) => {
          it(`${type}: displays the correct number of rows`, () => {
            cy.visit(url);

            // Test type filter works
            Page.Components.Templates()
              .filter(`[data-notification-type="${type}"]`)
              .then((templates) => {
                const emailRows = templates.length;

                Page.ToggleFilters();
                Page.ApplyTypeFilter(type);
                Page.ApplyCategoryFilterAll();

                // ensure the same number of rows from the start is shown
                Page.Components.Templates()
                  .filter(":visible")
                  .should("have.length", emailRows);
              });
          });
        });
      });

      context("Filtering by category", () => {
        categories[lang].forEach((type) => {
          it(`${type}: displays the correct number of rows`, () => {
            cy.visit(url);

            // Test type filter works
            Page.Components.Templates()
              .filter(`[data-template-category="${type}"]`)
              .then((templates) => {
                const emailRows = templates.length;

                Page.ToggleFilters();
                Page.ApplyCategoryFilter(type);
                Page.ApplyTypeFilterAll();

                // ensure the same number of rows from the start is shown
                Page.Components.Templates()
                  .filter(":visible")
                  .should("have.length", emailRows);
              });
          });
        });
      });

      it("Resetting filters should show all templates", () => {
        cy.visit(url);
        Page.Components.Templates()
          .filter(":visible")
          .then((templates) => {
            const emailRows = templates.length;

            // Filter rows
            Page.ToggleFilters();
            Page.ApplyTypeFilter(types[lang][0]);
            Page.ApplyCategoryFilter(categories[lang][0]);

            // Clear filters
            Page.ApplyTypeFilterAll();
            Page.ApplyCategoryFilterAll();

            Page.Components.Templates()
              .filter(":visible")
              .should("have.length", emailRows);
          });
      });
    });
  });
});
