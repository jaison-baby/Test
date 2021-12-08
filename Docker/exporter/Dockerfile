# Step 1 select default OS image
FROM ubuntu:18.04


# # Step 2 tell what you want to do
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
  && apt-get install -y python3-pip python3-dev vim-tiny libatlas-base-dev gfortran nginx supervisor \
  && cd /usr/local/bin \
  && ln -s /usr/bin/python3 python \
  && pip3 install --upgrade pip
RUN pip3 install uwsgi


# # Step 3 Configure a software
# # Defining working directory
WORKDIR /usr/src/app


# # Copy everything which is present in my docker directory to working (/app)
COPY Exporter/requirements.txt /usr/src/app

RUN pip3 install -r requirements.txt


# Exposing an internal port
# EXPOSE 5001
EXPOSE 5000

