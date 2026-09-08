# Process types for Heroku / container-style deployment.
# Run `python pipeline.py` to (re)generate landslide_risk_output.json,
# then serve the FastAPI backend behind uvicorn.
release: python pipeline.py
web: uvicorn main:app --host 0.0.0.0 --port $PORT
worker: python train_ml_model.py
