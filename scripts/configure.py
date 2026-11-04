"""Generate ignored, machine-local credentials without printing values."""

import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
path = root / ".env"
if not path.exists():
    password = secrets.token_urlsafe(24)
    values = {
        "APP_SECRET": secrets.token_urlsafe(48),
        "POSTGRES_PASSWORD": password,
        "DATABASE_URL": f"postgresql+psycopg://foundry:{password}@localhost:5432/foundry",
        "S3_SECRET_KEY": secrets.token_urlsafe(32),
        "DEV_PASSWORD": secrets.token_urlsafe(18),
    }
    content = (root / ".env.example").read_text()
    for key, value in values.items():
        content = (
            "\n".join(
                f"{key}={value}" if line.startswith(key + "=") else line for line in content.splitlines()
            )
            + "\n"
        )
    path.write_text(content)
    path.chmod(0o600)
    print("Created .env with private local credentials. No credential values were printed.")
else:
    print("Using existing .env.")
