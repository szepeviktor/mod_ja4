use std::time::Duration;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    println!("reqwest 0.13; default TLS backend (rustls)");
    // Only the local HTTPS fixture is contacted.
    let certificate = reqwest::Certificate::from_pem(&std::fs::read("/fixture/ca.pem")?)?;
    let client = reqwest::blocking::Client::builder()
        .add_root_certificate(certificate)
        .timeout(Duration::from_secs(15))
        .build()?;
    let response = client.get("https://ja4-server/rust.txt").send()?;
    if response.status() != reqwest::StatusCode::OK || response.text()? != "ok\n" {
        return Err("Unexpected response".into());
    }
    Ok(())
}
