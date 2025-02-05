// used to check the email inbox
const imaps = require('imap-simple')
const nodemailer = require("nodemailer");
// used to parse emails from the inbox
const simpleParser = require('mailparser').simpleParser
const env = require('../../cypress.env.json');
const _ = require('lodash');

const emailAccount = async () => {

    const emailConfig = {
        imap: {
            user: env.NOTIFY_USER,
            password: env.IMAP_PASSWORD,
            host: 'imap.gmail.com',
            port: 993,
            tls: true,
            authTimeout: 10000,
            tlsOptions: {
                rejectUnauthorized: false
            }
        },
    }

    const userEmail = {
        /**
         * Utility method for getting the last email
         * for the Ethereal email account
         */
        async deleteAllEmails() {
            try {
                const connection = await imaps.connect(emailConfig)

                // grab up to 50 emails from the inbox
                await connection.openBox('INBOX')
                const searchCriteria = ['1:50']
                const fetchOptions = {
                    bodies: [''],
                }
                const messages = await connection.search(searchCriteria, fetchOptions)

                if (!messages.length) {
                    // and close the connection to avoid it hanging
                    connection.end()
                    return null
                } else {
                    // delete all messages
                    const uidsToDelete = messages
                        .filter(message => {
                            return message.parts
                        })
                        .map(message => message.attributes.uid);

                    if (uidsToDelete.length > 0) {
                        await connection.deleteMessage(uidsToDelete);
                    }
                    // and close the connection to avoid it hanging
                    connection.end()

                    // and returns the main fields
                    return {}
                }
            } catch (e) {
                // and close the connection to avoid it hanging
                // connection.end()
                console.error(e)
                return null
            }
        },
        /**
         * Utility method for getting the last email
         * for the Ethereal email account 
         */
        async getLastEmail(emailAddress) {
            let connection;
            try {
                connection = await imaps.connect(emailConfig);

                // grab up to 50 emails from the inbox
                await connection.openBox('INBOX');
                const searchCriteria = ['UNSEEN'];
                const fetchOptions = {
                    bodies: [''],
                    struct: true,
                };
                const messages = await connection.search(searchCriteria, fetchOptions);

                if (!messages.length) {
                    return null;
                } else {
                    let latestMail = null;
                    let uidsToDelete = [];
                    for (const message of messages) {
                        const mail = await simpleParser(message.parts[0].body);
                        const to_address = mail.to.value[0].address;

                        if (to_address == emailAddress) {
                            uidsToDelete.push(message.attributes.uid);
                            latestMail = {
                                subject: mail.subject,
                                text: mail.text,
                                html: mail.html,
                            };
                        }
                    }

                    try {
                        if (uidsToDelete.length > 0) {
                            await connection.deleteMessage(uidsToDelete);
                            await connection.imap.expunge();
                        }
                    } catch (e) {
                        console.error('delete error', uidsToDelete, e);
                    }

                    return latestMail;
                }
            } catch (e) {
                console.error(e);
                return null;
            } finally {
                if (connection) {
                    connection.end();
                }
            }
        },
        async fetchEmail(acct) {
            const _config = {
                imap: {
                    user: acct.user,
                    password: acct.pass,
                    host: "imap.ethereal.email", //'imap.gmail.com',
                    port: 993,
                    tls: true,
                    authTimeout: 10000,
                    tlsOptions: {
                        rejectUnauthorized: false
                    }
                },
            }
            try {
                const connection = await imaps.connect(_config)

                // grab up to 50 emails from the inbox
                await connection.openBox('INBOX')
                const searchCriteria = ['1:50', 'UNDELETED']
                const fetchOptions = {
                    bodies: [''],
                }
                const messages = await connection.search(searchCriteria, fetchOptions)
                // and close the connection to avoid it hanging
                connection.end()

                if (!messages.length) {
                    return null
                } else {

                    // grab the last email
                    const mail = await simpleParser(
                        messages[messages.length - 1].parts[0].body,
                    )
                    // console.log('m', mail)
                    // and returns the main fields
                    return {
                        subject: mail.subject,
                        to: mail.to.text,
                        from: mail.from.text.replace(/<|>/g, ''),
                        html: mail.html,
                        totalEmails: messages.length,
                        attachments: mail.attachments
                    }
                }
            } catch (e) {
                // and close the connection to avoid it hanging
                // connection.end()

                console.error(e)
                return null
            }
        }
    }

    return userEmail
}

module.exports = emailAccount
