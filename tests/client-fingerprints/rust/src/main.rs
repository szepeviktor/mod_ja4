use std::time::Duration;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    println!("reqwest 0.13; default TLS backend (rustls)");
    // Only the local self-signed HTTPS fixture is contacted.
    let client = reqwest::blocking::Client::builder()
        .danger_accept_invalid_certs(true)
        .timeout(Duration::from_secs(15))
        .build()?;
    let response = client.get("https://ja4-server/rust.txt").send()?;
    if response.status() != reqwest::StatusCode::OK || response.text()? != "ok\n" {
        return Err("Unexpected response".into());
    }
    Ok(())
}
