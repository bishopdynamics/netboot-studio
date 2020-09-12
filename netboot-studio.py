#!/usr/local/bin/python3
# Netboot Studio service

#    This file is part of Netboot Studio, a system for managing netboot clients
#    Copyright (C) 2019 James Bishop (jamesbishop2006@gmail.com)

# info about ipxe: http://ipxe.org/

# ignore rules:
#   docstring
#   snakecasevars
#   too-broad-exception
#   line-too-long
#   too-many-branches
#   too-many-statements
#   global-statement
#   too-many-public-methods
#   too-many-lines
#   too-many-nested-blocks
#   toddos (annotations linter handling this)
#pylint: disable=C0111,C0103,W0703,C0301,R0912,R0915,W0603,R0904,C0302,R1702,W0511

import time
import os
import sys
import json
import socket
import uuid
import multiprocessing
import signal
import asyncio


# for experiments in iso file upload
# import cgi
# import shutil


from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib import parse
from collections import OrderedDict
import websockets
import yaml

# import CreateImage and CreatUnattended functions
import createimage
import createunattended

########### Hardcoded static vars
# TODO - dont hardcode these
ADMIN_USER = 'admin'
ADMIN_PASSWORD = 'admin'
HTTP_PORT = 6161
WEBSOCKET_PORT = 6162
LOCAL_STORAGE_FOLDER = '/opt/tftp-root'
HTTP_SERVER = 'http://192.168.1.188'
############## The rest of the vars

ISO_FOLDER = '%s/iso' % LOCAL_STORAGE_FOLDER
IMAGES_FOLDER = '%s/images' % LOCAL_STORAGE_FOLDER
UNATTENDED_FOLDER = '%s/unattended' % LOCAL_STORAGE_FOLDER
JOB_STATUS_FOLDER = '/tmp/netboot-studio-jobs/'
CLIENT_LIST_FILE = '%s/client-list.json' % LOCAL_STORAGE_FOLDER
WIZARD_DATA_FILE = 'wizard-data.yaml'
LOG_FILE = '/tmp/netboot-studio.log'
# will read from file VERSION
VERSION = ''

# we dont need to set hostname
HOST_NAME = ''

# ttl in seconds. 30m = 1800
AUTH_TOKEN_TTL = 1800

# mapping image_type to actual functions
CREATE_IMAGE_FUNCTIONS = {
    'windows' : createimage.CreateImage_Windows,
    'debian-netboot-web' : createimage.CreateImage_DebianNetboot,
    'ubuntu-netboot-web' : createimage.CreateImage_UbuntuNetboot,
    'ubuntu-desktop-live' : createimage.CreateImage_UbuntuLive,
    'vmware-6x' : createimage.CreateImage_VMware,
    'gparted-live' : createimage.CreateImage_GParted,
    'custom' : createimage.CreateImage_Custom
}

CREATE_UNATTENDED_FUNCTIONS = {
    'windows' : createunattended.CreateUnattended_Windows,
    'debian' : createunattended.CreateUnattended_Debian,
    'vmware' : createunattended.CreateUnattended_VMware
}

# files within an image folder, which we support editing
SUPPORTED_FILES = {
    'netboot.ipxe',
    'netboot-unattended.ipxe',
    'winpeshl.ini',
    'startnet.cmd',
    'mount.cmd',
    'netboot.cfg',
    'netboot-unattended.cfg'
}

# metadata keys we show in ui
IMAGE_METADATA_DISPLAY_KEYS = {
    'source_iso',
    'image_type',
    'created',
    'description'
}

# we only serve real files for the following
WEB_RESOURCE_WHITELIST = {
    '/index.html',
    '/lib/netboot-studio.js',
    '/lib/netboot-studio-wizard.js',
    '/lib/netboot-studio-wizard-data.js',
    '/lib/codemirror-shell.js',
    '/lib/codemirror-theme-material.css',
    '/lib/codemirror.css',
    '/lib/codemirror.js',
    '/lib/material-icons.css',
    '/lib/material-icons.ttf',
    '/lib/materialize.min.css',
    '/lib/materialize.min.js'
}

# globals for storing our lists. Note some are lists, some are dicts
CLIENT_LIST = OrderedDict()
IMAGE_LIST = OrderedDict()
UNATTENDED_LIST = list()
ISO_LIST = list()
JOB_LIST = dict()
RUNNING_JOBS = dict()
AUTH_TOKEN_LIST = dict()

# store outgoing messages here, async check it
MESSAGE_OUTBOX = dict()

BUILT_IN_IMAGE_DEFAULT_NAME = 'standby-loop'
BUILT_IN_IMAGE_DEFAULT = '''#!ipxe
    # stage2 standby loop
    #  Part of Netboot Studio, a system for managing netboot clients
    #  Copyright (C) 2019 James Bishop (jamesbishop2006@gmail.com)

    # milliseconds, time to wait to check for new instructions
    set delay-time 10000

    # Colour index  Basic ANSI colour
    # 0 0 (black)
    # 1 1 (red)
    # 2 2 (green)
    # 3 3 (yellow)
    # 4 15 (blue or transparent)1)
    # 5 5 (magenta)
    # 6 6 (cyan)
    # 7 7 (white)
    # 9 9 (default)2)
    set color-fg 1
    set color-bg 4
    cpair --foreground ${color-fg} --background ${color-bg} 0
    cpair --foreground ${color-fg} --background ${color-bg} 1

    console --picture http://${next-server}/boot-images/standby.png ||
    # need four clear lines to account for header
    echo
    echo
    echo
    echo
    echo This client is in standby loop, goto http://${netboot-server}/ to configure
    echo
    echo mac: ${mac}, ip: ${ip}, platform: ${platform}
    echo arch: ${buildarch}, manufacturer: ${manufacturer}
    echo
    echo will check for new instructions in ${delay-time} milliseconds

    prompt --key 0x02 --timeout ${delay-time} Press Ctrl-B for the iPXE command line... && goto shell ||
    console --picture http://${next-server}/boot-images/loading.png ||
    echo
    echo
    echo
    echo
    sleep 1
    imgexec ${stage-2-url} ||failed

    :failed
    echo Something failed, hopefully errors are printed above this
    prompt Press any key to reboot ||
    goto :reboot

    :shell
    console
    shell

    :reboot
    echo rebooting
    reboot
    '''

BUILT_IN_UNATTENDED_DEFAULT_NAME = 'blank.cfg'
BUILT_IN_UNATTENDED_DEFAULT = ''

# this is what we will send if anything else fails
FALLBACK_EMPTY = ''

# for WebSocket server
WEBSOCKET_CLIENTS = set() # a set cannot have duplicates. woot.
WEBSOCKET_LOOP = None
WEBSOCKET_STOP = None

