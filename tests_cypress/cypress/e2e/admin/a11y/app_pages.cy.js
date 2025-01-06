/// <reference types="cypress" />

import config from "../../../../config";

const pages = [
  { name: "Landing page", route: "/accounts" },
  { name: "Your profile", route: "/user-profile" },
  { name: "Dashboard", route: `/services/${config.Services.Cypress}` },
  {
    name: "Dashboard > Notification reports",
    route: `/services/${config.Services.Cypress}/notifications/email?status=sending,delivered,failed`,
  },
  {
    name: "Dashboard > Problem emails",
    route: `/services/${config.Services.Cypress}/problem-emails`,
  },
  {
    name: "Dashboard > Monthly usage",
    route: `/services/${config.Services.Cypress}/monthly`,
  },
  {
    name: "Dashboard > Template usage",
    route: `/services/${config.Services.Cypress}/template-usage`,
  },
  {
    name: "Dashboard > Create template",
    route: `/services/${config.Services.Cypress}/templates/create?source=dashboard`,
  },
  {
    name: "Dashboard > Select template",
    route: `/services/${config.Services.Cypress}/templates?view=sending`,
  },
  { name: "API", route: `/services/${config.Services.Cypress}/api` },
  {
    name: "API > Keys",
    route: `/services/${config.Services.Cypress}/api/keys`,
  },
  {
    name: "API > Keys > Create",
    route: `/services/${config.Services.Cypress}/api/keys/create`,
  },
  {
    name: "API > Safelist",
    route: `/services/${config.Services.Cypress}/api/safelist`,
  },
  {
    name: "API > Callbacks",
    route: `/services/${config.Services.Cypress}/api/callbacks/delivery-status-callback`,
  },
  { name: "Team members", route: `/services/${config.Services.Cypress}/users` },
  {
    name: "Settings",
    route: `/services/${config.Services.Cypress}/service-settings`,
  },
  {
    name: "Settings > Change service name",
    route: `/services/${config.Services.Cypress}/service-settings/name`,
  },
  {
    name: "Templates",
    route: `/services/${config.Services.Cypress}/templates`,
  },
  {
    name: "Template > View template",
    route: `/services/${config.Services.Cypress}/templates/${config.Templates.SMOKE_TEST_EMAIL}`,
  },
  {
    name: "Template > Edit template",
    route: `/services/${config.Services.Cypress}/templates/${config.Templates.SMOKE_TEST_EMAIL}/edit`,
  },
  {
    name: "Template > Preview template",
    route: `/services/${config.Services.Cypress}/templates/${config.Templates.SMOKE_TEST_EMAIL}/preview`,
  },
  { name: "GC Notify Activity", route: "/activity" },
  { name: "Contact us", route: "/contact" },
  { name: "Create an account", route: "/register" },
  { name: "Sign in", route: "/sign-in" },
  { name: "Terms of use", route: "/terms" },
];

describe(`A11Y - App pages [${config.CONFIG_NAME}]`, () => {
  for (const page of pages) {
    it(`${page.name}`, () => {
      cy.login();
      cy.a11yScan(page.route, {
        a11y: true,
        htmlValidate: true,
        mimeTypes: false,
        deadLinks: false,
      });
    });
  }
});
