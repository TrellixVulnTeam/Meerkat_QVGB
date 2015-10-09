import json
import unittest
from meerkat.web_service import web_consumer
from tests.fixture import web_consumer_fixture


class WebConsumerTest(unittest.TestCase):
    """Our UnitTest class."""

    @classmethod
    def setUpClass(cls):
        web_consumer.BANK_CREDIT_SUBTYPE_CNN = web_consumer_fixture.get_mock_cnn
        web_consumer.BANK_DEBIT_SUBTYPE_CNN = web_consumer_fixture.get_mock_cnn
        web_consumer.BANK_MERCHANT_CNN = web_consumer_fixture.get_mock_cnn
        web_consumer.CARD_MERCHANT_CNN = web_consumer_fixture.get_mock_cnn
        web_consumer.BANK_SWS = web_consumer_fixture.get_mock_sws
        web_consumer.CARD_SWS = web_consumer_fixture.get_mock_sws
        web_consumer.get_es_connection = web_consumer_fixture.get_mock_esconnection

    def setUp(self):
        self.consumer = web_consumer.Web_Consumer(params=web_consumer_fixture.get_mock_params(), hyperparams=web_consumer_fixture.get_mock_hyperparams())
        return

    def tearDown(self):
        return

    def test_static_bank_category_map(self):
        """Assert that the correct static category label has been applied from the bank map"""
        transactions = web_consumer_fixture.get_transaction_bank_fallback_classifiable()

        self.consumer._Web_Consumer__apply_missing_categories(
                                                              transactions,
                                                              "bank")

        self.assertEqual(len(transactions[0]["category_labels"]), 1)
        self.assertEqual(transactions[0]["category_labels"][0], "Utilities")

    def test_static_card_category_map(self):
        """Assert that the correct static category label has been applied from the card map"""
        transactions = web_consumer_fixture.get_transaction_card_fallback_classifiable()

        self.consumer._Web_Consumer__apply_missing_categories(
                                                              transactions,
                                                              "card")

        self.assertEqual(len(transactions[0]["category_labels"]), 1)
        self.assertEqual(transactions[0]["category_labels"][0], "Restaurants/Dining")

    def test_static_subtype_category_map(self):
        """Assert that the category is applied out of the transaction subytpe fallback map when the merchant map indicates it should be"""
        transactions = web_consumer_fixture.get_transaction_subtype_fallback()

        self.consumer._Web_Consumer__apply_missing_categories(
                                                              transactions,
                                                              "bank")

        self.assertEqual(len(transactions[0]["category_labels"]), 1)
        self.assertEqual(transactions[0]["category_labels"][0], "Other Income")

    def test_catgory_not_found_subtype_fallback(self):
        """Assert that the transaction subtype is applied when it is not found in the subtype map"""
        transactions = web_consumer_fixture.get_transaction_subtype_no_fallback()

        self.consumer._Web_Consumer__apply_missing_categories(
                                                              transactions,
                                                              "bank")

        self.assertEqual(len(transactions[0]["category_labels"]), 1)
        self.assertEqual(transactions[0]["category_labels"][0], "Joseph Rules")

    def test_apply_subtype_cnn_bank(self):
        """Assert type/subtype are set on each transaction passed to the subypte CNN"""
        test_request = web_consumer_fixture.get_test_request_bank()
        request_len = len(test_request["transaction_list"])

        self.consumer._Web_Consumer__apply_subtype_CNN(test_request)

        self.assertEqual(len(test_request["transaction_list"]), request_len)
        for trans in test_request["transaction_list"]:
            self.assertEqual(trans["txn_type"], "joseph")
            self.assertEqual(trans["txn_sub_type"], "rules")

    def test_apply_merchant_cnn_bank(self):
        """Assert merchant name is set on each transaction passed to the merchant CNN"""
        test_request = web_consumer_fixture.get_test_request_bank()
        request_len = len(test_request["transaction_list"])

        self.consumer._Web_Consumer__apply_merchant_CNN(test_request)

        self.assertEqual(len(test_request["transaction_list"]), request_len)
        for trans in test_request["transaction_list"]:
            self.assertEqual(trans["CNN"], "joseph - rules")

    def test_apply_sws_classifier(self):
        """Assert all transactions are classified as physical or non-physical"""
        test_request = web_consumer_fixture.get_test_request_bank()
        request_len = len(test_request["transaction_list"])

        self.consumer._Web_Consumer__sws(test_request)

        self.assertEqual(len(test_request["transaction_list"]), request_len)
        for trans in test_request["transaction_list"]:
            self.assertTrue("is_physical_merchant" in trans)

    def test_apply_enrich_physical(self):
        """Assert transactions returned from enrich_physical have all the expected fields for a successful search"""
        self.consumer._Web_Consumer__search_index = web_consumer_fixture.get_mock_msearch
        transactions = web_consumer_fixture.get_test_transaction_list()
        # request_len = len(transactions)

        self.consumer._Web_Consumer__enrich_physical(transactions)
        for trans in transactions:
            self.assertTrue("ledger_entry" in trans)
            self.assertTrue("country" in trans)
            self.assertTrue("match_found" in trans)
            self.assertTrue("source" in trans)
            self.assertTrue("city" in trans)
            self.assertTrue("locale_bloom" in trans)
            self.assertTrue("latitude" in trans)
            self.assertTrue("street" in trans)
            self.assertTrue("state" in trans)
            self.assertTrue("longitude" in trans)
            self.assertTrue("postal_code" in trans)
            self.assertTrue("merchant_name" in trans)
            self.assertTrue("source_merchant_id" in trans)
            self.assertTrue("store_id" in trans)
            self.assertTrue("category_labels" in trans)
            self.assertTrue("description" in trans)

if __name__ == "__main__":
    unittest.main()
