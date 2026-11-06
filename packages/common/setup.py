from setuptools import find_packages, setup

setup(
    name="ecommerce-common",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "fastapi",
        "pydantic",
        "pydantic-settings",
        "email-validator",
        "motor",
        "aio-pika",
        "pyjwt",
        "argon2-cffi",
    ],
)
