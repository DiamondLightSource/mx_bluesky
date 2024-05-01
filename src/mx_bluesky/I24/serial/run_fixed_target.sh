#!/bin/bash

# Get edm path from input
edm_path=$1

# Get the directory of this script
current=$( realpath "$( dirname "$0" )" )

# Start rabbitMQ here 
# TODO

# Start the blueapi worker using the config file in this module
echo "Starting the blueapi runner"
blueapi -c "${current}/blueapi_config.yaml" serve

# Open the edm screen for a fixed target serial collection
echo "Starting fixed target edm screen."
edm -x "${edm_path}/FT-gui/DiamondChipI24-py3v1.edl"

echo "Edm screen closed, bye!"