let COMMON = {
    Services: {
        Cypress: 'd4e8a7f4-2b8a-4c9a-8b3f-9c2d4e8a7f4b'
    },
    Templates: {
        'SMOKE_TEST_EMAIL': 'f47ac10b-58cc-4372-a567-0e02b2c3d479',
        'SMOKE_TEST_SMS': 'e4b8f8d0-6a3b-4b9e-8c2b-1f2d3e4a5b6c',
    },
};

let STAGING = {
    CONFIG_NAME: "STAGING",
    Hostnames: {
        API: 'https://api.staging.notification.cdssandbox.xyz',
        Admin: 'https://staging.notification.cdssandbox.xyz',
        DDAPI: 'https://api.document.staging.notification.cdssandbox.xyz',
    },
};

let LOCAL = {
    CONFIG_NAME: "LOCAL",
    Hostnames: {
        API: 'http://localhost:6011',
        Admin: 'http://localhost:6012',
        DDAPI: 'http://localhost:7000',
    },
};

const config = {
    COMMON,
    STAGING,
    LOCAL,
};

// choose which config to use here
const ConfigToUse = { ...config.COMMON, ...config.STAGING };

module.exports = ConfigToUse;
