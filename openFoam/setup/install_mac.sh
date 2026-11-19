#!/usr/bin/env bash
set -e

if ! command -v docker &> /dev/null; then
    echo "Error: Install Docker Desktop for Mac first: https://docker.com"
    exit 1
fi

docker pull opencfd/openfoam-default:latest
echo "Launch OpenFOAM anytime with:"
echo "  docker run -it --rm -v \"\$(pwd)\":/home/openfoam/work -w /home/openfoam/work opencfd/openfoam-default:latest"