# for http server
HTTP_PROCESS = None
HTTP_INSTANCE = None


# var to signal end of looping
KEEP_LOOPING = True

def clearlogfile():
    timestamp = time.asctime()
    with open(LOG_FILE, 'wt', encoding='utf-8') as f:
        f.write('%s - New Log File\n' % timestamp)

def logmessage(msg):
    timestamp = time.asctime()
    print('%s - %s' % (timestamp, msg))
    with open(LOG_FILE, 'at', encoding='utf-8') as f:
        f.write('%s - %s\n' % (timestamp, msg))

def getLog():
    content = ''
    with open(LOG_FILE, 'r') as f:
        content = f.read()
    return content

# HTTP Server Handler
class NSHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()

    def log_message(self, format, *args):
        # override to hide messages from http server itself.
        # to see them again, just comment out this method
        return

    def do_GET(self):
        clean_url = parse.urlparse(self.path).path
        # if clean_url != '/favicon.ico':
        #     logmessage('Handling GET request: %s' % self.path)
        if clean_url == '/stage2.ipxe':
            self.get_stage2(self.path)
        elif clean_url in ('/unattended.cfg', '/unattend.xml', '/preseed.cfg'):
            self.get_unattended(self.path)
        elif clean_url == '/login':
            self.get_loginpage()
        else:
            # anything not handled by above, must be part of webui
            self.get_web(self.path)

    def do_POST(self):
        # all POST requests require auth_token (except /auth)
        clean_url = parse.urlparse(self.path).path
        if clean_url == '/auth':
            self.post_auth()
        elif 'auth_token' in self.headers:
            if ValidateAuthToken(self.headers['auth_token']):
                if clean_url != '/getjobstatus':
                    logmessage('Handling authorized POST request from: [%s] for: %s' % (self.client_address[0], self.path))
                if clean_url == '/saveimagefile':
                    self.post_saveimagefile()
                elif clean_url == '/saveunattended':
                    self.post_saveunattended()
                elif clean_url == '/newunattended':
                    # makes new empty unattended file
                    self.post_newunattended()
                elif clean_url == '/createunattended':
                    # generates a full unattended file with data from wizard
                    self.post_createunattended()
                elif clean_url == '/editclient':
                    self.post_editclient()
                elif clean_url == '/getimagefile':
                    self.post_getimagefile(self.path)
                elif clean_url == '/getunattended':
                    self.post_getunattended(self.path)
                elif clean_url == '/clients':
                    self.post_clients()
                elif clean_url == '/images':
                    self.post_images()
                elif clean_url == '/unattendeds':
                    self.post_unattendeds()
                elif clean_url == '/isos':
                    self.post_isos()
                elif clean_url == '/uploadiso':
                    self.post_uploadiso()
                elif clean_url == '/createimage':
                    self.post_createimage()
                elif clean_url == '/getjobstatus':
                    self.post_getjobstatus()
                elif clean_url == '/wizard-data.json':
                    self.post_wizarddata_json()
                elif clean_url == '/getlog':
                    self.post_getlog()
                else:
                    logmessage('Got a POST request we cannot handle: %s' % clean_url)
                    self.send_response(404)
            else:
                logmessage('Refusing POST request for %s with invalid auth_token' % clean_url)
                self.send_response(404)
        else:
            logmessage('Refusing POST request missing auth_token in header')
            self.send_response(404)

    def post_saveimagefile(self):
        # /saveimagefile?imagename=my-image&filename=netboot.ipxe
        content_length = int(self.headers['Content-Length'])
        imagefile_content = self.rfile.read(content_length)
        urlparams = dict(parse.parse_qsl(parse.urlsplit(self.path).query))
        client_ipaddress = self.client_address[0]
        if 'filename' in urlparams.keys() and 'imagename' in urlparams.keys():
            imagefile_name = urlparams['filename']
            image_name = urlparams['imagename']
            if image_name == BUILT_IN_IMAGE_DEFAULT_NAME:
                logmessage('Request for /saveimagefile for read-only built-in image')
                self.send_response(400)
                logmessage('Refused to save changes')
                return
            imagefile_path = '%s/%s/%s' % (IMAGES_FOLDER, image_name, imagefile_name)
            logmessage('Saving changes to %s' % imagefile_path)
            try:
                with open(imagefile_path, 'wt', encoding='utf-8') as f:
                    f.write(imagefile_content.decode("utf-8"))
                self.send_response(200)
                logmessage('Successfully saved changes to %s' % imagefile_path)
            except Exception as e:
                logmessage('Unexpected exception while writing to file: %s' % e)
                self.send_response(500)
                logmessage('Failed to save changes to %s' % imagefile_path)
        else:
            logmessage('Request from %s for /saveimagefile missing imagename or filename urlparam' % (client_ipaddress))
            self.send_response(400)
            logmessage('Failed to save changes')
        self.end_headers()

    def post_saveunattended(self):
        # /saveunattended?unattended=debian-nogui.cfg
        content_length = int(self.headers['Content-Length'])
        unattended_content = self.rfile.read(content_length)
        urlparams = dict(parse.parse_qsl(parse.urlsplit(self.path).query))
        client_ipaddress = self.client_address[0]
        if 'unattended' in urlparams.keys():
            unattended_name = urlparams['unattended']
            if unattended_name == BUILT_IN_UNATTENDED_DEFAULT_NAME:
                logmessage('Request for /saveunattended for read-only built-in file')
                self.send_response(400)
                logmessage('Refused to save changes')
                return
            unattended_path = '%s/%s' % (UNATTENDED_FOLDER, unattended_name)
            logmessage('Saving changes to %s' % unattended_path)
            try:
                with open(unattended_path, 'wt', encoding='utf-8') as f:
                    f.write(unattended_content.decode("utf-8"))
                self.send_response(200)
                logmessage('Successfully saved changes to %s' % unattended_path)
            except Exception as e:
                logmessage('Unexpected exception while writing unattended to file: %s' % e)
                self.send_response(500)
                logmessage('Failed to saved changes to %s' % unattended_path)
        else:
            logmessage('Request from %s for /saveunattended missing unattended urlparam' % (client_ipaddress))
            self.send_response(400)
            logmessage('Failed to save changes to unattended file')
        self.end_headers()

    def post_newunattended(self):
        # /newunattended?unattended=debian-xfce.cfg
        unattended_content = ''
        urlparams = dict(parse.parse_qsl(parse.urlsplit(self.path).query))
        client_ipaddress = self.client_address[0]
        if 'unattended' in urlparams.keys():
            unattended_name = urlparams['unattended']
            if unattended_name == BUILT_IN_UNATTENDED_DEFAULT_NAME:
                logmessage('tried to create new unattended file with name matching built-in file')
                self.send_response(400)
                logmessage('Refused to create unattended file')
                return
            unattended_path = '%s/%s' % (UNATTENDED_FOLDER, unattended_name)
            logmessage('Creating new unattended file: %s' % unattended_path)
            try:
                with open(unattended_path, 'wt', encoding='utf-8') as f:
                    f.write(unattended_content)
                self.send_response(200)
                logmessage('Successfully created %s' % unattended_path)
            except Exception as e:
                logmessage('Unexpected exception while creating unattended file: %s' % e)
                self.send_response(500)
                logmessage('Failed to create %s' % unattended_path)
        else:
            logmessage('Request from %s for /newunattended missing unattended urlparam' % (client_ipaddress))
            self.send_response(400)
            logmessage('Failed to create unattended file')
        self.end_headers()
        RefreshFileLists()

    def post_createunattended(self):
        # endpoint is /createunattended
        content_length = int(self.headers['Content-Length'])
        content = self.rfile.read(content_length)
        urlparams = json.loads(content.decode('UTF-8'))
        client_ipaddress = self.client_address[0]
        if 'os_type' in urlparams.keys():
            CreateJob_Unattended(urlparams)
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
        else:
            logmessage('Malformed request from %s for /createunattended' % (client_ipaddress))
            self.send_response(400)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()

    def post_auth(self):
        # /auth
        content_length = int(self.headers['Content-Length'])
        request_content = json.loads(self.rfile.read(content_length).decode("utf-8"))
        client_ipaddress = self.client_address[0]
        if 'user' in request_content and 'password' in request_content:
            # user login request
            if request_content['user'] == ADMIN_USER:
                if request_content['password'] == ADMIN_PASSWORD:
                    new_token = GenerateAuthToken()
                    response_content = '{"auth_token": "%s"}' % new_token
                    self.send_response(200)
                    self.send_header('Content-type', 'text/json')
                    self.end_headers()
                    self.wfile.write(bytes(response_content, 'UTF-8'))
                    logmessage('Successful login request from client: %s' % client_ipaddress)
                    return
        elif 'auth_token' in request_content:
            # renew token request
            if ValidateAuthToken(request_content['auth_token']):
                new_token = GenerateAuthToken()
                response_content = '{"auth_token": "%s"}' % new_token
                self.send_response(200)
                self.send_header('Content-type', 'text/json')
                self.end_headers()
                self.wfile.write(bytes(response_content, 'UTF-8'))
                logmessage('Successfully renewed token for client: %s' % client_ipaddress)
                return
        # if we got here, auth failed
        self.send_response(401)
        self.end_headers()
        logmessage('Refused token renew request from: %s' % client_ipaddress)

    def post_editclient(self):
        # endpoint is /editclient
        # here we assume only one urlparam of {image, unattended, do_unattended}
        # we have no plans to support more than one in the same request
        content_length = int(self.headers['Content-Length'])
        content = self.rfile.read(content_length)
        urlparams = json.loads(content.decode('UTF-8'))
        client_ipaddress = self.client_address[0]
        if 'macaddress' in urlparams.keys():
            client_macaddress = '%s' % urlparams['macaddress']
            if client_macaddress in CLIENT_LIST:
                if 'image' in urlparams.keys():
                    client_image = '%s' % urlparams['image']
                    logmessage('setting image for %s to: %s' % (client_macaddress, client_image))
                    CLIENT_LIST[client_macaddress]['image'] = client_image
                    SaveClientList()
                    self.post_clients()
                elif 'unattended' in urlparams.keys():
                    client_unattended = '%s' % urlparams['unattended']
                    logmessage('setting unattended for %s to: %s' % (client_macaddress, client_unattended))
                    CLIENT_LIST[client_macaddress]['unattended'] = client_unattended
                    SaveClientList()
                    self.post_clients()
                elif 'do_unattended' in urlparams.keys():
                    client_do_unattended = '%s' % urlparams['do_unattended']
                    logmessage('setting do_unattended for %s to: %s' % (client_macaddress, client_do_unattended))
                    if client_do_unattended == 'True':
                        CLIENT_LIST[client_macaddress]['do_unattended'] = True
                    else:
                        CLIENT_LIST[client_macaddress]['do_unattended'] = False
                    SaveClientList()
                    self.post_clients()
                else:
                    logmessage('Request from %s for /editclient missing appropriate data in content' % (client_ipaddress))
                    self.send_response(400)
                    self.send_header('Content-type', 'text/plain')
                    self.end_headers()
            else:
                logmessage('Tried to edit property of [%s] but not in client_list' % client_macaddress)
                self.send_response(400)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                return
        else:
            logmessage('Request from %s for /editclient missing macaddress urlparam' % (client_ipaddress))
            self.send_response(400)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()

    def post_createimage(self):
        # endpoint is /createimage
        content_length = int(self.headers['Content-Length'])
        content = self.rfile.read(content_length)
        urlparams = json.loads(content.decode('UTF-8'))
        client_ipaddress = self.client_address[0]
        if 'image_type' in urlparams.keys():
            CreateJob_NewImage(urlparams)
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
        else:
            logmessage('Malformed request from %s for /createimage' % (client_ipaddress))
            self.send_response(400)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()

    def post_getimagefile(self, fullurl):
        # endpoint is /getimagefile?imagename=fubar-v42&filename=netboot.ipxe
        # find given image, file, and reply with it's content
        urlparams = dict(parse.parse_qsl(parse.urlsplit(fullurl).query))
        client_ipaddress = self.client_address[0]
        if 'imagename' in urlparams.keys() and 'filename' in urlparams.keys():
            image_name = urlparams['imagename']
            file_name = urlparams['filename']
            if file_name in SUPPORTED_FILES:
                image_file_path = "%s/%s/%s" % (IMAGES_FOLDER, image_name, file_name)
                try:
                    if image_name == BUILT_IN_IMAGE_DEFAULT_NAME:
                        content = BUILT_IN_IMAGE_DEFAULT
                    else:
                        with open(image_file_path, 'r') as _file:
                            content = _file.read()
                    logmessage('Providing imagefile to editor: %s' % (image_file_path))
                    self.send_response(200)
                    self.send_header('Content-type', 'text/plain')
                    self.end_headers()
                    self.wfile.write(bytes(content, 'UTF-8'))
                except FileNotFoundError:
                    logmessage('Failed to find imagefile: %s' % image_file_path)
                    self.send_response(404)
                    self.send_header('Content-type', 'text/plain')
                    self.end_headers()
                except Exception as e:
                    logmessage('Unexpected exception while reading imagefile: %s' % e)
                    self.send_response(500)
                    self.send_header('Content-type', 'text/plain')
                    self.end_headers()
            else:
                logmessage('Refusing request for unsupported imagefile: %s' % file_name)
                self.send_response(400)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
        else:
            logmessage('Request from %s for /getimagefile missing imagename or filename urlparam' % (client_ipaddress))
            self.send_response(400)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()

    def post_getjobstatus(self):
        # endpoint is /getjobstatus
        # read from files in /tmp/netboot-studio/ to create dict of job status and progress info
        # because the ui is the only thing that cares about status,
        #   this method is responsible for doing any deletion of jobs as needed
        # This endpoint ALWAYS returns status 200, the content might just be empty dict if there are no jobs
        content = dict()
        # do this to avoid having the list change while iterating over it
        local_job_list = dict(JOB_LIST)

        if not os.path.isdir(JOB_STATUS_FOLDER):
            logmessage('job status folder not found, creating empty folder')
            os.mkdir(JOB_STATUS_FOLDER)
        for job_id in local_job_list:
            job_folder = '%s/%s' % (JOB_STATUS_FOLDER, job_id)
            job_status = 'none'
            job_progress = 0
            job_name = 'unknown'
            if os.path.isdir(job_folder):
                if os.path.exists('%s/progress' % job_folder):
                    try:
                        if job_id in RUNNING_JOBS:
                            if RUNNING_JOBS[job_id].is_alive():
                                job_status = 'running'
                            else:
                                job_status = 'done'
                        else:
                            job_status = 'queued'
                        with open('%s/progress' % job_folder, 'r') as _file:
                            data = _file.read().rstrip()
                            if data == '':
                                job_progress = 0
                            else:
                                job_progress = int(data)
                        with open('%s/name' % job_folder, 'r') as _file:
                            job_name = _file.read().rstrip()
                    except Exception as e:
                        logmessage('Unexpected exception while reading job status files: %s' % e)
                    content[job_id] = dict()
                    content[job_id]['status'] = job_status
                    content[job_id]['progress'] = job_progress
                    content[job_id]['name'] = job_name

                    # delete job if it is done
                    if job_status == 'done':
                        logmessage('flushing completed job %s' % job_id)
                        del JOB_LIST[job_id]
                        del RUNNING_JOBS[job_id]

                else:
                    logmessage('job missing status or progress file for job_id: %s' % job_id)
            else:
                logmessage('job status folder does not exist for job_id: %s' % job_id)
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(bytes(json.dumps(content), 'UTF-8'))

    def post_getunattended(self, fullurl):
        # endpoint is /getunattended
        # find given unattended file and reply with it's content
        urlparams = dict(parse.parse_qsl(parse.urlsplit(fullurl).query))
        client_ipaddress = self.client_address[0]
        if 'unattended' in urlparams.keys():
            unattended_name = urlparams['unattended']
            unattended_path = "%s/%s" % (UNATTENDED_FOLDER, unattended_name)
            try:
                if unattended_name == BUILT_IN_UNATTENDED_DEFAULT_NAME:
                    content = BUILT_IN_UNATTENDED_DEFAULT
                else:
                    with open(unattended_path, 'r') as unattended_file:
                        content = unattended_file.read()
                logmessage('Providing unattended to editor: %s' % (unattended_path))
                self.send_response(200)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(bytes(content, 'UTF-8'))
            except FileNotFoundError:
                self.send_response(400)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                logmessage('Failed to find unattended file: %s' % unattended_path)
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                logmessage('Unexpected exception while reading unattended file: %s' % e)
        else:
            logmessage('Request from %s for /getunattended missing unattended urlparam' % (client_ipaddress))
            self.send_response(400)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()

    def post_clients(self):
        # endpoint is /clients
        # return a json list of clients
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(bytes(json.dumps(CLIENT_LIST), 'UTF-8'))

    def post_getlog(self):
        # endpoint is /getlog
        # return current content of logfile
        content = getLog()
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(bytes(content, 'UTF-8'))
        # SendWebsocketMessage('got log')

    def post_images(self):
        # endpoint is /images
        # respond with json string, list of images
        RefreshFileLists()
        file_list = IMAGE_LIST
        try:
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(bytes(json.dumps(file_list), 'UTF-8'))
        except Exception as e:
            logmessage('Unexpected exception while handling request for /images: %s' % e)
            self.send_response(500)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()

    def post_unattendeds(self):
        # endpoint is /unattendeds
        # respond with json string, list of unattendeds
        RefreshFileLists()
        file_list = UNATTENDED_LIST
        try:
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(bytes(json.dumps(file_list), 'UTF-8'))
        except Exception as e:
            logmessage('Unexpected exception while handling request for /unattendeds: %s' % e)
            self.send_response(500)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()

    def post_isos(self):
        # endpoint is /isos
        # respond with json string, list of iso files
        RefreshFileLists()
        file_list = ISO_LIST
        try:
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(bytes(json.dumps(file_list), 'UTF-8'))
        except Exception as e:
            logmessage('Unexpected exception while handling request for /isos: %s' % e)
            self.send_response(500)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()

    def post_uploadiso(self):
        try:
            file_name = self.headers['file_name']
            file_full_path = '%s/%s' % (ISO_FOLDER, file_name)
            logmessage('handling a file upload for %s' % file_name)

            # form = cgi.FieldStorage(
            #     fp=self.rfile,
            #     headers=self.headers,
            #     environ={
            #         "REQUEST_METHOD": "POST",
            #         "CONTENT_TYPE":   self.headers['Content-Type']
            #     })

            # Don't overwrite files
            if os.path.exists(file_full_path):
                logmessage('refusing to overwrite existing file')
                self.send_response(409, 'Conflict')
                self.end_headers()
                reply_body = '"%s" already exists\n' % file_name
                self.wfile.write(reply_body.encode('utf-8'))
                return

            file_length = int(self.headers['Content-Length'])
            with open(file_full_path, 'wb') as output_file:
                output_file.write(self.rfile.read(file_length))
            # with open(file_full_path, 'wb') as output_file:
            #     shutil.copyfileobj(form["file"].file, output_file)
            self.send_response(201, 'Created')
            self.end_headers()
            reply_body = 'Saved "%s"\n' % file_name
            self.wfile.write(reply_body.encode('utf-8'))
            logmessage('file upload successfully')
        except Exception as e:
            logmessage('Unexpected exception while handling request for /uploadiso: %s' % e)

    def get_stage2(self, fullurl):
        # endpoint is /stage2.ipxe
        urlparams = dict(parse.parse_qsl(parse.urlsplit(fullurl).query))
        client_ipaddress = self.client_address[0]
        try:
            client_hostname = socket.gethostbyaddr(client_ipaddress)[0]
        except socket.herror:
            client_hostname = 'unknown'
        if 'macaddress' in urlparams.keys():
            client_macaddress = urlparams['macaddress']
        else:
            logmessage('macaddress urlparam not specified, all we have is ip address: %s' % client_ipaddress)
            logmessage('stage2.ipxe requires macaddress, cannot do anything ')
            self.respond_fallback_image()
            return
        # ip, mac, arch, platform, manufacturer
        if 'arch' in urlparams.keys():
            client_arch = urlparams['arch']
        else:
            client_arch = 'none'

        if 'platform' in urlparams.keys():
            client_platform = urlparams['platform']
        else:
            client_platform = 'none'

        if 'manufacturer' in urlparams.keys():
            client_manufacturer = urlparams['manufacturer']
        else:
            client_manufacturer = 'none'

        if client_macaddress not in CLIENT_LIST:
            # if no entry exists, create a clean default entry
            logmessage('Creating fresh entry for new client: %s' % client_macaddress)
            CLIENT_LIST[client_macaddress] = {
                'image': BUILT_IN_IMAGE_DEFAULT_NAME,
                'unattended': BUILT_IN_UNATTENDED_DEFAULT_NAME,
                'ipaddress': client_ipaddress,
                'arch': client_arch,
                'platform': client_platform,
                'manufacturer': client_manufacturer,
                'hostname': client_hostname,
                'do_unattended': False
                }
            SaveClientList()
        else:
            # always update the hostname
            CLIENT_LIST[client_macaddress]['hostname'] = client_hostname
            # if entry exists without script key, make a default one
            if 'image' not in CLIENT_LIST[client_macaddress].keys():
                CLIENT_LIST[client_macaddress]['image'] = BUILT_IN_IMAGE_DEFAULT_NAME
            # for remaining possible urlparams, if they were provided then update entry in client_list
            if client_arch != 'none':
                CLIENT_LIST[client_macaddress]['arch'] = client_arch
            if client_ipaddress != 'none':
                CLIENT_LIST[client_macaddress]['ipaddress'] = client_ipaddress
            if client_platform != 'none':
                CLIENT_LIST[client_macaddress]['platform'] = client_platform
            if client_manufacturer != 'none':
                CLIENT_LIST[client_macaddress]['manufacturer'] = client_manufacturer
        image_bootscript = 'netboot.ipxe'
        if CLIENT_LIST[client_macaddress]['do_unattended']:
            if IMAGE_LIST[CLIENT_LIST[client_macaddress]['image']]['has_netboot-unattended.ipxe']:
                logmessage('do_unattended is true, using netboot-unattended.ipxe')
                image_bootscript = 'netboot-unattended.ipxe'
            else:
                logmessage('do_unattended is true, but has_netboot-unattended.ipxe is false')
        else:
            logmessage('do_unattended is false, using netboot.ipxe')
        image_bootscript_path = "%s/%s/%s" % (IMAGES_FOLDER, CLIENT_LIST[client_macaddress]['image'], image_bootscript)
        try:
            if CLIENT_LIST[client_macaddress]['image'] == BUILT_IN_IMAGE_DEFAULT_NAME:
                content = BUILT_IN_IMAGE_DEFAULT
            else:
                with open(image_bootscript_path, 'r') as _file:
                    content = _file.read()
            logmessage('Responding to %s, with image bootscript file: %s' % (client_macaddress, image_bootscript_path))
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(bytes(content, 'UTF-8'))
        except FileNotFoundError:
            logmessage('Failed to find image bootscript file: %s' % image_bootscript_path)
            self.respond_fallback_image()
        except Exception as e:
            logmessage('Unexpected exception while reading image bootscript file: %s' % e)

    def get_unattended(self, fullurl):
        # endpoints are /unattended.cfg, /preseed.cfg, /Autounattend.xml, /unattend.xml
        # windows is a little picky about unattend file names, so we support multiple endpoints with the same method
        # actual name of the file within unattended/ is totally irrelevant to the client, the client receives file named matching the endpoint it requested
        urlparams = dict(parse.parse_qsl(parse.urlsplit(fullurl).query))
        client_ipaddress = self.client_address[0]
        # if not macaddress urlparam, use getmac library to lookup from ipaddress
        if 'macaddress' in urlparams.keys():
            client_macaddress = urlparams['macaddress']
        else:
            # logmessage('macaddress not specified, looking up from client IP address: %s' % client_ipaddress)
            client_macaddress = 'none'
            for entry_macaddress in CLIENT_LIST:
                if CLIENT_LIST[entry_macaddress]['ipaddress'] == client_ipaddress:
                    client_macaddress = entry_macaddress
                    logmessage('got macaddress: %s from ipaddress: %s' % (client_macaddress, client_ipaddress))
                    break
            if client_macaddress == 'none':
                logmessage('macaddress not specified and ipaddress is not in clientlist')
                self.respond_fallback_empty()
                return

        if client_macaddress not in CLIENT_LIST:
            # if no entry exists, bail
            logmessage('no entry in client_list for mac: %s' % client_macaddress)
            self.respond_fallback_empty()
            return

        unattended_path = "%s/%s" % (UNATTENDED_FOLDER, CLIENT_LIST[client_macaddress]['unattended'])
        try:
            if CLIENT_LIST[client_macaddress]['unattended'] == BUILT_IN_UNATTENDED_DEFAULT_NAME:
                content = BUILT_IN_UNATTENDED_DEFAULT
            else:
                with open(unattended_path, 'r') as unattended_file:
                    content = unattended_file.read()
            logmessage('Responding to %s, with unattended file: %s' % (client_macaddress, unattended_path))
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(bytes(content, 'UTF-8'))
        except FileNotFoundError:
            logmessage('Failed to find unattended file: %s' % unattended_path)
            self.respond_fallback_empty()
        except Exception as e:
            logmessage('Unexpected exception while reading unattended file: %s' % e)
            self.send_response(500)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()

    def get_loginpage(self):
        content = '''
            <!DOCTYPE html>
            <html>
                <head>
                    <title>Netboot Studio</title>
                    <meta name = "viewport" content = "width = device-width, initial-scale = 1"> 
                    <link rel="stylesheet" href="lib/materialize.min.css">
                    <link rel="stylesheet"  href="lib/material-icons.css">
                    <style>
                        .page-body {
                            display: flex;
                            flex-direction: column;
                            min-height: 100vh;
                        }
                        .main-style {
                            bottom:54px;
                            flex: 1 0 auto;
                            left:2vw;
                            overflow:scroll;
                            padding-top:112px;
                            position:absolute;
                            right:2vw;
                            top:0;
                            width:95vw;
                        }
                    </style>
                    <div id="static-header" style="z-index:100;">
                        <nav>
                            <div class="nav-wrapper" style="width:100vw;">
                                <a href="#" class="brand-logo">&nbsp; Netboot Studio</a>
                            </div>
                        </nav>
                    </div>
                </head>
                <body class="page-body lighten-5">
                    <main class="main-style container">
                        <form class="">
                            <div class="row">
                                <div class="input-field">
                                    <input id="user_name" type="email" autocorrect="off" autocapitalize="none" autofocus>
                                    <label for="user_name">User</label>
                                </div>
                            </div>
                            <div class="row">
                                <div class="input-field">
                                    <input id="user_password" type="password">
                                    <label for="user_password">Password</label>
                                </div>
                            </div>
                            <div class="row">
                                <a id="submit_button" class="waves-effect waves-light btn" onclick="doLoginRequest()">Login</a>
                            </div>
                        </form>
                    </main>
                    <script src="lib/materialize.min.js"></script>
                    <script>
                    function doLoginRequest(){
                        var user = document.getElementById('user_name').value.toLowerCase();
                        var password = document.getElementById('user_password').value;
                        var xmlHttp = new XMLHttpRequest(); 
                        try {
                            // create headers with auth-token here
                            xmlHttp.open( "POST", '/auth', false);
                            xmlHttp.send('{"user": "' + user + '", "password": "' + password + '"}'); 
                            if (xmlHttp.status === 200) {
                                var obj = JSON.parse(xmlHttp.responseText);
                                if ('auth_token' in obj) {
                                    AUTH_TOKEN = obj.auth_token;
                                    console.log('Successfully logged in');
                                    sessionStorage.setItem('auth_token', obj.auth_token);
                                    window.location.href = '/';
                                } else {
                                    M.toast({html: "Login Error"});
                                    console.error('Failed to login. status: 200, but no auth_token in response');
                                }
                            } else if (xmlHttp.status === 401) {
                                M.toast({html: "Unauthorized"});
                                console.error('Unauthorized. check user and pass');
                            } else {
                                M.toast({html: "Login Error:" + xmlHttp.status});
                                console.error('Error logging in. status: ' + xmlHttp.status);
                            }
                        } catch(e) {
                            M.toast({html: "Login Exception: " + e.name});
                            console.error('Exception while doing login request: ' + e);
                        }
                    }
                    document.getElementById('user_password').addEventListener('keyup', function(event){
                        if(event.keyCode == 13){
                            document.getElementById('submit_button').click();
                        }
                    });
                    document.addEventListener('DOMContentLoaded', function() {
                        // auto-initialize materialize elements
                        M.AutoInit();
                    });
                    </script>
                </body>
                <footer class="page-footer" style="position:fixed;bottom:0;left:0;width:100vw;">
                    <div class="footer-copyright">
                        <div class="container">
                        Copyright (C) 2019 James Bishop - v%s
                        </div>
                    </div>
                </footer>
            </html>
        ''' % (VERSION)
        # logmessage('Providing login form')
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(bytes(content, 'UTF-8'))

    def get_web(self, fullurl):
        clean_url = parse.urlparse(fullurl).path
        # urlparams = dict(parse.parse_qsl(parse.urlsplit(fullurl).query))
        client_ipaddress = self.client_address[0]
        if clean_url == '/':
            clean_url = '/index.html'
        if clean_url in WEB_RESOURCE_WHITELIST:
            local_file = 'web%s' % clean_url
            if local_file.endswith('.html'):
                content_type = 'text/html'
            elif local_file.endswith('.ttf'):
                content_type = 'font/ttf'
            elif local_file.endswith('.css'):
                content_type = 'text/css'
            elif local_file.endswith('.js'):
                content_type = 'text/javascript'
            else:
                content_type = 'text/plain'
            try:
                with open(local_file, 'r') as _file:
                    content = _file.read()
                # logmessage('Providing web file: %s' % (local_file))
                self.send_response(200)
                self.send_header('Content-type', content_type)
                self.end_headers()
                self.wfile.write(bytes(content, 'UTF-8'))
            except FileNotFoundError:
                self.send_response(400)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                logmessage('Failed to find web file: %s' % local_file)
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                logmessage('Unexpected exception while reading web file: %s' % e)
        else:
            logmessage('Request from %s for %s not whitelisted. Redirecting to /' % (client_ipaddress, clean_url))
            self.send_response(301)
            self.send_header('Location', '/')
            self.end_headers()

    def respond_fallback_image(self):
        # if we fail to find an expected image we will return built in default
        logmessage('WARNING - providing fallback image to %s for request: %s' % (self.client_address[0], parse.urlparse(self.path).path))
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(bytes(BUILT_IN_IMAGE_DEFAULT, 'UTF-8'))

    def respond_fallback_empty(self):
        # if all else fails respond with empty response
        logmessage('WARNING - providing empty response to %s for request: %s' % (self.client_address[0], parse.urlparse(self.path).path))
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(bytes(FALLBACK_EMPTY, 'UTF-8'))

    def post_wizarddata_json(self):
        # endpoint is /wizard-data.json
        # javascript cant work with yaml files without an ugly library, so we convert it to json first
        # returns wizard data as a json file for use by frontend
        try:
            with open(WIZARD_DATA_FILE, 'r') as data_file:
                content_obj = yaml.safe_load(data_file)
            content = json.dumps(content_obj)
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(bytes(content, 'UTF-8'))
        except FileNotFoundError:
            logmessage('Failed to find wizard data file: %s' % WIZARD_DATA_FILE)
            self.respond_fallback_empty()
        except yaml.YAMLError as e:
            logmessage('Exception while parsing wizard data file: %s' % e)
            self.send_response(500)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
        except Exception as e:
            logmessage('Unexpected exception while reading wizard data file: %s' % e)
            self.send_response(500)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()

