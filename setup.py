from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="keymaster",
    version="0.1.0",
    author="Joe Azure",
    author_email="jazure@gmail.com",
    description="Secure API key management for AI services",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/joeazure/keymaster",
    packages=find_packages(exclude=["tests", "tests.*"]),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Security",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: MacOS :: MacOS X",
    ],
    python_requires=">=3.11",
    install_requires=[
        "click>=8.1.0",
        "keyring>=24.0.0",
        "pyyaml>=6.0.0",
        "cryptography>=41.0.0",
        "python-dotenv>=1.0.0",
        "structlog>=23.0.0",
        "requests>=2.31.0",
    ],
    extras_require={
        "test": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
            "pytest-mock>=3.11.1",
            "responses>=0.23.0",
            "freezegun>=1.2.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "keymaster=keymaster.cli:cli",
        ],
    },
) 