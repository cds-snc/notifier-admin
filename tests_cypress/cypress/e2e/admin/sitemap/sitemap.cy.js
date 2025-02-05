/// <reference types="cypress" />

import config from "../../../../config";
let sitemaplinks = [];
const path = "/sitemap";
const sitemap_footer_id = "nav-footer-sitemap";

describe(`Sitemap`, () => {
  it("Has link text that corresponds to page titles", () => {
    cy.visit(path);
    cy.get("main").within(() => {
      cy.get("a").each((link) => {
        sitemaplinks.push({
          url: link.prop("href"),
          text: link.text().trim(),
        });
        const link_url = link.prop("href");
        const link_text = link.text().trim();

        cy.log(`Checking sitemap link: ${link_text}/${link_url}`);
        if (
          link_url.includes(config.Hostnames.Admin) &&
          !link_url.includes("/#")
        ) {
          cy.visit(link_url);
          cy.get("h1").should("contain", `${link_text}`);
        }
      });
    });
  });

  context("Has links ordered alphabetically in each category", () => {
    ["en", "fr"].forEach((lang) => {
      it(lang === "en" ? "English" : "French", () => {
        cy.visit(`/sitemap?lang=${lang}`);
        cy.get("main").within(() => {
          cy.get("h2").each((category) => {
            const category_links = category.next("ul").find("a");
            const category_links_text = category_links
              .map((i, el) => Cypress.$(el).text().trim())
              .get();
            const category_links_text_sorted = [...category_links_text].sort();
            expect(category_links_text).to.deep.equal(
              category_links_text_sorted,
            );
          });
        });
      });
    });

    it("Does NOT display the 'You' group when logged out", () => {
      cy.visit(path);
      cy.getByTestId("sitemap-group").should("not.have.text", "Your GC Notify");
    });

    it("Does display the 'You' group when logged in", () => {
      cy.login();
      cy.visit(path);

      cy.getByTestId("sitemap-group").contains("Your GC Notify");
    });
  });

  context("Footer", () => {
    it("Has the sitemap link on app pages when logged out", () => {
      cy.then(Cypress.session.clearCurrentSessionData);
      cy.visit("/activity");

      cy.get(`#${sitemap_footer_id}`).should("be.visible");
    });
    it("Has the sitemap link on GCA pages when logged out", () => {
      cy.then(Cypress.session.clearCurrentSessionData);
      cy.visit("/features");

      cy.get('a[href="/sitemap"]').should("be.visible");
    });
    it("Has the sitemap link on app pages when logged in", () => {
      cy.login();
      cy.visit("/activity");

      cy.get(`#${sitemap_footer_id}`).should("be.visible");
    });
    it("Has the sitemap link on GCA pages when logged in", () => {
      cy.login();
      cy.visit("/features");

      cy.get('a[href="/sitemap"]').should("be.visible");
    });
  });
});