# Backend Stuff
def CreateJob_NewImage(job_data):
    # we call job_function in a background thread, providing it one argument: job_data
    if job_data['image_type'] in CREATE_IMAGE_FUNCTIONS:
        job_function = CREATE_IMAGE_FUNCTIONS[job_data['image_type']]
        job_name = job_data['name']
        try:
            job_id = '%s' % uuid.uuid4()
            job_folder = '%s/%s' % (JOB_STATUS_FOLDER, job_id)
            job_file_name = '%s/name' % (job_folder)
            job_file_status = '%s/status' % (job_folder)
            job_file_progress = '%s/progress' % (job_folder)
            os.mkdir(job_folder)
            with open(job_file_name, 'wt', encoding='utf-8') as f:
                f.write(job_name)
            with open(job_file_status, 'wt', encoding='utf-8') as f:
                f.write('running')
            with open(job_file_progress, 'wt', encoding='utf-8') as f:
                f.write('0')
            JOB_LIST[job_id] = job_id
            RUNNING_JOBS[job_id] = multiprocessing.Process(target=job_function, args=(job_id, job_data))
            logmessage('starting job: %s' % job_id)
            RUNNING_JOBS[job_id].start()
        except Exception as e:
            logmessage('Unexpected exception while creating job: %s' % e)

