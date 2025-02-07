"""Unit test for meerkat/classification/split_data.py"""

import sys
import unittest
import meerkat.classification.split_data as split_data

from nose_parameterized import parameterized

class SplitDataTests(unittest.TestCase):
	"""Our UnitTest class."""

	@parameterized.expand([
		([["merchant", "bank"], "merchant", "bank", False]),
		([["subtype", "bank"], "", "", True])
	])
	def test_parse_arguments(self, args, model_type, bank_or_card, exception):
		"""Test get_parge_arguments with parameters"""
		if exception:
			self.assertRaises(Exception, split_data.parse_arguments, args)
		else:
			args = split_data.parse_arguments(args)
			self.assertEqual(args.model_type, model_type)
			self.assertEqual(args.bank_or_card, bank_or_card)
