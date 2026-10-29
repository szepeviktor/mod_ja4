const https = require('node:https');

console.log(`Node.js ${process.version}; OpenSSL ${process.versions.openssl}`);
// Only the local self-signed HTTPS fixture is contacted.
const request = https.get('https://ja4-server/node.txt', {
  rejectUnauthorized: false,
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
