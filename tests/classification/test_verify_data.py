"""Unit tests for meerkat.classification.verify_data"""

import sys
import unittest
import csv
import pandas as pd
import meerkat.classification.verify_data as verifier

from tests.classification.fixture import verify_data_fixture
from nose_parameterized import parameterized

class VerifyDataTests(unittest.TestCase):
	"""Unit tests for meerkat.classification.verify_data"""

	@parameterized.expand([
		([["csv_input", "json_input", "subtype", "bank", "--credit_or_debit", "credit"]]),
	])
	def test_parse_arguments(self, arguments):
		"""Test parse_arguments with parameters"""
		parser = verifier.parse_arguments(arguments)
		self.assertEqual(parser.csv_input, "csv_input")
		self.assertEqual(parser.json_input, "json_input")
		self.assertEqual(parser.merchant_or_subtype, "subtype")
		self.assertEqual(parser.bank_or_card, "bank")
		self.assertEqual(parser.credit_or_debit, "credit")

	@parameterized.expand([
		([verify_data_fixture.get_args("valid"), ["subtype", "bank", "credit"], False]),
		([verify_data_fixture.get_args("invalid"), [], True])
	])
	def test_process_arguments(self, arguments, expected, exception):
		"""Test process_arguments with parameters"""
		if exception:
			self.assertRaises(Exception, verifier.process_arguments, arguments)
		else:
			self.assertEqual(verifier.process_arguments(arguments), expected)

	@parameterized.expand([
		([["AA", "BB"], ["AA", "BB"], "names", ""]),
		([[1, 2], [1, 2], "numbers", ""]),
		([[1, 2], [2, 3, 4], "numbers", "There are missing class numbers in json: " \
			"\"1\"\nThere are extra class numbers in json: \"3\", \"4\"\n"])
	])
	def test_add_err_msg(self, label_csv, label_json, numbers_or_names, err_msg):
		"""Test add_err_msg with parameters"""
		self.assertEqual(verifier.add_err_msg(label_csv, label_json, numbers_or_names), err_msg)

	@parameterized.expand([
		(["normal", [["AA", "BB"], ["AA", "BB"], [1, 2]]]),
		(["edge", [["AA", "BB"], ["BB"], [2]]])
	])
	def test_check_json_and_csv_consistency(self, case_type, labels):
		"""Test check_csv_and_json_consistency with parameters"""
		label_names_csv, label_names_json, label_numbers_json = labels[:]
		if case_type == "normal":
			verifier.check_json_and_csv_consistency(label_names_csv, label_names_json, label_numbers_json)
		else:
			self.assertRaises(SystemExit, verifier.check_json_and_csv_consistency,
				label_names_csv, label_names_json, label_numbers_json)

	@parameterized.expand([
		(["normal", verify_data_fixture.get_json_input_path("correct_format")]),
		(["edge", verify_data_fixture.get_json_input_path("dup_key")]),
		(["edge", verify_data_fixture.get_json_input_path("not_found")])
	])
	def test_load_json(self, case_type, json_input):
		"""Test load_json edge cases with parameters"""
		if case_type == "normal":
			verifier.load_json(json_input)
		else:
			self.assertRaises(SystemExit, verifier.load_json, json_input)

	@parameterized.expand([
		([verify_data_fixture.get_csv_input_path("subtype"), ["subtype", "bank", "credit"], 3]),
		([verify_data_fixture.get_csv_input_path("merchant"), ["merchant", "card"], 2])
	])
	def test_read_csv_to_df(self, csv_input, cnn_type, df_len):
		"""Test read_csv_to_df with parameters"""
		self.assertEqual(len(verifier.read_csv_to_df(csv_input, cnn_type)), df_len)

	@parameterized.expand([
		(["normal", verify_data_fixture.get_csv_input_path("correct_format"),
			["subtype", "bank", "debit"]]),
		(["edge", verify_data_fixture.get_csv_input_path("mal_format"),
			["subtype", "bank", "debit"]])
	])
	def test_verify_csv_format(self, case_type, csv_input, cnn_type):
		"""Test verify_csv_format with parameters"""
		df = pd.read_csv(csv_input, quoting=csv.QUOTE_NONE, na_filter=False,
			encoding="utf-8", sep='|', error_bad_lines=False, low_memory=False)
		if case_type == "normal":
			verifier.verify_csv_format(df, cnn_type)
		else:
			self.assertRaises(SystemExit, verifier.verify_csv_format, df, cnn_type)

	@parameterized.expand([
		(["normal", [1, 2, 3]]),
		(["edge", [0, 1, 2]])
	])
	def test_verify_json_1_indexed(self, case_type, label_numbers_json):
		"""Test verify_json_1_indexed with parameters"""
		if case_type == "normal":
			verifier.verify_json_1_indexed(label_numbers_json)
			return
		else:
			self.assertRaises(SystemExit, verifier.verify_json_1_indexed, label_numbers_json)

	@parameterized.expand([
		(["normal", ["AAA Insurance", "IKEA", "Starbucks"]]),
		(["edge", ["IKEA", "IKEA", "Starbucks"]])
	])
	def test_verify_json_no_dup_names(self, case_type, label_names_json):
		"""Test verify_json_no_dup_names with parameters"""
		if case_type == "normal":
			verifier.verify_json_no_dup_names(label_names_json)
		else:
			self.assertRaises(SystemExit, verifier.verify_json_no_dup_names, label_names_json)

	@parameterized.expand([
		(["normal", ["AA", "BB"], {"AA": 600, "BB": 800}, ["merchant"]]),
		(["edge", ["AA", "BB"], {"AA": 400, "BB": 600}, ["merchant"]])
	])
	def test_verify_numbers_in_each_class(self, case_type, label_names_csv, label_counts_csv, cnn_type):
		"""Test verify_numbers_in_each_class with parameters"""
		if case_type == "normal":
			verifier.verify_numbers_in_each_class(label_names_csv, label_counts_csv, cnn_type)
		else:
			self.assertRaises(SystemExit, verifier.verify_numbers_in_each_class,
				label_names_csv, label_counts_csv, cnn_type)

	@parameterized.expand([
		(["edge", verify_data_fixture.get_csv_input_path("subtype"),
			["subtype", "bank", "debit"]]),
		(["edge", verify_data_fixture.get_csv_input_path("merchant"),
			["merchant", "card"]])
	])
	def test_verify_total_numbers(self, case_type, csv_input, cnn_type):
		"""Test verify_total_numbers with parameters"""
		df = pd.read_csv(csv_input, quoting=csv.QUOTE_NONE, na_filter=False,
			encoding="utf-8", sep='|', error_bad_lines=False, low_memory=False)
		if case_type == "edge":
			self.assertRaises(SystemExit, verifier.verify_total_numbers, df, cnn_type)
