import os

os.environ.setdefault("RABBITMQ_PORT", "5672")
os.environ.setdefault("RABBITMQ_HOST", "localhost")
os.environ.setdefault("RABBITMQ_USER", "guest")
os.environ.setdefault("RABBITMQ_PASSWORD", "guest")
os.environ.setdefault("MONGODB_PORT", "27017")
os.environ.setdefault("MONGODB_HOST", "localhost")
os.environ.setdefault("MONGODB_USER", "app")
os.environ.setdefault("MONGODB_PASSWORD", "app")
os.environ.setdefault("MONGODB_DB_NAME", "ai_interview")
os.environ.setdefault("MONGODB_CV_ANALYSIS_COLLECTION_NAME", "cv_analysis")
