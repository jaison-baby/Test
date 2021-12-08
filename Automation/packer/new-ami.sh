#!/bin/bash

#python
sudo yum -y install git
sudo yum -y install python38 python38-pip 
sudo pip-3.8 install certifi==2020.12.5
sudo pip-3.8 install chardet==4.0.0
sudo pip-3.8 install idna==2.10
sudo pip-3.8 install prometheus-client==0.10.1
sudo pip-3.8 install requests==2.25.1
sudo pip-3.8 install urllib3==1.26.4
sudo pip-3.8 install Werkzeug==1.0.1

#supervisor

sudo pip-3.8  install supervisor
#sudo /usr/local/bin/echo_supervisord_conf
#sudo /usr/local/bin/echo_supervisord_conf > /etc/supervisord.conf
#cd /tmp 
#sudo cp supervisord.conf /etc/
#sudo echo 'files = supervisord.d/*.ini' >> /etc/supervisord.conf 
#sudo mkdir -p /etc/supervisord.d
#cd /tmp
#sudo cp exporter.ini /etc/supervisord.d/

cd /tmp
sudo cp supervisord.conf /etc/
sudo cp -pr supervisord.d/   /etc/
sudo cp exporter.ini /etc/supervisord.d/
sudo chmod 755 supervisord
sudo cp supervisord /etc/init.d/


#node exporter
cd /tmp
sudo yum -y install wget
sudo wget https://github.com/prometheus/node_exporter/releases/download/v0.17.0/node_exporter-0.17.0.linux-amd64.tar.gz

sudo tar -xvf node_exporter-0.17.0.linux-amd64.tar.gz

sudo cd /tmp/node_exporter-0.17.0.linux-amd64/

sudo cp /tmp/node_exporter-0.17.0.linux-amd64/node_exporter /usr/local/bin/
sudo chmod 755 node-exporter
sudo cp /tmp/node-exporter /etc/init.d/

