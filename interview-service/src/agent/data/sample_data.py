from shared_models.cv.cv_data import CVData

SAMPLE_CV: CVData = CVData(
    user_name="Aliaksandr Fedaraka",
    specialization="Python Developer",
    education=[
        {
            "institution": "Belarusian State University of Informatics and Radioelectronics",
            "faculty": "Faculty of Computer Systems and Networks",
            "degree": "Bachelor of Science",
            "start_year": 2023,
            "end_year": 2027,
        }
    ],
    experience=[
        {
            "company": "Innowise Group",
            "role": "Python Developer",
            "start_date": "April 2025",
            "end_date": "Present",
            "responsibilities": [
                "Developing and maintaining web applications using FastAPI",
                "Developing and maintaining web applications using Django",
            ],
        }
    ],
    languages=[
        {"language": "Russian", "proficiency": "Native"},
        {"language": "English", "proficiency": "B1"},
    ],
    skills=[
        {"name": "Python", "category": "programming_language"},
        {"name": "FastAPI", "category": "framework"},
        {"name": "Django", "category": "framework"},
        {"name": "Django REST Framework", "category": "framework"},
        {"name": "SQL", "category": "database"},
        {"name": "Redis", "category": "database"},
        {"name": "MongoDB", "category": "database"},
        {"name": "Kafka", "category": "messaging"},
        {"name": "RabbitMQ", "category": "messaging"},
        {"name": "Docker", "category": "devops"},
        {"name": "Kubernetes", "category": "devops"},
        {"name": "CI/CD", "category": "devops"},
        {"name": "AWS", "category": "cloud"},
    ],
    additional_competitive_non_work_achievements=[
        "Participant in the 2024 ICPC Belarus Regional Contest",
        "Winner of BIT-Cup 2024 in the „Algorithms and Databases” section supported by SoftTeco",
    ],
)