def CreateJob_Unattended(job_data):
    # we call job_function in a background thread, providing it one argument: job_data
    if job_data['os_type'] in CREATE_UNATTENDED_FUNCTIONS:
        job_function = CREATE_UNATTENDED_FUNCTIONS[job_data['os_type']]
        job_name = job_data['filename']
        try:
            job_id = '%s' % uuid.uuid4()
            job_folder = '%s/%s' % (JOB_STATUS_FOLDER, job_id)
            job_file_name = '%s/name' % (job_folder)
            job_file_status = '%s/status' % (job_folder)
            job_file_progress = '%s/progress' % (job_folder)
            os.mkdir(job_folder)
            with open(job_file_name, 'wt', encoding='utf-8') as f:
                f.write(job_name)
            with open(job_file_status, 'wt', encoding='utf-8') as f:
                f.write('running')
            with open(job_file_progress, 'wt', encoding='utf-8') as f:
                f.write('0')
            JOB_LIST[job_id] = job_id
            RUNNING_JOBS[job_id] = multiprocessing.Process(target=job_function, args=(job_id, job_data))
            logmessage('starting job: %s' % job_id)
            RUNNING_JOBS[job_id].start()
        except Exception as e:
            logmessage('Unexpected exception while creating job: %s' % e)

def RefreshFileLists():
    # refresh SCRIPTS_LIST and UNATTENDED_LIST from files on disk
    # logmessage('Refreshing file lists from disk')
    IMAGE_LIST.clear()
    UNATTENDED_LIST.clear()
    ISO_LIST.clear()
    if not os.path.isdir(UNATTENDED_FOLDER):
        logmessage('unattended folder not found, creating empty folder')
        os.mkdir(UNATTENDED_FOLDER)
    if not os.path.isdir(IMAGES_FOLDER):
        logmessage('scripts folder not found, creating empty folder')
        os.mkdir(IMAGES_FOLDER)
    # create the built-in entry
    IMAGE_LIST[BUILT_IN_IMAGE_DEFAULT_NAME] = OrderedDict()
    IMAGE_LIST[BUILT_IN_IMAGE_DEFAULT_NAME]['name'] = BUILT_IN_IMAGE_DEFAULT_NAME
    for file_name in SUPPORTED_FILES:
        if file_name == 'netboot.ipxe':
            IMAGE_LIST[BUILT_IN_IMAGE_DEFAULT_NAME]['has_netboot.ipxe'] = True
        else:
            IMAGE_LIST[BUILT_IN_IMAGE_DEFAULT_NAME]['has_%s' % file_name] = False

    for image_folder in sorted(next(os.walk(IMAGES_FOLDER))[1]):
        if os.path.exists('%s/%s/netboot.ipxe' % (IMAGES_FOLDER, image_folder)):
            # netboot.ipxe is required, not a valid image without
            IMAGE_LIST[image_folder] = OrderedDict()
            IMAGE_LIST[image_folder]['name'] = image_folder
            IMAGE_LIST[image_folder]['has_netboot.ipxe'] = True

            for file_name in SUPPORTED_FILES:
                if file_name == 'netboot.ipxe':
                    # already set
                    continue
                if os.path.exists('%s/%s/%s' % (IMAGES_FOLDER, image_folder, file_name)):
                    IMAGE_LIST[image_folder]['has_%s' % file_name] = True
                else:
                    IMAGE_LIST[image_folder]['has_%s' % file_name] = False

            if os.path.exists('%s/%s/metadata.yaml' % (IMAGES_FOLDER, image_folder)):
                # load keys from metadata.yaml
                try:
                    with open('%s/%s/metadata.yaml' % (IMAGES_FOLDER, image_folder), 'r') as _file:
                        metadata = yaml.safe_load(_file)
                    for key in metadata:
                        IMAGE_LIST[image_folder][key] = metadata[key]
                except yaml.YAMLError as e:
                    logmessage('YAMLError while loading metadata.yaml: %s' % e)
                except Exception as e:
                    logmessage('Unexpected exception while loading metadata.yaml: %s' % e)


    UNATTENDED_LIST.append(BUILT_IN_UNATTENDED_DEFAULT_NAME)
    for file in sorted(os.listdir(UNATTENDED_FOLDER)):
        if file.endswith(".cfg"):
            UNATTENDED_LIST.append(file)
        if file.endswith(".xml"):
            UNATTENDED_LIST.append(file)
    for file in sorted(os.listdir(ISO_FOLDER)):
        if file.endswith(".iso"):
            ISO_LIST.append(file)

