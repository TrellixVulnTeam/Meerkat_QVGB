#!/usr/local/bin/python3.3

"""This module enriches transactions with additional
data found by Meerkat

Created on Nov 3, 2014
@author: Matthew Sevrens
"""

import json
# pylint:disable=deprecated-module
import string
import re
import logging
import os
from multiprocessing.pool import ThreadPool
from scipy.stats.mstats import zscore

from meerkat.various_tools import get_es_connection, string_cleanse, get_boosted_fields
from meerkat.various_tools import synonyms, get_merchant_query
from meerkat.classification.load_model import load_scikit_model, get_tf_cnn_by_path, get_tf_rnn_by_path
from meerkat.classification.auto_load import main_program as load_models_from_s3

# pylint:disable=no-name-in-module
from meerkat.classification.bloom_filter.trie import location_split

# Enabled Models
BANK_SWS = load_scikit_model("bank_sws")
CARD_SWS = load_scikit_model("card_sws")

class WebConsumer():
	"""Acts as a web service client to process and enrich
	transactions in real time"""

	# 14 is the best thread number Andy has tried
	__cpu_pool = ThreadPool(processes=14)

	def __init__(self, params=None, hyperparams=None, cities=None):
		"""Constructor"""

		if params is None:
			self.params = dict()
		else:
			self.params = params
			if not params["elasticsearch"]["skip_es"]:
				self.elastic_search = get_es_connection(params)
				mapping = self.elastic_search.indices.get_mapping()
				index = params["elasticsearch"]["index"]
				index_type = params["elasticsearch"]["type"]
				self.params["routed"] = "_routing" in mapping[index]["mappings"][index_type]

		self.load_tf_models()
		self.hyperparams = hyperparams if hyperparams else {}
		self.cities = cities if cities else {}

	def load_tf_models(self):
		"""Load all tensorFlow models"""

		gmf = self.params.get("gpu_mem_fraction", False)
		auto_load_config = self.params.get("auto_load_config", None)

		#Auto load cnn models from S2, if necessary
		if auto_load_config is not None:
			#Flush old models, to be safe
			target_dir = "meerkat/classification/models/"
			for file_name in os.listdir(target_dir):
				if file_name.endswith(".meta") or file_name.endswith(".ckpt"):
					file_path = os.path.join(target_dir, file_name)
					logging.warning("Removing {0}".format(file_path))
					os.unlink(file_path)
			#Load new models from S3
			load_models_from_s3(config=auto_load_config)

		# Get CNN Models
		self.models = dict()
		models_dir = 'meerkat/classification/models/'
		label_maps_dir = "meerkat/classification/label_maps/"
		for filename in os.listdir(models_dir):
			if filename.endswith('.ckpt') and not filename.startswith('train'):
				temp = filename.split('.')[:-1]
				if temp[-1][-1].isdigit():
					key = '_'.join(temp[1:-1] + [temp[0], temp[-1], 'cnn'])
				else:
					key = '_'.join(temp[1:] + [temp[0], 'cnn'])
				self.models[key] = get_tf_cnn_by_path(models_dir + filename, \
					label_maps_dir + filename[:-4] + 'json', gpu_mem_fraction=gmf)

		# Get RNN Models
		self.merchant_rnn = get_tf_rnn_by_path('meerkat/longtail/models/bilstm.ckpt', 'meerkat/longtail/models/w2i.json')

	def update_hyperparams(self, hyperparams):
		"""Updates a WebConsumer object's hyper-parameters"""
		self.hyperparams = hyperparams

	def __get_query(self, transaction):
		"""Create an optimized query"""

		# Input transaction must not be empty
		if len(transaction['description']) <= 2 and re.match('^[a-zA-Z0-9_]+$', transaction['description']):
			return

		locale_bloom = transaction["locale_bloom"]
		if transaction["CNN"]['label'] != '':
			term = transaction["CNN"]['label']
		else:
			self.merchant_rnn([transaction])
			term = transaction["Predicted"]

		# Replace synonyms
		term = synonyms(term)
		term = string_cleanse(term)
		transaction["Processed"] = term

		if locale_bloom:
			return get_merchant_query(term, locale_bloom[0], locale_bloom[1])
		else:
			return get_merchant_query(term, '', '')

	def __search_index(self, queries):
		"""Search against a structured index"""
		index = self.params["elasticsearch"]["index"]
		results = self.elastic_search.msearch(queries, index=index)
		return results
		#try:
		#	# pull routing out of queries and append to below msearch
		#	results = self.elastic_search.msearch(queries, index=index)
		#except Exception as exception:
		#	logging.warning(exception)
		#	return None
		#return results

	@staticmethod
	def __z_score_delta(scores):
		"""Find the Z-Score Delta"""
		if len(scores) < 2:
			return None, None
		z_scores = zscore(scores)
		first_score, second_score = z_scores[0:2]
		z_score_delta = round(first_score - second_score, 3)
		return z_score_delta, scores[0]

	def __process_results(self, results, transaction):
		"""Process search results and enrich transaction
		with found data"""

		hyperparams = self.hyperparams

		# Must be at least one result
		if "hits" not in results or results["hits"]["total"] == 0:
			transaction = self.__no_result(transaction)
			return transaction

		# Collect Necessary Information
		hits = results['hits']['hits']
		if len(hits) <= 0: 
			transaction = self.__no_result(transaction)
			return transaction
		top_hit = hits[0]

		# Elasticsearch v1.0 bug workaround
		if top_hit["_source"].get("pin", "") != "":
			coordinates = top_hit["_source"]["pin"]["location"]["coordinates"]
			top_hit["_source"]["longitude"] = "%.6f" % (float(coordinates[0]))
			top_hit["_source"]["latitude"] = "%.6f" % (float(coordinates[1]))

		name = top_hit["_source"].get("name", '')
		locality = top_hit["_source"].get("locality", '')
		region = top_hit["_source"].get("region", '')
		city, state = (transaction['locale_bloom'][0], transaction['locale_bloom'][1]) if transaction['locale_bloom'] else ('', '')
		total = results['hits']['total']
		decision = False
		if locality.lower().replace('.', '') != city.lower() or region.upper() != state.upper():
			if name.lower().replace('-', ' ').replace('\'', '') != transaction["Processed"].lower():
				name = ''
		else:
			if total == 1:
				decision = True
			else:
				if len(hits) < 2:
					transaction = self.__no_result(transaction)
					return transaction
				if locality != hits[1]["_source"].get("locality", '') or region != hits[0]["_source"].get("region", ''):
					decison = True
