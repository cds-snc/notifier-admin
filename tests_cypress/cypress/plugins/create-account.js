const http = require('http');
const https = require('https');

// TODO: This duplicates some code in Notify/NotifyAPI.js and should be consolidated
const Utilities = {
    CreateJWT: (username, secret) => {
        const jwt = require('jsrsasign');
        const claims = {
            'iss': username,
            'iat': Math.round(Date.now() / 1000)
        }

        const headers = { alg: "HS256", typ: "JWT" };
        return jwt.jws.JWS.sign("HS256", JSON.stringify(headers), JSON.stringify(claims), secret);
    },
    GenerateID: (length = 10) => {
        const characters = '0123456789abcdefghijklmnopqrstuvwxyz';
        let result = '';
        const charactersLength = characters.length;
        for (let i = 0; i < length; i++) {
            result += characters.charAt(Math.floor(Math.random() * charactersLength));
        }
        return result;
    }
};

const createAccount = async (baseUrl, username, secret) => {
    // return a generated id
    const token = Utilities.CreateJWT(username, secret);
    const generatedUsername = Utilities.GenerateID(10);
    const url = `${baseUrl}/cypress/create_user/${generatedUsername}`;

    return new Promise((resolve, reject) => {
        const options = {
            method: 'POST',
            headers: {
                Authorization: `Bearer ${token}`,
                "Content-Type": 'application/json',
                'Content-Length': 0
            },
        };
        
        const getHttpModule = (url) => url.startsWith('https://') ? https : http;

        const req = getHttpModule(url).request(url, options, (res) => {
            let data = '';

            // A chunk of data has been received.
            res.on('data', (chunk) => {
                data += chunk;
            });

            // The whole response has been received.
            res.on('end', () => {
                try {
                    const parsedData = JSON.parse(data);
                    resolve(parsedData);
                } catch (e) {
                    reject(e);
                }
            });
        });

        req.on('error', (error) => {
            reject(error); // Reject the promise on request error
        });
        
        req.end();
    });
};


module.exports = createAccount;
