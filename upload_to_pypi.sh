#!/bin/bash

# Remove previous builds
rm -rf dist

# Build the package
python setup.py sdist bdist_wheel

# Upload the package to PyPI
twine upload dist/*

# Clean up
rm -rf dist build *.egg-info