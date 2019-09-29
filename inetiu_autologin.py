#!/usr/bin/python3
#
# Author:       Julian Reith
# E-Mail:       julianreith@gmx.de
# Version:      0.9
# Last Updated: 2019-09-25
# 
# Description:
# This script extracts the Login-URL from a html response from the 
# BWI INetiU Wi-Fi Captive Login, fills it with your login credentials
# and logs your device into the Proxy.
# It is intended to be used on a Raspberry Pi or similar linux machine
# that runs python >= 3.5
# Its recommended to create a service, that runs this script on boot 
# and e.g. all 5min to prevent you from a logged out period.
# 
# Usage:
# - Enter your INetiU login credentials in the section below
# - Install python >= 3.5 on your machine who needs to be logged in
# - Run the script on that machine who needs to be logged in
#
# Known issues / work to do:
# - no logout function (not figured out howto do that now or if even possible?!)
# - no "MAX_DEVICES reached, do you want to delete oldest device" auto-accept function
#   -> this leads into a ~1min delay after login before the internet is reachable  
# - function checkLoginResult() not working proberly, because sometimes the
#   webpage call is to close after login. Maybe a deley would help.
#   -> results into a "... you are NOT logged in!" message but you are logged in.

### ENTER YOUR INetiU CREDENTIALS HERE ###
user = "user"
password = "password"

### DON'T CHANGE BELOW !!! ###

### IMPORTS ###
import os
import pathlib
import requests
import ssl
import sys
from requests import adapters
from urllib3 import poolmanager

### GLOBAL VARS ###
# urls:
try_url = "http://www.google.de"    # do not use https site
host_url = ""                       # e.g.: "https://inetiu4.bundeswehr.de:8443/portal"
portal_url = ""                     # URL you can use to manual log in your device with a webbrowser
                                    # e.g.: "https://inetiu4.bundeswehr.de:8443/portal/PortalSetup.action?portal=6101cf70-c869-11e8-8db0-005056817c86&sessionId=0a473a140000a59b5d8a79a1&action=cwa"
login_url = ""                      # e.g.: "https://inetiu4.bundeswehr.de:8443/portal/LoginSubmit.actioin?from=LOGIN"
terms_url = ""                      # e.g.: "https://inetiu4.bundeswehr.de:8443/portal/AupSubmit.action?from=AUP"

# url parts:
headers = {'User-Agent': 'Mozilla/5.0'}
sessionId = ""
portal = ""
action = "cwa"
token = ""
hidden_value = ""
hidden_value_len = 32

logged_in = 0
export_path = "/tmp/inetiu/"        # the last "/" is important! -> do not enter "/tmp/inetiu"

### CLASSES ###
class TLSAdapter(adapters.HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=False):
        """Create and initialize the urllib3 Poolmanager."""
        ctx = ssl.create_default_context()
        ctx.set_ciphers('DEFAULT@SECLEVEL=1')
        self.poolmanager = poolmanager.PoolManager(
            num_pools=connections,
            block=block,
            ssl_version=ssl.PROTOCOL_TLS,
            ssl_context=ctx)

### FUNCTIONS ###
def getLoginState(response):
    target = "<TITLE> Web Authentication Redirect</TITLE>"
    result = response.find(target)
    if result > 0:
        return 0
    else:
        return 1
  
def getPortalUrl(response):          # proceed only for Web Authentication Redirect response!!!
    target = "URL="
    targetend = "&redirect=" + try_url.replace("http://", "")
    url = response[response.find(target):response.find(targetend)].replace(target, "")
    storeSessionParams(url)
    url = host_url + "PortalSetup.action?portal=" + portal + "&sessionId=" + sessionId + "&action=" + action
    return url

def getLoginUrl():
    url = host_url + "LoginSubmit.action?from=LOGIN"
    return url

def getTermsUrl():
    url = host_url + "AupSubmit.action?from=AUP"
    return url

def getHiddenValue(response):
    target = "<input type=\"hidden\" name=\"token\" value=\""
    global hidden_value_len
    hidden_val = response[response.find(target)+len(target):response.find(target)+len(target)+hidden_value_len]
    return hidden_val
  
def storeSessionParams(url):
    pathlib.Path(export_path).mkdir(parents=True, exist_ok=True)
    # host_url
    target = "http"
    targetend = "gateway?sessionId="
    global host_url
    host_url = url[url.find(target):url.find(targetend)].replace(targetend, "")
    with open(export_path + "host_url", 'w+') as file:
        file.write(host_url)
    # sessionId:
    target = "sessionId="
    targetend = "&portal="
    global sessionId
    sessionId = url[url.find(target):url.find(targetend)].replace(target, "")
    with open(export_path + "sessionId", 'w+') as file:
        file.write(sessionId)
    # portal:
    target = "portal="
    targetend = "&action="
    global portal
    portal = url[url.find(target):url.find(targetend)].replace(target, "")
    with open(export_path + "portal", 'w+') as file:
        file.write(portal)
    # action:
    target = "action="
    targetend = "&token="
    global action
    action = url[url.find(target):url.find(targetend)].replace(target, "")
    with open(export_path + "action", 'w+') as file:
        file.write(action)
    # token:
    target = "token="
    targetend = len(url)
    global token
    token = url[url.find(target):targetend].replace(target, "")
    with open(export_path + "token", 'w+') as file:
        file.write(token)
   
def printSessionSummary():          # for debugging only!
    print("\n++++++++++++++++++++++++++++++++++++++++++++++")
    print("URLs:")
    print("try_url: " + try_url)
    print("host_url: " + host_url)
    print("portal_url: " + portal_url)
    print("terms_url: " + terms_url)
    print("\nSession Params:\n")
    print("sessionId: " + sessionId)
    print("portal: " + portal)
    print("action: " + action)
    print("token: " + token)
    print("hidden_value: " + hidden_value)
    print("++++++++++++++++++++++++++++++++++++++++++++++\n")
   
def checkLoginResult(response):
    target = "<title>Google</title>"
    result = response.find(target)
    if result > 0:
        print("DONE: You successfully logged in!")
    else:
        print("Something went wrong ... you are NOT logged in!")
    
   
### START OF SCRIPT ###
# create session:
session = requests.Session()
session.mount('https://', TLSAdapter())   # "dh key to small" fix
r = session.get(try_url)
response = r.text
logged_in = getLoginState(response)
if logged_in == 0:
    print("Login to INetiU Captive Portal ...")
    portal_url = getPortalUrl(response)
    print("Portal-URL for manual Login:\n" + portal_url)
    r = session.get(portal_url)
    hidden_value = getHiddenValue(r.text)
    
    # login
    print("send login data ...")
    login_url = getLoginUrl()
    payload_login = {'user.username':user,'user.password':password,'token':hidden_value,'portal':portal}
    r = session.post(login_url,headers=headers,data=payload_login)

    # accept terms:
    print("accept terms ...")
    terms_url = getTermsUrl()
    payload_terms = {'aupAccepted':'true','token':hidden_value}
    r = session.post(terms_url,headers=headers,data=payload_terms)
    
    # check result
    r = session.get(try_url)
    checkLoginResult(r.text)
    
    #printSessionSummary()              # for debugging only
else:
    print("DONE: You are already logged in! Nothing to do.")
    
