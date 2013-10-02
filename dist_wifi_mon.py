#!/usr/bin/python
#
# Monitor the specified wifi network

# TODO: add ability to look for specific wired network based on next hop's MAC
#       add ability to record next hop's MAC address

import os
import random
import getpass
import sha
import base64
import hmac
import hashlib
import datetime
from subprocess import CalledProcessError, check_output

# How to do the tests (add your own values here)
ssid = ""
s3_bucket = ""
access_key = ""
secret_access_key = ""
s3host = "http://s3-eu-west-1.s3.amazonaws.com"  # FIXME: hard-coded region
content_type = "text/plain"
username = getpass.getuser()  # Can be a random string if you want 'privacy'
cache = "/tmp/dist-wifi-mon"
cache_limit = 4000  # Number of bytes of results to cache before sending
cache_full = 99999  # Stop collecting data if the cache gets too full
ping_timeout = "10000"  # milliseconds
debug = False

# What to test (you can change these, e.g. if you have a restricted network)
dns_server = ""  # Use route-provided DNS
#dns_server = "8.8.8.8"  # Use a specific DNS server
ping_addresses = [
    "8.8.8.8",        # Google's public DNS server
    "4.2.2.2",        # b.resolvers.Level3.net
    "208.67.222.222"  # resolver1.opendns.com
]
host_addresses = [  # Things that should be addressable
    "google.com",
    "bbc.co.uk",
    "slashdot.org"
]
curl_addresses = [  # Things that shoul be up - consider using smaller pages
    "http://bbc.co.uk",
    "http://google.com",
    "http://slashdot.org"
]

if not (ssid and s3_bucket and s3host and access_key and secret_access_key):
    exit("Please enter all required values in the top of the script")

if not os.path.exists(cache):
    os.mkdir(cache)

t0 = datetime.datetime.now()
t0_awsformat = t0.strftime("%a, %-d %b %Y %H:%M:%S BST")  # FIXME: hard-coded locale, non-portable strf hack
t0_epoch = int(round((t0 - datetime.datetime(1970, 1, 1)).total_seconds()))
expires = t0_epoch + 1814400  # 3 weeks

# Pick random settings to use on this run
ip = random.choice(ping_addresses)
host = random.choice(host_addresses)
curl  = random.choice(curl_addresses)

# Check we're on the correct network
airport = "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport"
on_wifi = check_output([airport, "-I"])
if 'SSID: {}'.format(ssid) not in on_wifi:
    exit("Not on the {} network".format(ssid))

# Ping check
try:
    ping_cmd = ["ping", "-c", "1", "-n", "-W", ping_timeout, ip]
    ping_result = check_output(ping_cmd)
except CalledProcessError:
    exit("Ping exception, likely took longer than {} ms".format(ping_timeout))
if "time=" in ping_result:
    ping_line = ping_result.split("\n")[1].split(' ')
    ping_time = ping_line[-2][5:]
    ping_units = ping_line[-1]
    print("Pinged {0} in {1} {2}".format(ip, ping_time, ping_units))
elif "100.0% packet loss" in ping_result:  # TODO, capture percent packet loss
    print "100.0% packet loss from {}".format(ip)
    ping_time = -100
else:
    print "Unknown response when pinging {}".format(ip)
    ping_time = -1

# DNS check
dns_t0 = datetime.datetime.now()
dns_args = ["host", host]
if dns_server:
    dns_args.append(dns_server)
dns_result = check_output(dns_args)
dns_time = (datetime.datetime.now() - dns_t0).seconds
if 'has address' in dns_result:
    if dns_time > 0:
        print("Warning: DNS lookup took {} seconds".format(dns_time))
    else:
        print("DNS lookup took less than a second")
elif 'NXDOMAIN' in dns_result:
    exit("Got NXDOMAIN for a well-known domain")
else:
    exit("There was an unknown problem with DNS")

# Curl check
curl_t0 = datetime.datetime.now()
curl_response = check_output(["curl", "-s", curl])
curl_time = (datetime.datetime.now() - curl_t0).seconds
try:
    if curl_response != '':
        if "html" in curl_response.lower():
            print("found 'html' in curl response after {} seconds".format(
                curl_time))
except:
    print "Unable to fetch {}".format(curl)
    curl_time = -1

# Save results locally
with open(os.path.join('{}'.format(cache), str(t0_epoch)), 'w') as f:
    f.write("{0}, {1}, {2}, {3}, {4}, {5}, {6}\n".format(
        t0_epoch, ip, ping_time, host, dns_time, curl, curl_time))

# Unlikely to be able to go any further if not successful so far
if not (ping_time >= 0 and dns_time >= 0 and curl_time >= 0):
    exit()

# If it is time to post data to s3, try to do so
filenames = os.listdir(cache)
dir_size = sum([
    os.path.getsize(os.path.join(cache, filename))
        for filename in filenames])
print "Current cache is {} bytes, will upload at {} bytes".format(
    dir_size, cache_limit)
if dir_size > cache_limit:
    outfile = "{0}/{1}-{2}".format(cache, str(t0_epoch), username)
    _, outfilename = os.path.split(outfile)
    if cache not in ["", "/", ".", "~"]:  # Don't blat important directories
        with open(outfile, 'w') as o:
            for f in filenames:
                if not f.endswith(getpass.getuser()):
                    with open(os.path.join(cache, f)) as i:
                        content = i.read()
                        o.write(content)

        m = hashlib.md5()
        with open(outfile, 'r') as o:
            content = o.read()
            m.update(content)
        content_md5 = m.hexdigest()

        # Calculate aws signature
        str_to_sign = "PUT\n\n{0}\n{1}\n/s3-eu-west-1/{2}/{3}".format(
            #content_md5,
            content_type,
            t0_awsformat,
            s3_bucket,
            outfilename)
        h = hmac.new(secret_access_key, str_to_sign, sha)
        b = base64.encodestring(h.digest()).strip()

        headers = [
            "-H", "User-Agent: ",
            "-H", "ACCEPT: ",
            "-H", "Connection: ",
            "-H", "Expect: ",
            "-H", "PUT /{0}/{1} HTTP/1.0".format(s3_bucket, outfilename),
            "-H", "Content-Type: {}".format(content_type),
            "-H", "Date: {}".format(t0_awsformat),
            "-H", "Authorization: AWS {}:{}".format(access_key, b)]

        if debug:
            verbosity = '-v'
        else:
            verbosity = ''

        curl_cmd = [
            "curl", "-0", "-s", verbosity,
            "--retry", "10", "--retry-delay", "5",
            "-X", "PUT", "-L",
            "-d", "@{}".format(os.path.join(cache, outfile)) ] + headers + [
            "{0}/{1}/{2}".format(s3host, s3_bucket, outfilename)]

        if debug:
            print "Uploading {0} to {1} using {2}...".format(
                outfile, s3host, curl_cmd)

        curl_response = check_output(curl_cmd)
        print "Response from s3 was: {}".format(curl_response)
print "Done."