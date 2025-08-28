FROM ubuntu:24.04
RUN apt-get -y update && apt-get upgrade -y
RUN apt-get -y install gcc valgrind
RUN apt-get -y install openjdk-21-jdk
RUN apt-get -y install gawk

# Install maven 3.8.6 for compatibility with jdk 17
RUN apt-get -y install wget
RUN wget https://archive.apache.org/dist/maven/maven-3/3.9.11/binaries/apache-maven-3.9.11-bin.tar.gz
RUN tar xzvf apache-maven-3.9.11-bin.tar.gz -C/opt/
ENV PATH="${PATH}:/opt/apache-maven-3.9.11/bin:/root/.local/bin"

RUN apt-get -y install sudo pipx

COPY . /codeval
WORKDIR /submissions
RUN pipx install /codeval --force