def LoadClientList():
    # logmessage('loading client list from file: %s' % CLIENT_LIST_FILE)
    try:
        with open(CLIENT_LIST_FILE, 'r') as f:
            data = json.loads(f.read().replace('\n', ''))
    except FileNotFoundError:
        logmessage('Failed to open: %s. Presuming fresh, starting with default data' % CLIENT_LIST_FILE)
        # if the file doesn't exist, we want to default to something valid
        data = {}
    except Exception as e:
        logmessage('Unexpected exception while reading client list from file: %s' % e)
        data = {}
    sorted_data = OrderedDict(sorted(data.items()))
    return sorted_data

def SaveClientList():
    logmessage('Writing client list to file')
    try:
        sorted_list = OrderedDict(sorted(CLIENT_LIST.items()))
        with open(CLIENT_LIST_FILE, 'wt', encoding='utf-8') as f:
            f.write(json.dumps(sorted_list))
    except Exception as e:
        logmessage('Unexpected exception while writing client list to file: %s' % e)

def GenerateAuthToken():
    _token = '%s' % uuid.uuid4()
    _time_now = datetime.timestamp(datetime.now())
    AUTH_TOKEN_LIST[_token] = dict()
    AUTH_TOKEN_LIST[_token]['timestamp'] = _time_now
    _delete_list = list()
    for this_token in AUTH_TOKEN_LIST:
        this_timestamp = AUTH_TOKEN_LIST[this_token]['timestamp']
        this_token_age = _time_now - this_timestamp
        if this_token_age > AUTH_TOKEN_TTL:
            # logmessage('marking an expired token for deletion, %s seconds old' % this_token_age)
            _delete_list.append(this_token)
    for this_token in _delete_list:
        # logmessage('deleting expired token: %s' % this_token)
        del AUTH_TOKEN_LIST[this_token]
    return _token

