from sqlalchemy import select

from .config import settings
from .db import Session, uid
from .models import Membership, Organization, Project, User
from .security import passwords
from .storage import initialize

TEXT_SCHEMA = {
    "type": "object",
    "required": ["prompt", "response"],
    "properties": {
        "prompt": {"type": "string", "minLength": 1},
        "response": {"type": "string", "minLength": 1},
    },
}

IMAGE_SCHEMA = {
    "type": "object",
    "required": ["image"],
    "properties": {
        "image": {
            "type": "object",
            "required": ["width", "height", "artifact", "thumbnail", "dhash"],
            "properties": {
                "width": {"type": "integer", "minimum": 1},
                "height": {"type": "integer", "minimum": 1},
                "artifact": {"type": "object"},
                "thumbnail": {"type": "object"},
                "dhash": {"type": "string", "pattern": "^[a-f0-9]{16}$"},
            },
        }
    },
}


def main():
    initialize()
    with Session.begin() as db:
        for org_name, email, name in [
            ("Atlas Research", "alex@foundry.local", "Alex Morgan"),
            ("Meridian Lab", "blair@foundry.local", "Blair Chen"),
        ]:
            if db.scalar(select(User).where(User.email == email)):
                continue
            user = User(
                id=uid("usr"), email=email, name=name, password_hash=passwords.hash(settings().dev_password)
            )
            org = Organization(id=uid("org"), name=org_name)
            db.add_all([user, org])
            db.flush()
            db.add(Membership(user_id=user.id, organization_id=org.id, role="Owner"))
            db.add(Project(id=uid("prj"), organization_id=org.id, name="Research workspace"))
    print("Local storage and two independent development organizations initialized; no passwords printed.")


if __name__ == "__main__":
    main()
