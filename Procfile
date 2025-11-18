# Procfile for Render.com deployment

# Web service (API)
web: uvicorn main:app --host 0.0.0.0 --port $PORT

# Background worker
worker: dramatiq main
