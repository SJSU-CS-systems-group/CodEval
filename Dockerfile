FROM ubuntu:24.04
RUN apt-get -y update && apt-get upgrade -y
RUN apt-get -y install gcc valgrind
RUN apt-get -y install openjdk-21-jdk
RUN apt-get -y install gawk
RUN apt-get -y install git
RUN apt-get -y install iproute2
RUN apt-get -y install  g++-14
RUN update-alternatives --install /usr/bin/g++ g++ /usr/bin/g++-14 100
RUN update-alternatives --install /usr/bin/c++ c++ /usr/bin/g++-14 100

# Go toolchain for Go assignments (Ubuntu 24.04 ships Go 1.22)
RUN apt-get -y install golang-go

# Install docker to test tofu
RUN apt-get -y install wget docker.io
RUN wget -qO- https://get.opentofu.org/install-opentofu.sh | sh -s -- --install-method deb


# Install maven 3.8.6 for compatibility with jdk 17
RUN wget https://archive.apache.org/dist/maven/maven-3/3.9.11/binaries/apache-maven-3.9.11-bin.tar.gz
RUN tar xzvf apache-maven-3.9.11-bin.tar.gz -C/opt/
ENV PATH="${PATH}:/opt/apache-maven-3.9.11/bin:/root/.local/bin"

RUN apt-get -y install sudo pipx

# Setuid wrapper that lets an unprivileged evaluation start dockerd (see the
# comment in start-dockerd.c). Only useful when the container is --privileged.
COPY start-dockerd.c /tmp/start-dockerd.c
RUN gcc -O2 -Wall -o /usr/local/bin/start-dockerd /tmp/start-dockerd.c \
    && chmod 4755 /usr/local/bin/start-dockerd && rm /tmp/start-dockerd.c

COPY . /codeval
WORKDIR /submissions
# Install outside /root so the evaluation can run as the host user (-u in the
# codeval.ini run command). /usr/local/bin is already on PATH.
RUN PIPX_HOME=/opt/pipx PIPX_BIN_DIR=/usr/local/bin pipx install /codeval --force
