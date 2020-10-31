#!/usr/bin/python

def pluck(collection, key):
	'''
	extract x[key] for every item x in the collection
	'''
	return [x[key] for x in collection]

def yesno(value, icaps=False):
	"""
	Return 'yes' or 'no' according to the (assumed-bool) value.
	"""

	if (value):
		str = 'Yes' if icaps else 'yes'
	else:
		str = 'No' if icaps else 'no'

	return str


class FilterModule(object):

	def filters(self):
		return {
			'yesno': yesno,
			'pluck': pluck
		}