def ValidateAuthToken(token):
    if token in AUTH_TOKEN_LIST:
        _time_now = datetime.timestamp(datetime.now())
        this_timestamp = AUTH_TOKEN_LIST[token]['timestamp']
        this_token_age = _time_now - this_timestamp
        if this_token_age > AUTH_TOKEN_TTL:
            logmessage('Refusing expired token age: %s seconds' % this_token_age)
            del AUTH_TOKEN_LIST[token]
            return False
    else:
        logmessage('Refusing invalid token')
        return False
    return True

def GetVersion():
    # version is only ever shown on login page, because it is rendered server-side, as i dont think it necessary to create an endpoint just for getting version
    with open('VERSION', 'r') as file:
        _version = file.read()
    return _version

def SetupHTTPServer():
    # need global so changes in made by this function are are global
    global HTTP_PROCESS
    global HTTP_INSTANCE
    logmessage('Setting Up HTTPServer')
    try:
        HTTP_INSTANCE = HTTPServer(
            (HOST_NAME, HTTP_PORT),
            NSHTTPRequestHandler)
        HTTP_PROCESS = multiprocessing.Process(
            target=HTTP_INSTANCE
            .serve_forever)
        HTTP_PROCESS.daemon = False
        HTTP_PROCESS.start()
        logmessage('HTTP Server Start - %s:%s' % (HOST_NAME, HTTP_PORT))
    except Exception as e:
        logmessage('Unexpected Exception while setting up HTTPServer: %s' % e)

