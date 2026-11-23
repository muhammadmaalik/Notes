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

case "$OS" in
    fedora)
        # Install ParaView, Python plotting tools, and Podman
        sudo dnf install -y paraview python3-numpy python3-matplotlib podman

        # Try native COPR install first; if broken on newer Fedora (e.g., fc44), fall back to container image
        sudo dnf install -y dnf-plugins-core
        sudo dnf copr enable -y openfoam/openfoam || true
        if sudo dnf install -y openfoam-default 2>/dev/null; then
            OF_RC=$(ls -d /usr/lib/openfoam/openfoam*/etc/bashrc 2>/dev/null | tail -n 1)
            if [ -n "$OF_RC" ]; then
                grep -qxF "source $OF_RC" ~/.zshrc 2>/dev/null || echo "source $OF_RC" >> ~/.zshrc
                grep -qxF "source $OF_RC" ~/.bashrc 2>/dev/null || echo "source $OF_RC" >> ~/.bashrc
            fi
            echo "Native OpenFOAM installed! Run: source ~/.zshrc"
        else
            echo "Native COPR package unavailable for Fedora $VERSION_ID. Pulling official OpenCFD container..."
            podman pull docker.io/opencfd/openfoam-default:latest
            echo "Container setup complete! scripts/run_case.sh will automatically use Podman."
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
        echo "Installation complete! Run: source ~/.bashrc"
        ;;
    *)
        echo "Unsupported distro ($OS). Pulling official OpenCFD container via Podman/Docker..."
        if command -v podman &> /dev/null; then
            podman pull docker.io/opencfd/openfoam-default:latest
        elif command -v docker &> /dev/null; then
            docker pull opencfd/openfoam-default:latest
        else
            echo "Please install podman or docker first."
            exit 1
        fi
        ;;
esac
