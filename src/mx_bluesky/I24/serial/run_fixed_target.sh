#!/bin/bash

# Get edm path from input
edm_path=$1

# Get the directory of this script
current=$( realpath "$( dirname "$0" )" )

# Start rabbitMQ here 
# podman run -it --rm --net host rmohr/activemq:5.15.9-alpine

# Start the blueapi worker using the config file in this module
echo "Starting the blueapi runner"
blueapi -c "${current}/blueapi_config.yaml" serve &

# Open the edm screen for a fixed target serial collection
echo "Starting fixed target edm screen."
edm -x "${edm_path}/FT-gui/DiamondChipI24-py3v1.edl"

echo "Edm screen closed, bye!"

pgrep blueapi | xargs kill -9
echo "Blueapi process killed"