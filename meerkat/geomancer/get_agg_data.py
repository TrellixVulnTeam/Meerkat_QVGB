"""This module will sync local agg data with s3"""

import argparse
import boto3
import json
import logging
import os
import sys
import yaml

from meerkat.various_tools import load_params

logging.config.dictConfig(yaml.load(open('meerkat/geomancer/logging.yaml', 'r')))
logger = logging.getLogger('get_agg_data')

def parse_arguments(args):
	"""Parse arguments from command line"""
	parser = argparse.ArgumentParser()
	parser.add_argument("--bucket", default="s3yodlee",
		help="s3 bucket name")
	parser.add_argument("--prefix", default="meerkat/geomancer/data/agg/",
		help="s3 object prefix")
	parser.add_argument("--filename", default="All_Merchants.csv",
		help="agg data file name in s3")
	parser.add_argument("--savepath", default="meerkat/geomancer/data/agg_data/",
		help="local save path of agg data file")
	args = parser.parse_args(args)
	return args

def get_etags(base_dir):
	"""Fetch local ETag values from a local file"""
	etags_file = base_dir + "etags.json"
	etags = {}
	if os.path.isfile(etags_file):
		logger.info("ETags found.")
		etags = load_params(etags_file)
	else:
		logger.info("Etags not found")
	return etags, etags_file

def get_s3_file(**kwargs):
	"""Load agg data from s3 to the local host"""

	client = boto3.client("s3")
	remote_file = kwargs["prefix"] + kwargs["file_name"]
	local_file = kwargs["save_path"] + kwargs["file_name"]

	local_file_exist = False
	if os.path.isfile(local_file):
		logger.info("local file {0} exists".format(local_file))
		local_file_exist = True
	else:
		logger.info("local file {0} not found".format(local_file))

	logger.debug(client.list_objects(Bucket=kwargs["bucket"],
		Prefix=remote_file))
	remote_etag = client.list_objects(Bucket=kwargs["bucket"],
		Prefix=remote_file)["Contents"][0]["ETag"]

	if local_file_exist:
		local_etag = None
		if remote_file in kwargs["etags"]:
			local_etag = kwargs["etags"][remote_file]

		logger.info("{0: <6} ETag is : {1}".format("Remote", remote_etag))
		logger.info("{0: <6} ETag is : {1}".format("Local", local_etag))

		#If the file is already local, skip downloading
		if local_etag == remote_etag:
			logger.info("Agg data exists locally no need to download")
			#File does not need to be downloaded
			return False

	logger.info("start downloading agg data from s3")
	client.download_file(kwargs["bucket"], remote_file, local_file)
	logger.info("Agg data file is downloaded at: " + local_file)

	etags = {}
	etags[remote_file] = remote_etag
	with open(kwargs["etags_file"], "w") as outfile:
		logger.info("Writing {0}".format(kwargs["etags_file"]))
		json.dump(etags, outfile)

	#File needs to be downloaded
	return True

def main_process(args):
	"""Execute the main programe"""

	bucket = args.bucket
	prefix = args.prefix
	file_name = args.filename
	save_path = args.savepath
	os.makedirs(save_path, exist_ok=True)

	etags, etags_file = get_etags(save_path)

	needs_to_be_downloaded = get_s3_file(bucket=bucket, prefix=prefix, file_name=file_name,
		save_path=save_path, etags=etags, etags_file=etags_file)


if __name__ == "__main__":
	args = parse_arguments(sys.argv[1:])
	main_process(args)

