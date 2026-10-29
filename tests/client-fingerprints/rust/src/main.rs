use std::io::{Read, Write};
use std::net::TcpStream;
use std::time::Duration;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    println!("native-tls 0.2; {}", openssl::version::version());
    // Only the local self-signed HTTPS fixture is contacted.
    let connector = native_tls::TlsConnector::builder()
        .danger_accept_invalid_certs(true)
        .danger_accept_invalid_hostnames(true)
        .build()?;
    let tcp = TcpStream::connect("ja4-server:443")?;
    tcp.set_read_timeout(Some(Duration::from_secs(15)))?;
    tcp.set_write_timeout(Some(Duration::from_secs(15)))?;
    let mut stream = connector.connect("ja4-server", tcp)?;
    stream.write_all(b"GET /rust.txt HTTP/1.1\r\nHost: ja4-server\r\nConnection: close\r\n\r\n")?;
    // Check the response headers; avoid relying on TLS close-notify policy.
    let mut response = Vec::new();
    let mut byte = [0u8; 1];
    while !response.ends_with(b"\r\n\r\n") {
        stream.read_exact(&mut byte)?;
        response.push(byte[0]);
        if response.len() > 65536 { return Err("Response headers too large".into()); }
    }
    if !response.starts_with(b"HTTP/1.1 200 ") { return Err("Unexpected response".into()); }
    Ok(())
}
