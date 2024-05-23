set -x

current=$( realpath "$( dirname "$0" )" )

blueapi -c "${current}/blueapi_config.yaml" controller run $@
