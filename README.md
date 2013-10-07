dist-wifi-mon
=============

A distributed wifi monitor. Tested on Mac, with minor modifications should port to other systems.

Setting up your site
--------------------

You will also need to set up an Amazon s3 bucket and create an IAM user with an access key and secret access key and give the user the folling IAM policy:

(Policy TBD)

Edit the variables at the top of the script to reflect your settings.

To use this script you need to make it run every minute or few. You can use automator or cron to do this.