#				else:
#					if name.lower().replace('-', ' ').replace('\'', '') != hits[1]["_source"].get("name", ''):
#						name = ''

		# Enrich Data if Passes Boundary
		args = [decision, transaction, top_hit, name, city, state]
		return self.__enrich_transaction(*args)

	def __no_result(self, transaction):
		"""Make sure transactions have proper attribute names"""

		params = self.params
		fields = params["output"]["results"]["fields"]
		labels = params["output"]["results"]["labels"]
		attr_map = dict(zip(fields, labels))

		for field in fields:
			transaction[attr_map.get(field, field)] = ""

		transaction["match_found"] = False
		# Add fields required
		if transaction["country"] == "":
			transaction["country"] = "US"
		transaction["source"] = "FACTUAL"
		transaction["confidence_score"] = ""

		return transaction

	def __enrich_transaction(self, *argv):
		"""Enriches the transaction with additional data"""
		
		decision = argv[0]
		transaction = argv[1]
		top_hit = argv[2]
		name = argv[3]
		city = argv[4]
		state = argv[5]

		params = self.params
		field_names = params["output"]["results"]["fields"]
		fields_in_hit = [field for field in top_hit["_source"]]
		transaction["match_found"] = False

		# Collect Mapping Details
		attr_map = dict(zip(params["output"]["results"]["fields"], params["output"]["results"]["labels"]))

		# Enrich with found data
		if decision is True:
			transaction["match_found"] = True
			for field in field_names:
				if field in fields_in_hit:
					field_content = top_hit["_source"][field][0] if isinstance(top_hit["_source"][field],\
 						(list)) else str(top_hit["_source"][field])
					transaction[attr_map.get(field, field)] = field_content
				else:
					transaction[attr_map.get(field, field)] = ""

			if not transaction.get("country") or transaction["country"] == "":
				logging.warning(("Factual response for merchant {} has no country code. "
					"Defaulting to US.").format(top_hit["_source"]["factual_id"][0]))
				transaction["country"] = "US"
		# Add Business Name, City and State as a fallback
		if decision is False:
			for field in field_names:
				transaction[attr_map.get(field, field)] = ""
			transaction["merchant_name"] = name
			transaction["city"] = city
			transaction["state"] = state
			#Ensuring that there is a country code that matches the schema limitation
			transaction["country"] = "US"

		# Ensure Proper Casing
		if transaction[attr_map['name']] == transaction[attr_map['name']].upper():
			transaction[attr_map['name']] = string.capwords(transaction[attr_map['name']], " ")

		# Add Source
		index = params["elasticsearch"]["index"]
		transaction["source"] = "FACTUAL" if (("factual" in index) and
			(transaction["match_found"] is True)) else "OTHER"

		# Add "confidence_score" to the output schema.
		transaction["confidence_score"] = ""

		return transaction

	@staticmethod
	def __geo_fallback(city_names, state_names, transaction, attr_map):
		"""Basic logic to obtain a fallback for city and state
		when no factual_id is found"""
		city_names = city_names[0:2]
		state_names = state_names[0:2]
		states_equal = state_names.count(state_names[0]) == len(state_names)
		city_in_transaction = (city_names[0].lower() in transaction["description"].lower())
		state_in_transaction = (state_names[0].lower() in transaction["description"].lower())

		if city_in_transaction:
			transaction[attr_map['locality']] = city_names[0]

		if states_equal and state_in_transaction:
			transaction[attr_map['region']] = state_names[0]

		return transaction

	def __business_name_fallback(self, business_names, transaction, attr_map):
		"""Basic logic to obtain a fallback for business name
		when no factual_id is found"""
		business_names = business_names[0:2]
		top_name = business_names[0].lower()
		all_equal = business_names.count(business_names[0]) == len(business_names)
		not_a_city = top_name not in self.cities

		if all_equal and not_a_city:
			transaction[attr_map['name']] = business_names[0]

		return transaction

	def __apply_category_with_merchant(self, trans):
		"""Fix category_labels based on merchant_category and subtype_category"""
		merchant_category = trans.get("CNN", {}).get("category", "").strip()

		if merchant_category == "Use Subtype Rules for Categories" or merchant_category == "":
			# No valid merchant_category
			if trans["category_labels"] == ["Other Income"] or \
			   trans["category_labels"] == ["Other Expenses"]:
				subtype_category = trans.get("subtype_CNN", {}).get("category", \
								   trans.get("subtype_CNN", {}).get("label", ""))
				if isinstance(subtype_category, dict):
					subtype_category = subtype_category[trans["ledger_entry"].lower()]
				if subtype_category != "":
					trans["category_labels"] = [subtype_category]
		else:
			# Has an valid merchant_category
			trans["category_labels"] = [merchant_category]

		trans["CNN"] = trans.get("CNN", {}).get("label", "")
		trans.pop("subtype_CNN", None)

		return trans

	def __apply_category(self, transactions):
		"""Fix category_labels with category_cnn"""
		json_obj = open('meerkat/web_service/config/category.json')
		json_data = json.loads(json_obj.read())
		bank_credit = json_data['bank_credit']
		card_credit = json_data['card_credit']
		bank_debit = json_data['bank_debit']
		card_debit = json_data['card_debit']

		for trans in transactions:
			try:
				category = trans['category_labels'][0]
			except IndexError:
				if trans['ledger_entry'] == 'credit':
					category = 'Other Income'
				else:
					category = 'Other Expenses'

			if trans['ledger_entry'] == 'credit' and trans['container'] == 'bank' and \
				category in bank_credit:
				self.__apply_category_with_merchant(trans)
			elif trans['ledger_entry'] == 'credit' and trans['container'] == 'card' and \
				category in card_credit:
				self.__apply_category_with_merchant(trans)
			elif trans['ledger_entry'] == 'debit' and trans['container'] == 'bank' and \
				category not in bank_debit:
				self.__apply_category_with_merchant(trans)
			elif trans['ledger_entry'] == 'debit' and trans['container'] == 'card' and \
				category not in card_debit:
				self.__apply_category_with_merchant(trans)
			else:
				trans['CNN'] = trans.get('CNN', {}).get('label', '')
				trans.pop('subtype_CNN', None)

			trans['search'] = {'category_labels': trans.get('category_labels', [])}

		return transactions

	def ensure_output_schema(self, transactions, debug):
		"""Clean output to proper schema"""

		# Collect Mapping Details
		fields = self.params["output"]["results"]["fields"]
		labels = self.params["output"]["results"]["labels"]
		attr_map = dict(zip(fields, labels))

		# Override / Strip Fields
		for trans in transactions:
			if trans["is_physical_merchant"]:
				trans["chain_name"] = trans.get("chain_name", "")
				trans["confidence_score"] = trans.get("confidence_score", "")
				trans["country"] = trans.get("country", "")
				trans["fax_number"] = trans.get("fax_number", "")
				trans["latitude"] = trans.get("latitude", "")
				trans["longitude"] = trans.get("longitude", "")
				trans["match_found"] = trans.get("match_found", False)
				trans["neighbourhood"] = trans.get("neighbourhood", "")
				trans["phone_number"] = trans.get("phone_number", "")
				trans["postal_code"] = trans.get("postal_code", "")
				trans["source"] = trans.get("source", "OTHER")
				trans["source_merchant_id"] = trans.get("source_merchant_id", "")
				trans["store_id"] = trans.get("store_id", "")
				trans["street"] = trans.get("street", "")
				trans["txn_sub_type"] = trans.get("txn_sub_type", "")
				trans["txn_type"] = trans.get("txn_type", "")
				trans["website"] = trans.get("website", "")

			trans["city"] = trans.get("city", "")
			trans["state"] = trans.get("state", "")
			trans["transaction_id"] = trans.get("transaction_id", None)
			trans["is_physical_merchant"] = trans.get("is_physical_merchant", "")
			trans["merchant_name"] = trans.get("merchant_name", "")
			trans["txn_sub_type"] = trans.get("txn_sub_type", "")
			trans["txn_type"] = trans.get("txn_type", "")

			if debug and trans.get("is_physical_merchant", None):
				trans["search"]["merchant_name"] = trans["merchant_name"]
				trans["search"]["street"] = trans["street"]
				trans["search"]["city"] = trans["city"]
				trans["search"]["country"] = trans["country"]
				trans["search"]["state"] = trans["state"]
				trans["search"]["postal_code"] = trans["postal_code"]
				trans["search"]["source_merchant_id"] = trans["source_merchant_id"]
				trans["search"]["store_id"] = trans["store_id"]
				trans["search"]["latitude"] = trans["latitude"]
				trans["search"]["longitude"] = trans["longitude"]
				trans["search"]["website"] = trans["website"]
				trans["search"]["phone_number"] = trans["phone_number"]
				trans["search"]["fax_number"] = trans["fax_number"]
				trans["search"]["chain_name"] = trans["chain_name"]
				trans["search"]["neighbourhood"] = trans["neighbourhood"]
			else:
				trans.pop("search", None)

			# Override output with CNN v1
			if trans.get("CNN", "") != "":
				trans[attr_map["name"]] = trans.get("CNN", "")

			# Override Locale with Bloom Results
			# Add city and state to each transaction
			if trans.get("locale_bloom", None) != None:
				trans["city"] = trans["locale_bloom"][0]
				trans["state"] = trans["locale_bloom"][1]
				if trans["is_physical_merchant"]:
					trans["country"] = "US"
			else:
				trans["city"] = ""
				trans["state"] = ""

			if debug:
				trans["bloom_filter"] = {"city": trans["city"], "state": trans["state"]}
				trans["cnn"] = {"txn_type" : trans.get("txn_type", ""),
					"txn_sub_type" : trans.get("txn_sub_type", ""),
					"merchant_name" : trans.pop("CNN", ""),
					"category_labels" : [trans["category_CNN"].get("label", "")],
					"merchant_score" : trans.get("merchant_score", "0.0"),
					"subtype_score" : trans.get("subtype_score", "0.0"),
					"category_score" : trans.get("category_score", "0.0")
					}

			trans.pop("locale_bloom", None)
			trans.pop("description", None)
			trans.pop("amount", None)
			trans.pop("date", None)
			trans.pop("ledger_entry", None)
			trans.pop("CNN", None)
			trans.pop("container", None)
			trans.pop("category_CNN", None)
			trans.pop("merchant_score", None)
			trans.pop("subtype_score", None)
			trans.pop("category_score", None)
			trans.pop("Predicted", None)
			trans.pop("Processed", None)

		# return transactions

	def __enrich_physical(self, transactions):
		"""Enrich physical transactions with Meerkat"""
		if len(transactions) == 0:
			return transactions

		enriched, queries = [], []
		index = self.params["elasticsearch"]["index"]

		for trans in transactions:
			query = self.__get_query(trans)

			header = {"index": index}
			# add routing to header
			if self.params["routed"] and trans.get("locale_bloom", None):
				region = trans["locale_bloom"][1]
				header["routing"] = region.upper()

			queries.append(header)
			queries.append(query)

		queries = '\n'.join(map(json.dumps, queries))
		results = self.__search_index(queries)

		# Error Handling
		if results is None:
			return transactions

		results = results['responses']

		for result, transaction in zip(results, transactions):
			trans_plus = self.__process_results(result, transaction)
			enriched.append(trans_plus)

		return enriched

	@staticmethod
	def __sws(data):
		"""Split transactions into physical and non-physical"""
		physical, non_physical = [], []

		# Determine Whether to Search
		for trans in data["transaction_list"]:
			classifier = BANK_SWS if (data["container"] == "bank") else CARD_SWS
			label = classifier(trans["description"])
			trans["is_physical_merchant"] = True if (label == "1") else False
			(non_physical, physical)[label == "1"].append(trans)

		return physical, non_physical

	def __apply_merchant_cnn(self, data):
		"""Apply the merchant CNN to transactions"""

		if "cobrand_region" in data:
			region = 'region_' + str(data["cobrand_region"])
		else:
			region = 'default'

		classifier = None
		if data["container"] == "bank":
			if 'bank_merchant_' + region + '_cnn' not in self.models:
				classifier = self.models['bank_merchant_cnn']
			else:
				classifier = self.models['bank_merchant_' + region + '_cnn']
		else:
			if 'card_merchant_' + region + '_cnn' not in self.models:
				classifier = self.models['card_merchant_cnn']
			else:
				classifier = self.models['card_merchant_' + region + '_cnn']
		return classifier(data["transaction_list"], label_only=False)

	def __apply_subtype_cnn(self, data):
		"""Apply the subtype CNN to transactions"""

		if len(data["transaction_list"]) == 0:
			return data["transaction_list"]

		if "cobrand_region" in data:
			region = 'reigion_' + str(data["cobrand_region"])
		else:
			region = 'default'

		if data["container"] == "card":
			if 'card_credit_subtype_' + region + '_cnn' not in self.models:
				credit_subtype_classifer = self.models['card_credit_subtype_cnn']
			else:
				credit_subtype_classifer = self.models['card_credit_subtype_' + region + '_cnn']
			if 'card_debit_subtype_' + region + '_cnn' not in self.models:
				debit_subtype_classifer = self.models['card_debit_subtype_cnn']
			else:
				debit_subtype_classifer = self.models['card_debit_subtype_' + region + '_cnn']
		elif data["container"] == "bank":
			if 'bank_credit_subtype_' + region + '_cnn' not in self.models:
				credit_subtype_classifer = self.models['bank_credit_subtype_cnn']
			else:
				credit_subtype_classifer = self.models['bank_credit_subtype_' + region + '_cnn']
			if 'bank_debit_subtype_' + region + '_cnn' not in self.models:
				debit_subtype_classifer = self.models['bank_debit_subtype_cnn']
			else:
				debit_subtype_classifer = self.models['bank_debit_subtype_' + region + '_cnn']

		# Split transactions into groups
		credit, debit = [], []

		for transaction in data["transaction_list"]:
			if transaction["ledger_entry"] == "credit":
				credit.append(transaction)
			if transaction["ledger_entry"] == "debit":
				debit.append(transaction)

		# Apply classifiers
		if len(credit) > 0:
			credit_subtype_classifer(credit, label_key="subtype_CNN", label_only=False)
		if len(debit) > 0:
			debit_subtype_classifer(debit, label_key="subtype_CNN", label_only=False)

		# Split label into type and subtype
		for transaction in data["transaction_list"]:

			label = transaction["subtype_CNN"].get("label", "")

			if " - " not in label:
				if transaction["ledger_entry"] == "debit":
					label = "Other Expenses - Debit"
				elif transaction["ledger_entry"] == "credit":
					if data["container"] == "bank":
						label = "Other Income - Credit"
					elif data["container"] == "card":
						label = "Bank Adjustment - Adjustment"
				else:
					label = " - "
			
			txn_type, txn_sub_type = label.split(" - ")
			transaction["txn_type"] = txn_type
			transaction["txn_sub_type"] = txn_sub_type

		return data["transaction_list"]

	def __apply_category_cnn(self, data):
		"""Apply the category CNN to transactions"""

		if len(data["transaction_list"]) == 0:
			return data["transaction_list"]

		if "cobrand_region" in data:
			region = 'region_' + str(data["cobrand_region"])
		else:
			region = 'default'

		if data["container"] == "card":
			if 'card_credit_category_' + region + '_cnn' not in self.models:
				credit_category_classifer = self.models['card_credit_category_cnn']
			else:
				credit_category_classifer = self.models['card_credit_category_' + region + '_cnn']
			if 'card_debit_category_' + region + '_cnn' not in self.models:
				debit_category_classifer = self.models['card_debit_category_cnn']
			else:
				debit_category_classifer = self.models['card_debit_category_' + region + '_cnn']
		elif data["container"] == "bank":
			if 'bank_credit_category_' + region + '_cnn' not in self.models:
				credit_category_classifer = self.models['bank_credit_category_cnn']
			else:
				credit_category_classifer = self.models['bank_credit_category_' + region + '_cnn']
			if 'bank_debit_category_' + region + '_cnn' not in self.models:
				debit_category_classifer = self.models['bank_debit_category_cnn']
			else:
				debit_category_classifer = self.models['bank_debit_category_' + region + '_cnn']

		# Split transactions into groups
		credit, debit = [], []

		for transaction in data["transaction_list"]:
			if transaction["ledger_entry"] == "credit":
				credit.append(transaction)
			if transaction["ledger_entry"] == "debit":
				debit.append(transaction)

		# Apply classifiers
		if len(credit) > 0:
			credit_category_classifer(credit, label_key="category_CNN", label_only=False)
		if len(debit) > 0:
			debit_category_classifer(debit, label_key="category_CNN", label_only=False)

		refund_transactions = []

		for transaction in data["transaction_list"]:
			category = transaction["category_CNN"].get("label", "")
			transaction["category_labels"] = [category]

			if category == "":
				transaction["category_labels"] = ["Other Expenses"]
				if transaction["ledger_entry"] == "credit":
					transaction["category_labels"] = ["Other Income"]

			# Collect refund/adjustments transactions to apply a refund transactions model soon
			if transaction["category_labels"] == ["Refunds/Adjustments"]:
				refund_transactions.append(transaction)

		return data["transaction_list"]

	@staticmethod
	def __apply_locale_bloom(data):
		""" Apply the locale bloom filter to transactions"""
		for trans in data["transaction_list"]:
			try:
				description = trans["description"]
				trans["locale_bloom"] = location_split(description)
			except KeyError:
				pass

		return data["transaction_list"]

	@staticmethod
	def __apply_category_labels(physical):
		"""Adds a 'category_labels' field to a physical transaction if found in index"""

		# Add or Modify Fields
		for trans in physical:

			categories = trans.get("category_labels", "")

			if isinstance(categories, str):
				if categories != "":
					categories = json.loads(categories)
				else:
					categories = []

			# Merge sublists into single list if any exist:
			if any(isinstance(elem, list) for elem in categories):
				categories = list(set([item for sublist in categories for item in sublist]))

			trans["category_labels"] = categories

	@staticmethod
	def __enrich_physical_no_search(transactions):
		""" When not search, enrich physical transcation with necessary fields """
		for transaction in transactions:
			transaction["merchant_name"] = ""
			transaction["source"] = "OTHER"
			transaction["match_found"] = False
		return transactions

	def __apply_cpu_classifiers(self, data):
		"""Apply all the classifiers which are CPU bound.  Written to be
		run in parallel with GPU bound classifiers."""
		for transaction in data["transaction_list"]:
			transaction["container"] = data["container"]

		services_list = data.get("services_list", [])
		if "bloom_filter" in services_list or services_list == []:
			self.__apply_locale_bloom(data)
		else:
			for transaction in data["transaction_list"]:
				transaction["locale_bloom"] = None
		physical, non_physical = self.__sws(data)

		if "search" in services_list or services_list == [] and \
		not self.params["elasticsearch"]["skip_es"]:
			physical = self.__enrich_physical(physical)
			self.__apply_category_labels(physical)
		else:
			physical = self.__enrich_physical_no_search(physical)
		return physical, non_physical

	def classify(self, data, optimizing=False):
		"""Classify a set of transactions"""
		services_list = data.get("services_list", [])
		debug = data.get("debug", False)

		# Apply Merchant CNN
		if "cnn_merchant" in services_list or services_list == []:
			self.__apply_merchant_cnn(data)

		cpu_result = self.__cpu_pool.apply_async(self.__apply_cpu_classifiers, (data, ))

		if not optimizing:
			# Apply Subtype CNN
			if "cnn_subtype" in services_list or services_list == []:
				self.__apply_subtype_cnn(data)
			else:
				# Add the filed to ensure output schema pass
				for transaction in data["transaction_list"]:
					transaction["txn_sub_type"] = ""
					transaction["txn_type"] = ""

			# Apply Category CNN
			if "cnn_category" in services_list or "cnn_subtype" in services_list or services_list == []:
				self.__apply_category_cnn(data)


		cpu_result.get() # Wait for CPU bound classifiers to finish

		if not optimizing:
			self.__apply_category(data["transaction_list"])

		self.ensure_output_schema(data["transaction_list"], debug)

		return data

if __name__ == "__main__":
	# Print a warning to not execute this file as a module
	print("This module is a Class; it should not be run from the console.")
