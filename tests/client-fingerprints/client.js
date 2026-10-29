const https = require('node:https');
const fs = require('node:fs');

console.log(`Node.js ${process.version}; OpenSSL ${process.versions.openssl}`);
// Only the local HTTPS fixture is contacted.
const request = https.get('https://ja4-server/node.txt', {
  ca: fs.readFileSync('/fixture/ca.pem'),
  rejectUnauthorized: true,
  timeout: 15000,
}, (response) => {
  let body = '';
  response.setEncoding('utf8');
  response.on('data', (chunk) => { body += chunk; });
  response.on('end', () => {
    if (response.statusCode !== 200 || body !== 'ok\n') process.exitCode = 1;
  });
  response.on('error', (error) => { console.error(error); process.exitCode = 1; });
});
request.on('timeout', () => request.destroy(new Error('HTTPS timeout')));
request.on('error', (error) => { console.error(error); process.exitCode = 1; });
