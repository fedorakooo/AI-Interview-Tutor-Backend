from setuptools import find_packages, setup

setup(
    name="shared_models",
    version="0.1.0",
    author="Aliaksandr Fedaraka",
    author_email="fedorakooo@gmail.com",
    description="Shared CV and messaging models for AI Interview Tutor microservices",
    packages=find_packages(exclude=["tests*", "test*"]),
    install_requires=[
        "pydantic>=2.11.7",
    ],
    python_requires=">=3.12",
)
