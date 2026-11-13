"""One-time Gmail sign-in helper. Run this on a computer WITH a browser (your Windows desktop):

    pip install google-auth-oauthlib
    python gmail-auth.py path\to\client_secret_XXXX.json

It opens Google's consent page, asks for READ-ONLY Gmail access, and writes gmail_token.json
next to this script. Copy that file plus the client secret to the server's backend/secrets/ folder.
"""
import sys
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def main() -> None:
    if len(sys.argv) != 2 or not Path(sys.argv[1]).exists():
        print(__doc__)
        sys.exit(1)
    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(sys.argv[1], SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent")
    out = Path(__file__).with_name("gmail_token.json")
    out.write_text(creds.to_json())
    print(f"\nSigned in. Token saved to {out}")
    print("Now copy BOTH files to the server:")
    print(f"  scp \"{sys.argv[1]}\" bon@192.168.0.221:~/trackhub/backend/secrets/gmail_client_secret.json")
    print(f"  scp \"{out}\" bon@192.168.0.221:~/trackhub/backend/secrets/gmail_token.json")
    print("  ssh bon@192.168.0.221 sudo systemctl restart trackhub")


if __name__ == "__main__":
    main()
