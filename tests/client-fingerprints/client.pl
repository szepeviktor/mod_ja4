use strict;
use warnings;
use LWP::UserAgent;
use LWP::Protocol::https;
use IO::Socket::SSL;
use Net::SSLeay;

printf "Perl %s; LWP::UserAgent %s; LWP::Protocol::https %s; IO::Socket::SSL %s; Net::SSLeay %s; %s\n",
    $^V, $LWP::UserAgent::VERSION, $LWP::Protocol::https::VERSION,
    $IO::Socket::SSL::VERSION, $Net::SSLeay::VERSION, Net::SSLeay::SSLeay_version(0);

# Only the local HTTPS fixture is contacted; retain the library's TLS defaults.
my $client = LWP::UserAgent->new(
    timeout => 15,
    max_redirect => 0,
    ssl_opts => {
        SSL_ca_file => '/fixture/ca.pem',
        SSL_verify_mode => IO::Socket::SSL::SSL_VERIFY_PEER(),
        verify_hostname => 1,
    },
);
my $response = $client->get('https://ja4-server/perl.txt');
die $response->status_line . "\n" unless $response->code == 200;
die "Unexpected response body\n" unless $response->content eq "ok\n";
