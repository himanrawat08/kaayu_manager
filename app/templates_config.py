from fastapi.templating import Jinja2Templates
from pathlib import Path

from app.config import settings
from app.services import storage

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))
templates.env.globals["root_path"] = settings.ROOT_PATH
templates.env.globals["email_tool_url"] = settings.EMAIL_TOOL_URL
templates.env.globals["storage_url"] = storage.public_url
