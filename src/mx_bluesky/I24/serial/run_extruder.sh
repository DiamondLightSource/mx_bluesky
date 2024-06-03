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

# Wait for blueapi to start
for i in {1..30}
do
    echo "$(date)"
    curl --head -X GET http://localhost:25565/status >/dev/null
    ret_value=$?
    if [ $ret_value -ne 0 ]; then
        sleep 1
    else
        break
    fi
done

if [ $ret_value -ne 0 ]; then
    echo "$(date) BLUEAPI Failed to start!!!!"
    exit 1
else
    echo "$(date) BLUEAPI started"
fi

# Open the edm screen for an extruder serial collection
echo "Starting extruder edm screen."
edm -x "${edm_path}/EX-gui/DiamondExtruder-I24-py3v1.edl"

echo "Edm screen closed, bye!"

pgrep blueapi | xargs kill -9
echo "Blueapi process killed"