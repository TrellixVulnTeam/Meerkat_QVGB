"""Fixtures for test_tools"""
import numpy as np

BASE_DIR = "tests/classification/fixture/"

def get_output_filename():
	"""Return a output filename for tarball"""
	return "tests/classification/fixture/made_tarball.tar.gz"

def get_source_dir():
	"""Return a source directory"""
	return "tests/classification/fixture/to_make_tarball/"

def get_archive_path(case_type):
	"""Return the archive path"""
	archive_paths = {
		"invalid_tarfile": "tarball_1.tar.gz",
		"valid_tarfile": "tarball_5.tar.gz"
	}
	return BASE_DIR + archive_paths[case_type]

def get_des_path():
	"Return the destination path"
	return BASE_DIR + "extracted_tarball/"

def get_dict():
	"""Return a dictionary"""
	return {
		1: 0.0395,
		2: 0.0238,
		3: 0.0179,
		4: 0.0134
	}

def get_reversed_dict():
	"""Return a reversed dictionary"""
	return {
		0.0395: 1,
		0.0238: 2,
		0.0179: 3,
		0.0134: 4
	}

def get_csv_path(csv_type):
	"""Return a csv file path"""
	csv_path = {
		"correct_format": "tests/fixture/correct_format.csv",
		"with_empty_transaction": BASE_DIR + "with_empty_transaction.csv"
	}
	return csv_path[csv_type]

def get_s3_params_to_check_file_existence():
	"""Return a dictionary of s3 params"""
	return {
		"bucket": "s3yodlee",
		"prefix": "meerkat/Meerkat_tests_fixture/check_existence/"
	}

def get_s3_params_to_pull_from_s3(case_type):
	"""Return a dictionary of s3 params"""
	file_names = {
		"with_file_name": "csv_file_1.csv",
		"file_not_found": "missing.csv"
	}
	s3_params = {
			"bucket": "s3yodlee",
			"prefix": "meerkat/Meerkat_tests_fixture",
			"extension": "csv",
			"save_path": "tests/fixture/"
		}
	if case_type == "with_file_name" or case_type == "file_not_found":
		s3_params["file_name"] = file_names[case_type]
	return s3_params

def get_s3params(case_type):
	"""Return a dictionary of s3 params"""
	prefix = {
		"missing_input": "Meerkat_tests_fixture/missing_input/",
		"unpreprocessed": "Meerkat_tests_fixture/unpreprocessed/",
		"preprocessed": "Meerkat_tests_fixture/preprocessed/",
		"missing_slosh": "Meerkat_tests_fixture/preprocessed"
	}
	return {
		"bucket": "s3yodlee",
		"prefix": "meerkat/" + prefix[case_type]
	}

def get_result(case_type):
	"""Return a tuple of result"""
	newest_version_dir_unprocessed = "meerkat/Meerkat_tests_fixture/unpreprocessed/201604011500"
	newest_version_dir_processed = "meerkat/Meerkat_tests_fixture/preprocessed/201604011500"
	newest_version = "201604011500"
	if case_type == "missing_input":
		return ()
	elif case_type == "unpreprocessed":
		return (True, newest_version_dir_unprocessed, newest_version)
	else:
		return (False, newest_version_dir_processed, newest_version)

def get_predictions(case_type):
	"""Return a numpy array of predictions"""
	np_array_all_correct = np.arange(4).reshape(2, 2)

	np_array_all_wrong = np.arange(4).reshape(2, 2)
	np_array_all_wrong[:, 0] = 4

	np_array_half_correct = np.arange(4).reshape(2, 2)
	np_array_half_correct[0, 0] = 4

	np_arrays = {
		"all_correct": np_array_all_correct,
		"all_wrong": np_array_all_wrong,
		"half_correct": np_array_half_correct
	}
	return np_arrays[case_type]

def get_labels():
	"""Return a numpy array of labels"""
	return np.arange(4).reshape(2,2)

def get_gz_file(case_type):
	"""Return gz file path"""
	paths = {
		"no_json": BASE_DIR + "no_json.tar.gz",
		"two_jsons": BASE_DIR + "two_jsons.tar.gz",
		"valid": BASE_DIR + "valid_merchant_input.tar.gz"
	}
	return paths[case_type]

def get_unzip_and_merge_result():
	"""Return a turple of results"""
	return (2, "./merchant_card_unzip/foo.json")

def get_config():
	"""Return a config dictionary"""
	alphabet = "abcdefghijklmnopqrstuvwxyz0123456789,;.!?:'\"/\\|_@#$%^&*~`+-=<>()[]{}"
	alpha_dict = {a : i for i, a in enumerate(alphabet)}
	return {
		"alphabet": alphabet,
		"alpha_dict": alpha_dict
	}

def get_tensor(case_type):
	"""Return a tensor coverted from doc string"""
	if case_type == "short_doc":
		tensor = np.zeros((68, 4), dtype=np.float32)
		tensor[0][1] = 1.
		tensor[0][2] = 1.
		tensor[1][0] = 1.
	else:
		tensor = np.zeros((68, 2), dtype=np.float32)
		tensor[0] = [1., 1.]
	return tensor

