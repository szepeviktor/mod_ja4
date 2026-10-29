require 'net/http'
require 'openssl'

puts "Ruby #{RUBY_VERSION}; #{OpenSSL::OPENSSL_LIBRARY_VERSION}"
http = Net::HTTP.new('ja4-server', 443, nil)
http.use_ssl = true
# Only the local HTTPS fixture is contacted.
http.ca_file = '/fixture/ca.pem'
http.verify_mode = OpenSSL::SSL::VERIFY_PEER
http.verify_hostname = true
http.open_timeout = 15
http.read_timeout = 15
response = http.get('/ruby.txt')
abort 'Unexpected response' unless response.code == '200' && response.body == "ok\n"
