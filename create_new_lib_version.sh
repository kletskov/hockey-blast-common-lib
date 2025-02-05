#!/bin/bash

# Step 1: Change directory to the subfolder and dump the sample database
echo "Changing directory to hockey_blast_common_lib and dumping the sample database..."
cd hockey_blast_common_lib
./dump_sample_db.sh
cd ..

# Step 2: Upload the new library version to PyPI
echo "Uploading the new library version to PyPI..."
source .venv/bin/activate
./upload_to_pypi.sh
deactivate

echo "New library version creation process completed."
