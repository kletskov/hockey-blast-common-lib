from setuptools import setup, find_packages

setup(
    name='hockey-blast-common-lib',  # The name of your package
    version='0.1.48',
    description='Common library for shared functionality and DB models',
    author='Pavel Kletskov',
    author_email='kletskov@gmail.com',
    packages=find_packages(),  # Automatically find all packages
    include_package_data=True,  # Include non-Python files specified in MANIFEST.in
    install_requires=[
        "setuptools",  # For package management
        "Flask-SQLAlchemy",  # For Flask database interactions
        "SQLAlchemy",  # For database interactions
        "requests",    # For HTTP requests
    ],
    python_requires='>=3.7',  # Specify the Python version compatibility
)

