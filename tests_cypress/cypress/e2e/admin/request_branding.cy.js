/// <reference types="cypress" />

import config from "../../../config";
import { RequestBranding, LoginPage } from "../../Notify/Admin/Pages/all";

describe('Branding request', () => {

    // Login to notify before the test suite starts
    before(() => {
        LoginPage.Login(Cypress.env('NOTIFY_USER'), Cypress.env('NOTIFY_PASSWORD'));

        // ensure we logged in correctly
        cy.contains('h1', 'Sign-in history').should('be.visible');
    });

    beforeEach(() => {
        // stop the recurring dashboard fetch requests
        cy.intercept('GET', '**/dashboard.json', {});
        cy.visit(config.Hostnames.Admin + `/services/${config.Services.Cypress}/branding-request`);
    });

    it('Loads request branding page', () => {
        cy.contains('h1', 'New branding request').should('be.visible');
    });

    it('Disallows submission when there is no data', () => {
        RequestBranding.Components.SubmitButton().should('be.disabled');
    });

    it('Disallows submission when there is no image', () => {      
        RequestBranding.EnterBrandName('Test Brand');
        RequestBranding.Components.SubmitButton().should('be.disabled');
    });

    it('Disallows submission when there is no brand name', () => {      
        RequestBranding.UploadBrandImage('cds2.png', 'image/png');
        RequestBranding.Components.SubmitButton().should('be.disabled');
    });

    it('Only allows pngs', () => {
        RequestBranding.EnterBrandName('Test Brand');

        RequestBranding.UploadBrandImage('cds2.jpg', 'image/jpg');
        RequestBranding.Components.SubmitButton().should('be.disabled');
        
        RequestBranding.UploadBrandImage('example.json', 'text/plain');
        RequestBranding.Components.SubmitButton().should('be.disabled');
        
        RequestBranding.UploadBrandImage('cds2.jpg', 'image/png');
        RequestBranding.Components.BrandPreview().should('be.visible');        
        RequestBranding.Components.SubmitButton().should('be.enabled');
    });
    
    it('Allows submission when all valid data provided', () => {      
        RequestBranding.UploadBrandImage('cds2.png', 'image/png');
        RequestBranding.EnterBrandName('Test Brand');
        RequestBranding.Components.SubmitButton().should('be.enabled');
    });

    it('Displays branding preview', () => {      
        RequestBranding.UploadBrandImage('cds2.png', 'image/png');
        RequestBranding.Components.BrandPreview().should('be.visible');        
    });

    it('Rejects malicious files', () => {
        RequestBranding.EnterBrandName('Test Brand');
        RequestBranding.UploadMalciousFile();
        RequestBranding.Components.SubmitButton().should('be.disabled');
    });
});