#!/bin/bash
# MeatBagPnP Runner Script
# Activates the virtual environment and runs the application

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Change to the project directory
cd "$SCRIPT_DIR"

# Check if virtual environment exists
if [ ! -d "venv_arm" ]; then
    echo "Virtual environment 'venv_arm' not found!"
    echo "Please create it first with: python3 -m venv venv_arm"
    echo "Then install dependencies with: source venv_arm/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Activate virtual environment and run the application
echo "Activating virtual environment and starting MeatBagPnP..."
source venv_arm/bin/activate

# Run the application with all passed arguments
python meatbag.py "$@"
