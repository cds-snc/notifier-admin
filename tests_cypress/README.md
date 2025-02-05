# Notify + Cypress 🎉

## Setup
This folder contains Cypress tests suites.  In order to run them, you'll need to install cypress and its dependencies. If you're running inside the dev container, rebuild your dev container to get the necessary packages.  

## Running the tests
### In your devcontainer
There are some issues getting the cypress UI to launch within the devcontainer.  For now, you can run the headless tests inside the dev container but if you want to launch the cypress UI you will need to do that outside of the dev container.  

There are 3 helper scripts in `package.json` to run 2 of the test suites.  Run these from the `tests_cypress/` folder:
- `npm run cypress`:  this will open Cypress with its UI and you can choose any test suite to run
- `npm run a11y`: this will run the accessibility tests in headless mode using the electron browser
- `npm run ci`: this will run the headless CI tests in headless mode using the electron browser

### Outside of your devcontainer
To launch the cypress UI, where you can choose your test suite and visually debug and inspect tests, run (from the `tests_cypress/` folder):
- `npm run cypress`: this will open the cypress UI where you can choose which tests to run and in which browser

### Local installation
To install cypress locally, use the following command, from the `tests_cypress/` folder:
```bash
npm install
npx cypress install
```

## Configuration 
- `cypress.env.json`: this file contains sensitive items like api keys and passphrases that you'll need to run the tests. You'll need to add the file `cypress.env.json` into the `tests_cypress/` folder and its contents can be found in 1password.
- `config.js`: this file contains non-sensitive items like template ids and hostnames that you'll need to run the tests

### `cypress.env.json` contents
| key                        | description                                     |
| -------------------------- | ----------------------------------------------- |
| ADMIN_SECRET               | Secret admin uses to authenticate against API   |
| ADMIN_USERNAME             | Username admin uses to authenticate against API |
| NOTIFY_USER                | Notify user used by the tests                   |
| NOTIFY_PASSWORD            | Password of NOTIFY_USER (deprecated)            |
| IMAP_PASSWORD              | IMAP password of gmail account for NOTIFY_USER  |
| CYPRESS_AUTH_USER_NAME     | Username for the Cypress auth client            | 
| CYPRESS_AUTH_CLIENT_SECRET | Secret for the Cypress auth client              |
| NOTIFY_USER                | Actual notify user CDS email account            |
| NOTIFY_PASSWORD            | Password of NOTIFY_USER (deprecated)            |
| CYPRESS_USER_PASSWORD      | Password for the Cypress user                   |
| IMAP_PASSWORD              | IMAP password of gmail account for NOTIFY_USER  |

### Target environment 🎯
The tests are configured to run against the staging environment by default.  To run the tests against your local environment, you will need to update the `ConfigToUse` variable in `config.js` file to use `LOCAL` instead of `STAGING`.  For example:
```js
const ConfigToUse = { ...config.COMMON, ...config.LOCAL };
```

