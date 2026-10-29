package main

import (
	"crypto/tls"
	"fmt"
	"io"
	"net/http"
	"os"
	"runtime"
	"time"
)

func main() {
	fmt.Printf("Go %s; crypto/tls\n", runtime.Version())
	transport := http.DefaultTransport.(*http.Transport).Clone()
	// Only the local self-signed HTTPS fixture is contacted.
	transport.TLSClientConfig = &tls.Config{InsecureSkipVerify: true}
	defer transport.CloseIdleConnections()
	client := &http.Client{Transport: transport, Timeout: 15 * time.Second}
	if err := check(client); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func check(client *http.Client) error {
	response, err := client.Get("https://ja4-server/go.txt")
	if err != nil {
		return err
	}
	defer response.Body.Close()
	body, err := io.ReadAll(response.Body)
	if err != nil {
		return err
	}
	if response.StatusCode != http.StatusOK || string(body) != "ok\n" {
		return fmt.Errorf("unexpected response: status=%d body=%q", response.StatusCode, body)
	}
	return nil
}
