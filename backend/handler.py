from pathlib import Path
import sys

from mangum import Mangum

sys.path.append(str(Path(__file__).resolve().parent))

from app.main import app


handler = Mangum(app)