def ShutdownHTTPServer():
    # properly shutdown the http server
    global HTTP_PROCESS
    global KEEP_LOOPING
    try:
        logmessage('Shutting Down HTTP Server')
        KEEP_LOOPING = False
        HTTP_PROCESS.terminate()
        HTTP_PROCESS.join()
        logmessage('HTTP Server Stop - %s:%s' % (HOST_NAME, HTTP_PORT))
    except Exception as e:
        logmessage('Unexpected Exception while shutting down HTTP server: %s' % e)

def SetupWebSocketServer():
    # need global so changes in made by this function are are global
    global WEBSOCKET_LOOP
    global WEBSOCKET_STOP
    logmessage('Setting Up WebSocket Server')
    try:
        WEBSOCKET_LOOP = asyncio.get_event_loop()
        WEBSOCKET_STOP = WEBSOCKET_LOOP.create_future()
        logmessage('WebSocket Server Start - %s:%s' % (HOST_NAME, WEBSOCKET_PORT))
    except Exception as e:
        logmessage('Unexpected Exception while setting up WebSocketServer: %s' % e)

def ShutdownWebSocketServer():
    # properly shutdown the WebSocket server
    global WEBSOCKET_STOP
    global WEBSOCKET_LOOP
    logmessage('Shutting Down WebSocket Server')
    try:
        WEBSOCKET_STOP.set_result(0)
        WEBSOCKET_LOOP.stop()
        logmessage('WebSocket Server Stop - %s:%s' % (HOST_NAME, WEBSOCKET_PORT))
    except Exception as e:
        logmessage('Unexpected Exception while shutting down WebSocket server: %s' % e)

