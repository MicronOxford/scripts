Temperature Monitoring scripts for Micron
=========================================

A set of scripts and config files for monitoring tempearture within
micron rooms and facilities. 

v2-temp-monitor.py
------------------

A simple python 2 script that uses Pyro3.4 to connect to the remote
computers and report back the cabinet tempearture as well as the
camera temperatures for the cameras. It then uses prometheus_client to
share that information via a http server on omxmaster:8000.

