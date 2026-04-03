# lambda_function.py
from mangum import Mangum
from app import app  # Import your FastAPI app

# Lambda handler
handler = Mangum(app, lifespan="off")
