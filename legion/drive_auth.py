"""One-time interactive OAuth helper (run on the deployment host, never in CI).
Usage: python -m legion.drive_auth --client-secret ~/.legion/client_secret.json --token ~/.legion/token.json
Writes a read-only Drive token to the path you give. Keep both files outside the repository."""
import argparse
def main():
    from google_auth_oauthlib.flow import InstalledAppFlow
    ap = argparse.ArgumentParser(); ap.add_argument("--client-secret", required=True); ap.add_argument("--token", required=True); a = ap.parse_args()
    creds = InstalledAppFlow.from_client_secrets_file(a.client_secret, ["https://www.googleapis.com/auth/drive.readonly"]).run_local_server(port=0)
    open(a.token, "w").write(creds.to_json()); print("token written to", a.token)
if __name__ == "__main__": main()
