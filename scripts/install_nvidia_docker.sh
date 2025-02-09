#!/bin/bash
# Copyright 2020 Google LLC.
# This script is used to install nvidia docker on Ubutun 20.04.
# For different Linux distributions and versions, modifications might be needed.

set -euo pipefail

APT_ARGS=(
"-qq"
"-y"
)

# Installing nvidia docker to use deepvariant_gpu Docker image.
# (1) Install nvidia driver:
# https://github.com/NVIDIA/nvidia-docker/wiki/Frequently-Asked-Questions#how-do-i-install-the-nvidia-driver
sudo apt-get "${APT_ARGS[@]}" update
# From: https://docs.docker.com/install/linux/docker-ce/ubuntu/#set-up-the-repository
sudo apt-get "${APT_ARGS[@]}" install \
  apt-transport-https \
  ca-certificates \
  curl \
  gnupg-agent \
  software-properties-common

# See https://www.tensorflow.org/install/source#gpu for versions required.
if ! dpkg-query -W cuda-11-3; then
  echo "Installing CUDA..."
  UBUNTU_VERSION="2004"
  CUDA_DEB="cuda-repo-ubuntu${UBUNTU_VERSION}-11-3-local_11.3.0-465.19.01-1_amd64.deb"
  curl -O https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2004/x86_64/cuda-ubuntu2004.pin
  sudo mv cuda-ubuntu2004.pin /etc/apt/preferences.d/cuda-repository-pin-600
  curl -O https://developer.download.nvidia.com/compute/cuda/11.3.0/local_installers/"${CUDA_DEB}"
  sudo -H apt-key adv --fetch-keys "http://developer.download.nvidia.com/compute/cuda/repos/ubuntu${UBUNTU_VERSION}/x86_64/7fa2af80.pub"
  sudo -H dpkg -i "./${CUDA_DEB}"
  sudo -H apt-get update "${APT_ARGS[@]}" > /dev/null
  sudo -H apt-get install "${APT_ARGS[@]}" cuda
fi

echo "Checking for CUDNN..."
if [[ ! -e /usr/local/cuda-11/include/cudnn.h ]]; then
  echo "Installing CUDNN..."
  CUDNN_TAR_FILE="cudnn-11.3-linux-x64-v8.2.0.53.tgz"
  wget -q https://developer.download.nvidia.com/compute/redist/cudnn/v8.2.0/${CUDNN_TAR_FILE}
  tar -xzvf ${CUDNN_TAR_FILE}
  sudo cp -P cuda/include/cudnn.h /usr/local/cuda-11/include
  sudo cp -P cuda/lib64/libcudnn* /usr/local/cuda-11/lib64/
  sudo cp -P cuda/lib64/libcudnn* /usr/local/cuda-11/lib64/
  sudo chmod a+r /usr/local/cuda-11/lib64/libcudnn*
  sudo ldconfig
fi

# (2) Install Docker CE:
# https://docs.docker.com/engine/install/ubuntu/
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
sudo apt-key fingerprint 0EBFCD88
sudo add-apt-repository \
 "deb [arch=amd64] https://download.docker.com/linux/ubuntu \
 $(lsb_release -cs) \
 stable"
sudo apt-get "${APT_ARGS[@]}" update
sudo apt-get "${APT_ARGS[@]}" install docker-ce docker-ce-cli containerd.io

# (3) Install nvidia docker:
# https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html#installing-on-ubuntu-and-debian
# Add the package repositories
distribution=$(. /etc/os-release;echo "$ID$VERSION_ID")
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L "https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list" | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update && sudo apt-get install "${APT_ARGS[@]}" nvidia-docker2
sudo systemctl restart docker

#### Test nvidia-smi with the latest official CUDA image
sudo docker run --gpus 1 nvidia/cuda:11.3.0-base-ubuntu20.04 nvidia-smi
