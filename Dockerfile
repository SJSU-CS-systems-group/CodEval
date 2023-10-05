FROM ubuntu:22.04
RUN apt-get -y update && apt-get upgrade -y
RUN apt-get -y install gcc valgrind
RUN apt-get -y install openjdk-17-jdk
RUN apt-get -y install gawk

# Install maven 3.8.6 for compatibility with jdk 17
RUN apt-get -y install wget
RUN wget https://archive.apache.org/dist/maven/maven-3/3.8.6/binaries/apache-maven-3.8.6-bin.tar.gz
RUN tar xzvf apache-maven-3.8.6-bin.tar.gz -C/opt/
ENV PATH="${PATH}:/opt/apache-maven-3.8.6/bin"

RUN apt-get -y install sudo

VOLUME ["/root/.m2","/submissions"]
