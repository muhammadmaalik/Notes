# Setup & Cross-Platform Installers (setup/)

- install_linux.sh   : Installs OpenFOAM on Fedora, Ubuntu, or Debian (uses Podman fallback on Fedora 44+ -- The OS that I'm testing this on is Fedora 44, do make sure to install any other dependencies based on your Operating System)
- install_mac.sh     : Pulls official opencfd/openfoam-default Docker image for macOS
- install_windows.ps1: Installs Ubuntu on WSL2 for Windows 10/11
