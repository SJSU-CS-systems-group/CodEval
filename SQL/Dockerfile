# Docker File for SQL executions
# Use the official Ubuntu 20.04 as the base image
FROM ubuntu:20.04

# Set environment variables to non-interactive mode for MySQL installation
ENV DEBIAN_FRONTEND=noninteractive

# Install MySQL Server
RUN apt-get update && \
    apt-get install -y mysql-server && \
    apt-get install -y software-properties-common && \
    add-apt-repository universe && \
    apt-get update && \
    apt-get install -y gcc valgrind

# Expose the MySQL port (default is 3306)
EXPOSE 3306

# Install MySQL client to interact with MySQL server
RUN apt-get install -y mysql-client

# Start MySQL when the container starts
#CMD ["mysqld"]
CMD ["sh", "-c", "service mysql start && sleep 5 && mysqld"]

# Create the 'dummy' MySQL user during container initialization

RUN service mysql start && \
    mysql -e "CREATE DATABASE IF NOT EXISTS dummy;" && \
    mysql -e "CREATE USER 'dummy'@'%' IDENTIFIED BY 'dummy';" && \
    mysql -e "GRANT ALL PRIVILEGES ON dummy.* TO 'dummy'@'%';" && \
    mysql -e "FLUSH PRIVILEGES;"


# Set the environment variables for MySQL user, password, and default database
ENV MYSQL_USER=dummy
ENV MYSQL_PASSWORD=dummy
ENV MYSQL_DATABASE=dummy