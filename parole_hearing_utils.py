import csv
import sys
from bs4 import BeautifulSoup
from string import ascii_uppercase
from time import localtime, mktime
from datetime import datetime
from dateutil import parser as dateparser

FORBIDDEN_HEADERS = [u'inmate name']

def get_existing_parolees(path):
    """
    Load in existing parole hearing data from provided path.  Turns into a
    dict, indexed by DIN and parole board interview date.
    """
    parolees = {}
    with open(path, 'rU') as csvfile:
        for row in csv.DictReader(csvfile, delimiter=',', quotechar='"'):

            # Ensure row is lowercased (this caused issues with legacy data)
            lc_row = {}
            for key, value in row.iteritems():
                key = key.lower()
                if value:
                    if key in lc_row:
                        if lc_row[key]:
                            raise Exception("Duplicate values in similar keys")
                    lc_row[key] = value

            parolees[(row[u"din"], row[u"parole board interview date"])] = lc_row
    return parolees

def fix_defective_sentence(sentence):
    """
    Most of the sentences in existing data were erroneously converted from
    "NN-NN" to "Month-NN" or "NN-Month", for example "03-00" to "Mar-00".  This
    fixes these mistakes.
    """
    if not sentence:
        return sentence
    sentence = sentence.split('-')
    month2num = {"jan": "01", "feb": "02", "mar": "03", "apr": "04",
                 "may": "05", "jun": "06", "jul": "07", "aug": "08",
                 "sep": "09", "oct": "10", "nov": "11", "dec": "12"}
    for i, val in enumerate(sentence):
        sentence[i] = month2num.get(val.lower(), ('00' + val)[-2:])
    try:
        # sometimes the min/max is flipped.
        if int(sentence[0]) > int(sentence[1]) and int(sentence[1]) != 0:
            sentence = [sentence[1], sentence[0]]
    except ValueError:
        pass
    return '-'.join(sentence)

def get_headers(list_of_dicts):
    """
    Returns a set of every different key in a list of dicts.
    """
    return set().union(*[l.keys() for l in list_of_dicts])

def reorder_headers(supplied):
    """
    Takes the supplied headers, and prefers the "expected" order.  Any
    unexpected supplied headers are appended alphabetically to the end.  Any
    expected headers not supplied are not included.
    """
    for forbidden_header in FORBIDDEN_HEADERS:
        if forbidden_header in supplied:
            supplied.remove(forbidden_header)
    headers = []
    expected = [
        "parole board interview date",
        "din",
        "scrape date",
        "nysid",
        "sex",
        "birth date",
        "race / ethnicity",
        "housing or interview facility",
        "parole board interview type",
        "interview decision",
        "year of entry",
        "aggregated minimum sentence",
        "aggregated maximum sentence",
        "release date",
        "release type",
        "housing/release facility",
        "parole eligibility date",
        "conditional release date",
        "maximum expiration date",
        "parole me date",
        "post release supervision me date",
        "parole board discharge date",
        "crime 1 - crime of conviction",
        "crime 1 - class",
        "crime 1 - county of commitment",
        "crime 2 - crime of conviction",
        "crime 2 - class",
        "crime 2 - county of commitment",
        "crime 3 - crime of conviction",
        "crime 3 - class",
        "crime 3 - county of commitment",
        "crime 4 - crime of conviction",
        "crime 4 - class",
        "crime 4 - county of commitment",
        "crime 5 - crime of conviction",
        "crime 5 - class",
        "crime 5 - county of commitment",
        "crime 6 - crime of conviction",
        "crime 6 - class",
        "crime 6 - county of commitment",
        "crime 7 - crime of conviction",
        "crime 7 - class",
        "crime 7 - county of commitment",
        "crime 8 - crime of conviction",
        "crime 8 - class",
        "crime 8 - county of commitment"
    ]
    for header in expected:
        if header in supplied:
            supplied.remove(header)
            headers.append(header)
    headers.extend(sorted(supplied))
    return headers

def print_data(parolees, out_file=None):
    """
    Prints output data to stdout, from which it can be piped to a file.  Orders
    by parole hearing date and DIN (order is important for version control.)
    """
    headers = get_headers(parolees)
    headers = reorder_headers(headers)

    # Convert date columns to SQL-compatible date format (like "2014-10-07")
    # when possible
    for parolee in parolees:
        for key, value in parolee.iteritems():
            if "inmate name" in key:
                continue
            if "date" in key.lower() and value:
                try:
                    parolee[key] = datetime.strftime(dateparser.parse(value), '%Y-%m-%d')
                except (ValueError, TypeError):
                    parolee[key] = value
            elif "sentence" in key.lower():
                parolee[key] = fix_defective_sentence(value)
        if 'scrape date' not in parolee:
            parolee['scrape date'] = datetime.strftime(datetime.now(), '%Y-%m-%d')

    parolees = sorted(parolees, key=lambda x: (x[u"parole board interview date"], x[u"din"]))
    if out_file:
        with open(out_file, 'wb') as f:
            out = csv.DictWriter(f, fieldnames=headers)
            out.writeheader()
            out.writerows(parolees)
    else:
        out = csv.DictWriter(sys.stdout, extrasaction='ignore',
                             delimiter=',', fieldnames=headers)
        out.writeheader()
        out.writerows(parolees)
