#!/usr/bin/python

"""Words we wish to ignore while searching."""
STOP_WORDS = ["CHECK", "CARD", "CHECKCARD", "PAYPOINT", "PURCHASE", "LLC" ]

GENERIC_ELASTICSEARCH_QUERY = {}
GENERIC_ELASTICSEARCH_QUERY["from"] = 0
GENERIC_ELASTICSEARCH_QUERY["size"] = 10
GENERIC_ELASTICSEARCH_QUERY["fields"] = ["BUSINESSSTANDARDNAME", "HOUSE"\
, "STREET", "STRTYPE", "CITYNAME", "STATE", "ZIP", "pin.location"]
GENERIC_ELASTICSEARCH_QUERY["query"] = {}
GENERIC_ELASTICSEARCH_QUERY["query"]["bool"] = {}
GENERIC_ELASTICSEARCH_QUERY["query"]["bool"]["minimum_number_should_match"] = 1
GENERIC_ELASTICSEARCH_QUERY["query"]["bool"]["boost"] = 1.0
GENERIC_ELASTICSEARCH_QUERY["query"]["bool"]["should"] = []