async def WebSocket_HandleReceiveMessages(websocket, path):
    # process any messages that come in
    global WEBSOCKET_CLIENTS
    WEBSOCKET_CLIENTS.add(websocket)
    async for message in websocket:
        wsclient_ipaddress = websocket.remote_address[0]
        wsclient_port = websocket.remote_address[1]
        logmessage('Received WebSocket message: %s from %s:%s' % (message, wsclient_ipaddress, wsclient_port))
        logmessage('sending one back')
        await SendWebsocketMessage('ack: %s' % message)

async def WebSocket_HandleSendMessages(websocket, path):
    # read MESSAGE_OUTBOX and send any messages
    global MESSAGE_OUTBOX
    while True:
        for msg_pending in MESSAGE_OUTBOX:
            logmessage('processing message: %s' % msg_pending.id)
            message = msg_pending.data
            del MESSAGE_OUTBOX[msg_pending]
            await websocket.send(message)

async def WebSocket_Handler(websocket, path):
    # handle BOTH sending and receiving
    consumer_task = asyncio.ensure_future(
        WebSocket_HandleReceiveMessages(websocket, path))
    producer_task = asyncio.ensure_future(
        WebSocket_HandleSendMessages(websocket, path))
    done, pending = await asyncio.wait(
        [consumer_task, producer_task],
        return_when=asyncio.FIRST_COMPLETED,
    )
    for task in pending:
        task.cancel()

async def WebSocket_Server(stop):
    async with websockets.serve(WebSocket_Handler, HOST_NAME, WEBSOCKET_PORT):
        await stop


def SendWebsocketMessage(message):
    global MESSAGE_OUTBOX
    msg_id = uuid.uuid4()
    logmessage('adding new msg to MESSAGE_OUTBOX')
    MESSAGE_OUTBOX[msg_id] = {
        'id': msg_id,
        'type': 'text',
        'data': message
    }

def Setup():
    # need global so changes in made by this function are are global
    global VERSION
    global CLIENT_LIST
    logmessage('Starting Setup')
    try:
        VERSION = GetVersion()
        clearlogfile()
        logmessage('Netboot Studio v%s service starting...' % VERSION)
        CLIENT_LIST = LoadClientList()
        # SetupWebSocketServer()
        SetupHTTPServer()
        signal.signal(signal.SIGTERM, HandleSignal)
        signal.signal(signal.SIGINT, HandleSignal)
        RefreshFileLists()
    except Exception as e:
        logmessage('Unexpected Exception during general setup: %s' % e)
    logmessage('Finished Setup')

def Shutdown():
    try:
        SaveClientList()
        ShutdownHTTPServer()
        # ShutdownWebSocketServer()
        logmessage('Netboot Studio Exiting')
        sys.exit(0)
    except Exception as e:
        logmessage('Unexpected Exception while Shutting Down: %s' % e)
        sys.exit(1)

def Loop():
    global WEBSOCKET_LOOP
    global WEBSOCKET_STOP
    logmessage('Loop Started')
    while KEEP_LOOPING:
        time.sleep(1)
    # WEBSOCKET_LOOP.run_until_complete(WebSocket_Server(WEBSOCKET_STOP))
    # WEBSOCKET_LOOP.run_forever()
    logmessage('Loop Ended')

def HandleSignal(this_signal, this_frame=None):
    # signal handler is attached to websocket loop
    try:
        logmessage('Caught signal, shutting down')
        logmessage('Caught signal: %s' % this_signal)
        # logmessage('Signal frame: %s' % this_frame)
        Shutdown()
    except Exception as e:
        logmessage('Unexpected Exception while handling signal: %s' % e)
        sys.exit(1)
    logmessage('Shutdown Complete')

if __name__ == '__main__':
    Setup()
    Loop()
