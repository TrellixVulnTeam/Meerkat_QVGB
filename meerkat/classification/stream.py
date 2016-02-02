""" Just a test bed for new ideas."""

import os
import sys
import json
import csv
import string

import numpy as np
import pandas as pd

from boto.s3.connection import Key, Location
from boto import connect_s3

def dict_2_json(obj, filename):
	"""Saves a dict as a json file"""
	with open(filename, 'w') as fp:
		json.dump(obj, fp, indent=4)

def cap_first_letter(label):
	"""Make sure the first letter of each word is capitalized"""
	temp = label.split()
	for i in range(len(temp)):
		if temp[i].lower() in ['by', 'with', 'or', 'at', 'in']:
			temp[i] = temp[i].lower()
		else:
			temp[i] = temp[i][0].upper() + temp[i][1:]
	return ' '.join(word for word in temp)

def pull_from_s3(*args, **kwargs):
	"""Pulls the contents of an S3 directory into a local file"""
	conn = connect_s3()
	bucket = conn.get_bucket(kwargs["bucket"], Location.USWest2)
	listing = bucket.list(prefix=kwargs["prefix"])

	my_filter = kwargs["my_filter"]
	s3_object_list = [
		s3_object
		for s3_object in listing
		if s3_object.key[-len(my_filter):] == my_filter
	]
	get_filename = lambda x: kwargs["input_path"] + x.key[x.key.rfind("/")+1:]
	local_files = []
	for s3_object in s3_object_list:
		local_file = get_filename(s3_object)
		print("Local Filename: {0}, S3Key: {1}".format(local_file, s3_object))
		s3_object.get_contents_to_filename(local_file)
		local_files.append(local_file)
	return local_files

def load(*args, **kwargs):
	"""Load the CSV into a pandas data frame"""
	filename, debit_or_credit = kwargs["input_file"], kwargs["debit_or_credit"]

	df = pd.read_csv(filename, quoting=csv.QUOTE_NONE, na_filter=False,
		encoding="utf-8", sep='|', error_bad_lines=False, low_memory=False)
	df['UNIQUE_TRANSACTION_ID'] = df.index
	df['LEDGER_ENTRY'] = df['LEDGER_ENTRY'].str.lower()
	grouped = df.groupby('LEDGER_ENTRY', as_index=False)
	groups = dict(list(grouped))
	df = groups[debit_or_credit]
	df["PROPOSED_SUBTYPE"] = df["PROPOSED_SUBTYPE"].str.strip()
	df['PROPOSED_SUBTYPE'] = df['PROPOSED_SUBTYPE'].apply(cap_first_letter)
	class_names = df["PROPOSED_SUBTYPE"].value_counts().index.tolist()
	return df, class_names

def get_label_map(*args, **kwargs):
	"""Stuff"""
	class_names = kwargs["class_names"]
	# Create a label map
	label_numbers = list(range(1, (len(class_names) + 1)))
	label_map = dict(zip(sorted(class_names), label_numbers))
	# Map Numbers
	a = lambda x: label_map[x["PROPOSED_SUBTYPE"]]
	df = kwargs["df"]
	df['LABEL'] = df.apply(a, axis=1)
	return label_map

def get_test_and_train_dataframes(*args, **kwargs):
	"""Produce (rich and poor) X (test and train) dataframes"""
	df_rich = kwargs["df"]
	df_poor = df_rich[['LABEL', 'DESCRIPTION_UNMASKED']]
	msk = np.random.rand(len(df_poor)) < 0.90
	return {
		"df_poor_train" : df_poor[msk],
		"df_poor_test" : df_poor[~msk],
		"df_rich_train" : df_rich[msk],
		"df_test" : df_rich[~msk]
	}

def get_json_and_csv_files(*args, **kwargs):
	"""This function generates CSV and JSON files"""
	prefix = output_path + bank_or_card + "." + debit_or_credit + "."
	#set file names
	files = {
		"map_file" : prefix + "map.json",
		"test_rich" : prefix + "test.rich.csv",
		"train_rich" : prefix + "train.rich.csv",
		"test_poor" : prefix + "test.poor.csv",
		"train_poor" : prefix + "train.poor.csv"
	}
	#Write the JSON file
	dict_2_json(kwargs["label_map"], files["map_file"])
	#Write the rich CSVs
	rich_kwargs = { "index" : False, "sep" : "|" }
	kwargs["df_test"].to_csv(files["test_rich"], **rich_kwargs)
	kwargs["df_rich_train"].to_csv(files["train_rich"], **rich_kwargs)
	#Write the poor CSVs
	poor_kwargs = { "cols" : ["LABEL", "DESCRIPTION_UNMASKED"], "header": False,
		"index" : False, "index_label": False }
	kwargs["df_poor_test"].to_csv(files["test_poor"], **poor_kwargs)
	kwargs["df_poor_train"].to_csv(files["train_poor"], **poor_kwargs)
	#Return file names
	return files

def process_stage_1(*args, **kwargs):
	"""Coordinates activity for the job stream"""
	# Create an output directory if it does not exist
	os.makedirs(kwargs["output_path"], exist_ok=True)
	# Load Data
	if len(kwargs["local_files"]) == 1:
		input_file = kwargs["local_files"].pop()
		del kwargs["local_files"]
	else:
		print("Cannot proceed, no files found in S3")
		sys.exit(0)
	df, class_names = load(input_file=input_file, debit_or_credit=kwargs["debit_or_credit"])
	# Generate a mapping (class_name: label_number)
	label_map = get_label_map(df=df, class_names=class_names)
	# Reverse the mapping (label_number: class_name)
	kwargs["label_map"] = dict(zip(label_map.values(), label_map.keys()))
	# Clean the "DESCRIPTION_UNMASKED" values within the dataframe
	fill_description = lambda x: x["DESCRIPTION"] if x["DESCRIPTION_UNMASKED"] == "" else x["DESCRIPTION_UNMASKED"]
	df["DESCRIPTION_UNMASKED"] = df.apply(fill_description, axis=1)
	kwargs["df"] = df
	# Make Test and Train data frames
	kwargs.update(get_test_and_train_dataframes(**kwargs))
	# Generate the output files (CSV and JSON) and return the file handles
	kwargs.update(get_json_and_csv_files(**kwargs))

""" Main program"""
if __name__ == "__main__":
	bucket = "yodleemisc"
	prefix = "hvudumala/Type_Subtype_finaldata/Card/"
	my_filter = "csv"
	input_path, output_path = "./", "./output/"
	bank_or_card, debit_or_credit = "card", "debit"
	local_files = pull_from_s3(bucket=bucket, prefix=prefix, my_filter=my_filter,
		input_path=input_path)
	process_stage_1(local_files=local_files, debit_or_credit=debit_or_credit,
		output_path=output_path, bank_or_card=bank_or_card)


