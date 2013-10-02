mac-wifi-dist-mon
=================

A distributed wifi monitor for mac

You will also need to set up an Amazon s3 bucket and create an IAM user with an access key and secret access key and give the user the folling IAM policy:

{}
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": [
        "s3:PutObject"
      ],
      "Sid": "Stmt1380621988000",
      "Resource": [
        "arn:aws:s3:::YOUR_S3_BUCKET_NAME"
      ],
      "Effect": "Allow"
    }
  ]
}

Edit the variables at the top of the script to reflect your settings.

To use this script you need to make it run every minute or few. You can use automator to do this.