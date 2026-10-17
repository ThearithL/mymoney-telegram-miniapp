import os
from app import create_app
from deployment_config import validate_vercel_environment

validate_vercel_environment(os.environ)
app = create_app()
