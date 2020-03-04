#
# Script to enable temp monitoring from v2 via prometheus.
# copyright ian.dobbie@gmail.com 2020

#Script read temperatures from the remotes via Pyro (version 3.4)
#and then serves that information out using prometheus_client
#which provides http on port 8000

# imports

from Pyro.ext import remote_nons as r
import time
from prometheus_client import start_http_server, Gauge

#definitions of the Pyro object connections to be made
POBJS=[["cabinettemperature","ni","omxnano",7766],
 ["Cam1temperature","pyroCam","omxcam1",1840],
 ["Cam2temperature","pyroCam","omxcam2",1840],
 ["Cam3temperature","pyroCam","omxcam3",1840],
 ["Cam4temperature","pyroCam","omxcam4",1840]]


if __name__ == '__main__':
    
    # Start up the server to expose the metrics.
    start_http_server(8000)

    #initiallise pyro connections
    cons=[None]*len(POBJS)
    consTemps=[None]*len(POBJS)
    for i in range (len(POBJS)):
 #       print (i,POBJS[i])
        cons[i]=r.get_server_object(POBJS[i][1],POBJS[i][2],POBJS[i][3])
        consTemps[i]=Gauge(POBJS[i][0],POBJS[i][0])
    
    while True:
        # Ni function is getTemp
        consTemps[0].set(cons[0].getTemp())
		#Cameras use getTempearture
        for i in range (4):
            consTemps[i+1].set(cons[i+1].getTemperature())
		#Sleep as we don't need too much resolution.
        time.sleep(10)


