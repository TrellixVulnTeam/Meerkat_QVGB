#!/usr/local/bin/python3
"""This module loads our general classifier."""

from sklearn.externals import joblib

def select_model(mode):
	"""Load either Card or Bank classifier depending on
	requested model"""

	# Switch on Models
	if mode == "card":
		print("--- Classifying Transactions in Card Mode ---")
		model_path = "meerkat/binary_classifier/models/final_card.pkl"
	elif mode == "bank":
		print("--- Classifying Transactions in Bank Mode ---")
		model_path = "meerkat/binary_classifier/models/final_bank.pkl"
	else:
		print("--- Binary Classifier requested not found. Terminating ---")
		sys.exit()

	# Load Model
	model = joblib.load(model_path)

	# Generate Helper Function
	def classifier(description=None):
		result = list(model.predict([description]))[0]
		return result
			
	return classifier