var config = require('./config');

const { defineConfig } = require("cypress");
const EmailAccount = require("./cypress/plugins/email-account");
const CreateAccount = require("./cypress/plugins/create-account");
const htmlvalidate = require("cypress-html-validate/plugin");

module.exports = defineConfig({
  e2e: {
    baseUrl: config.Hostnames.Admin,
    setupNodeEvents: async (on, config) => {
      htmlvalidate.install(on, {
        rules: {
          "form-dup-name": "off",
          "prefer-native-element": ["error", {
            "exclude": ["button", "link"]
          }],
          "no-redundant-role": "off",
          "no-dup-class": "off",
          "require-sri": "off",
        },
      });

      const emailAccount = await EmailAccount()

      on('task', {
        log(message) { // for debugging
          console.log(message)
          return null
        },
        // Email Account ///
        getLastEmail(emailAddress) {
          return emailAccount.getLastEmail(emailAddress)
        },
        deleteAllEmails() {
          return emailAccount.deleteAllEmails()
        },
        fetchEmail(acct) {
          return emailAccount.fetchEmail(acct)
        },
        createAccount({ baseUrl, username, secret }) {
          if (global.acct) {
            return global.acct;
          } else {
            let acct = CreateAccount(baseUrl, username, secret);
            global.acct = acct;
            return acct
          }          
        },
        getUserName() {
          return global.acct;
        }
      });

      on('before:browser:launch', (browser = {}, launchOptions) => {
        if (browser.family === 'chromium' && browser.name !== 'electron') {
          launchOptions.extensions = [];
        }
        return launchOptions;
      });
    },
    specPattern: '**/e2e/**/*.cy.js',
    watchForFileChanges: false,
    blockHosts: ['*google-analytics.com', 'stats.g.doubleclick.net', 'bam.nr-data.net', '*newrelic.com', '*qualtrics.com'],
    viewportWidth: 1280,
    viewportHeight: 850,
    testIsolation: true,
    retries: 3
  },
});
