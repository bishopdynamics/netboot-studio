# TODO

## Near Term

* move unattended name to page2 like in Images

* unattended - make copy button work
* unattended - add delete button
* images - add delete button
* clients - add forget button

* unattended wizard
	- windows, more options: https://docs.microsoft.com/en-us/windows-hardware/customize/desktop/unattend/microsoft-windows-international-core-winpe-inputlocale
	- windows, make base64 encoded passwords work

* unattended partitions options
	- collection of partitioning templates?

* rework how we validate input for wizards, and how to handle optional input
* make sure images that fail get cleaned up

* for saving/getting image files, check against SUPPORTED_FILES

* upload only works for files <1GB
	- https://deliciousbrains.com/using-javascript-file-api-to-avoid-file-upload-limits/
	- https://gist.github.com/Francesco149/8e5b29091bee8b7f630772cc459d8bcc
	- https://f-o.org.uk/2017/receiving-files-over-http-with-python.html
	- https://thoughtbot.com/blog/html5-powered-ajax-file-uploads
	- https://github.com/bencolon/file-uploader/blob/master/client/fileuploader.js

* rework status messages
	- https://www.programcreek.com/python/example/94582/websockets.ConnectionClosed
	- https://docs.python.org/3/library/asyncio-future.html
	- https://websockets.readthedocs.io/en/stable/deployment.html
	- https://websockets.readthedocs.io/en/stable/faq.html
	- 
	- we want to push from server, so realistically it has to be a websocket
	- want to live-update tabs when new entries are added server side
	- page side code will produce/update toast messages
		- job-status messages update
		- dismiss button will send back dismiss <msg-id>
	- messages will have ID, 
		- page will ignore already-seen messages by ID
		- server will drop messages older than N seconds
	- want to sent complex status messages
		- tags for buttons to show
		- lifetime
		- idea:
			```
			messages: {
				msg-2118: {
					type: 'job-status',
					job-id: '409820485983498593874583749584',
					job-type: 'unattended',
					name: 'my-unattend.xml',
					status: 'running',
					progress: '57'
				},
				msg-2225: {
					type: 'job-status',
					job-id: '4098204859834985938775845767876',
					job-type: 'image',
					name: 'Windows-12-Pro-Jan-2025',
					status: 'running',
					progress: '42'
				},
				msg-2227: {
					type: 'job-status',
					job-id: '4098204859834985938777838795433',
					job-type: 'image',
					name: 'Debian-11-64bit',
					status: 'done',
					progress: '100'
				},
				msg-2229: {
					type: 'job-status',
					job-id: '4098204478234589234897023479324',
					job-type: 'image',
					name: 'Ubuntu-22.04-Desktop-Live-64bit',
					status: 'queued',
					progress: '0'
				},
				msg-2231: {
					type: 'new-data',
					data-type: 'client'
					data: <client_list>
				},
			}
			```

* make editor less squirly
	- highlight vs actual mismatch, alignment
	- every load, extra newline added to end of file

* stage client changes, add save button, editclient needs to handle multiple changes
* move http file server to port 6163
* switch everything to using "netboot-service" user
* validate theory that only folders need chmodding for apache - validated, but not corrected everywhere
	- perform complete rebuild of /opt/tftp-root

* create "Continue" built-in image
	- either boot from first hd, or exit (next boot device hopefully)
* create "Interactive Menu" built-in image
	- generate from image_list



## next milestone

* create settings page
	- add password to settings
* can we manage post-install scripts?
	- add /post-install{.sh|.cmd} endpoint
	- like unattended, can use ip to lookup file
* prepare for running dir to be /opt/netboot-studio/
* create systemd service file
* create build-release.sh
	- compile ipxe binaries & fetch wimboot
	- package zip with essential files
	- include install.sh
		- create /opt/tftp-root folder structure
		- copy ipxe binaries (& images) to /opt/tftp-root/
		- copy netboot-studio files to /opt/netboot-studio/
		- create netboot-service user
		- chown all files as netboot-service:www-data
			- or add netboot-service user to www-data group, and chown netboot-service:netboot-service ?
		- install http, tftp, smb, nfs services
		- create (or append to) service config files
		- restart all services
* create dockerfile that fetches latest release.zip
* move from /opt/tftp-root -> /opt/netboot-studio
* can (should) we monitor http,smb,nfs access logs and note in our own log?


## profile and solutions

instead of assigning an unattended file, you assign a profile
a profile defines answers with all variables needed to construct an unattended file for any supported image type
further, a profile includes a post-install manifest, which defines a list of solutions to be installed on the machine
a solution is instructions to provide a standardized resource (ex: http server), with a standardized config. a solution provides tested, well conceived scripts for installing everything needed to provide the expected service, for each supported image type

A profile handles all unattended information, but the solutions attached to a profile provide all the post-install information. 

### format of wizard data

input-keys: a list of data points spcifying required input
distro-types: a list of distinct OS distributions, and the required input-keys to constitute a profile

