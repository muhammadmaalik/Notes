#!/usr/bin/env bash
set -e

if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
else
    echo "Error: Cannot detect Linux distribution."
    exit 1
fi

echo "Detected OS: $OS"
echo "Installing latest ESI-OpenCFD OpenFOAM (openfoam.com) + ParaView + Python tools..."

case "$OS" in
    fedora)
        sudo dnf install -y dnf-plugins-core
        sudo dnf copr enable -y openfoam/openfoam
        sudo dnf install -y openfoam-default paraview python3-numpy python3-matplotlib
        OF_RC=$(ls -d /usr/lib/openfoam/openfoam*/etc/bashrc 2>/dev/null | tail -n 1)
        if [ -n "$OF_RC" ]; then
            grep -qxF "source $OF_RC" ~/.zshrc 2>/dev/null || echo "source $OF_RC" >> ~/.zshrc
            grep -qxF "source $OF_RC" ~/.bashrc 2>/dev/null || echo "source $OF_RC" >> ~/.bashrc
        fi
        ;;
    ubuntu|debian)
        curl -s https://dl.openfoam.com/add-debian-repo.sh | sudo bash
        sudo apt-get update
        sudo apt-get install -y openfoam-default paraview python3-numpy python3-matplotlib
        OF_RC=$(ls -d /usr/lib/openfoam/openfoam*/etc/bashrc 2>/dev/null | tail -n 1)
        if [ -n "$OF_RC" ]; then
            grep -qxF "source $OF_RC" ~/.bashrc 2>/dev/null || echo "source $OF_RC" >> ~/.bashrc
        fi
        ;;
    *)
        echo "Unsupported distro ($OS). Use Docker: docker pull opencfd/openfoam-default:latest"
        exit 1
        ;;
esac

echo "Installation complete! Run: source ~/.zshrc"
