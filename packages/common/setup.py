from setuptools import setup, find_packages

setup(
    name="ecommerce-common",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "fastapi",
        "pydantic",
        "pydantic-settings",
        "motor",
        "aio-pika",
        "pyjwt",
        "argon2-cffi",
    ],
)
