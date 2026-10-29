require 'net/http'
require 'openssl'

puts "Ruby #{RUBY_VERSION}; #{OpenSSL::OPENSSL_LIBRARY_VERSION}"
http = Net::HTTP.new('ja4-server', 443, nil)
http.use_ssl = true
# Only the local self-signed HTTPS fixture is contacted.
http.verify_mode = OpenSSL::SSL::VERIFY_NONE
http.open_timeout = 15
http.read_timeout = 15
response = http.get('/ruby.txt')
abort 'Unexpected response' unless response.code == '200' && response.body == "ok\n"
