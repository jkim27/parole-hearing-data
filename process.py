import re, time, csv, datetime
import os, sys
import prison_list

import parole_hearing_utils as utils

def format_date(date):
  if int(date) <= 20:
    date = 2000 + int(date)
    return date
  elif int(date) > 50 and int(date) < 100:
    date = 1900 + int(date)
    return date
  else:
    return date

def get_year_of_entry(parolee):
  year_of_entry = format_date(parolee['din'][0:2])
  parolee['year of entry'] = year_of_entry
  return parolee

def set_security_level(parolee):
  """
  Takes a dictionary, finds the facility keys,
  and creates a key value pair with the security for that facility.
  """

  h_i_facility = parolee['housing or interview facility']
  h_r_facility = parolee['housing/release facility']

  h_i_sec_level = prison_list.PRISONS[h_i_facility]
  h_r_sec_level = prison_list.PRISONS[h_r_facility]

  parolee['housing/interview facility security level'] = h_i_sec_level
  parolee['housing/release facility security level'] = h_r_sec_level
  return parolee


def simplify_outcomes(parolee):
  """
  Takes a parolee, finds the outcome,
  and creates a key value pair with a simplified outcome.
  """
  
  decisions = {
      'ODOP': 'release',
      'PAROLED': 'release',
      'GRANTED': 'release',
      'REINSTATE': 'release',
      'OPEN DATE': 'release',
      'NO SUSREV': 'release',
      'DENIED': 'denial',
      'NOT GRANTD': 'denial',
      'M V NO S': 'denial',
      'M V SUS': 'denial',
      'SUST-REV': 'denial',
      'RCND&HOLD': 'ambiguous',
      'RCND&RELSE': 'ambiguous',
      'OR EARLIER': 'ambiguous'
      }
  parolee_decision = parolee['interview decision']
  if parolee_decision in decisions.keys():
      parolee['interview decision category'] = decisions[parolee_decision]
  else:
      parolee['interview decision category'] = None
  return parolee


parolees = utils.get_existing_parolees("data.csv")
for k, v in parolees.iteritems():
    parolees[k] = get_year_of_entry(v)
    parolees[k] = simplify_outcomes(v)

utils.print_data(parolees.values(), out_file = "data.csv")
