FROM ubuntu:20.04
RUN apt-get -y update && apt-get upgrade -y
RUN apt-get -y install gcc valgrind
RUN apt-get -y install openjdk-17-jdk
VOLUME /submissions
