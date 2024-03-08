import config from "../../../../config";
import { LoginPage } from "../../../Notify/Admin/Pages/all";

const BrandingRoutes = [
    '/edit-branding', '/branding-request', '/review-pool', '/preview-branding'
];

describe('Branding request', () => {
    // Login to notify before the test suite starts
    before(() => {
        cy.login(Cypress.env('NOTIFY_USER'), Cypress.env('NOTIFY_PASSWORD'));
    });

    beforeEach(() => {
        // stop the recurring dashboard fetch requests
        cy.intercept('GET', '**/dashboard.json', {});
    });


    // perform a11yScan on all pages in the branding_pages array
    BrandingRoutes.forEach((page) => {
        it(`${page} is accessible and has valid HTML`, () => {
            cy.a11yScan(
                config.Hostnames.Admin + `/services/${config.Services.Cypress}${page}`, 
                { 
                    a11y: true, 
                    htmlValidate: true, 
                    deadLinks: false, 
                    mimeTypes: false
                }
            );
        });
    });
});
