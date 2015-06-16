"""
Scrape all parole hearing data for NYS.
"""

import csv
import scrapelib
import sys
import argparse
from bs4 import BeautifulSoup
from string import ascii_uppercase
from time import localtime, mktime
from datetime import datetime
from dateutil import parser as dateparser

import parole_hearing_utils as utils

ROOT_URL = 'http://161.11.133.89/ParoleBoardCalendar'
DETAIL_URL = ROOT_URL + '/details.asp?nysid={number}'
INTERVIEW_URL = ROOT_URL + '/interviews.asp?name={letter}&month={month}&year={year}'
FORBIDDEN_HEADERS = [u'inmate name']


#def get_existing_parolees(path):
    #"""
    #Load in existing parole hearing data from provided path.  Turns into a
    #dict, indexed by DIN and parole board interview date.
    #"""
    #parolees = {}
    #with open(path, 'rU') as csvfile:
        #for row in csv.DictReader(csvfile, delimiter=',', quotechar='"'):

            ## Ensure row is lowercased (this caused issues with legacy data)
            #lc_row = {}
            #for key, value in row.iteritems():
                #key = key.lower()
                #if value:
                    #if key in lc_row:
                        #if lc_row[key]:
                            #raise Exception("Duplicate values in similar keys")
                    #lc_row[key] = value

            #parolees[(row[u"din"], row[u"parole board interview date"])] = lc_row
    #return parolees


def baseurls():
    """
    Provide URLs for the calendar going back 24 months and forward 6 months via
    generator.  Yields the URL, then the year and month it's for.
    """
    today = localtime()
    for monthdiff in xrange(-25, 7):
        year, month = localtime(mktime(
            [today.tm_year, today.tm_mon + monthdiff, 1, 0, 0, 0, 0, 0, 0]))[:2]
        for letter in ascii_uppercase:
            yield (INTERVIEW_URL.format(letter=letter, month=str(month).zfill(2), year=year),
                   year, month)


def get_general_parolee_keys(scraper, url):
    """
    Obtains a list of the standard parolee data keys (table headers) from the
    specified URL.
    """
    soup = BeautifulSoup(scraper.urlopen(url))
    keys_th = soup.find('table', class_='intv').find('tr').find_all('th')
    return [unicode(key.string) for key in keys_th]



def get_headers(list_of_dicts):
    """
    Returns a set of every different key in a list of dicts.
    """
    return set().union(*[l.keys() for l in list_of_dicts])


# pylint: disable=too-many-locals
def scrape_interviews(scraper):
    """
    Scrape all interviews.  Returns a list of parolees, with minimal data,
    from these hearings.
    """
    parolees = []
    parolee_keys = None

    for url, year, month in baseurls():
        sys.stderr.write(url + '\n')

        soup = BeautifulSoup(scraper.urlopen(url))

        # All parolees are within the central table.
        parolee_table = soup.find('table', class_="intv")
        if not parolee_table:
            continue

        if parolee_keys is None:
            parolee_keys = get_general_parolee_keys(scraper, url)

        # Splitting out into one line per parolee.
        parolee_tr = parolee_table.find_all('tr')
        for row in parolee_tr:
            cells = row.find_all('td')
            if not cells:
                continue
            parolee = {}
            for i, cell in enumerate(cells):
                key = parolee_keys[i].lower()
                value = cell.string.strip()
                if "date" in key and value:
                    try:
                        value = datetime.strftime(dateparser.parse(value), '%Y-%m-%d')
                    except (ValueError, TypeError):
                        pass
                parolee[key] = value
            parolees.append(parolee)

        # Keep track of originally scheduled month/year
        if parolee[u"parole board interview date"] == u'*':
            parolee[u"parole board interview date"] = u'{}-{}-*'.format(
                year, month)

    return parolees
# pylint: enable=too-many-locals


# pylint: disable=too-many-locals
def scrape_details(scraper, parolee_input):
    """
    Scrape details for specified parolees.  Returns the same list, with
    additional data.
    """
    out = []
    for existing_parolee in parolee_input:
        parolee = existing_parolee.copy()
        if len(parolee) <= 1:
            # Some blank rows sneak in; let's skip them.
            continue

        url = DETAIL_URL.format(number=parolee['nysid'])
        sys.stderr.write(url + '\n')

        soup = BeautifulSoup(scraper.urlopen(url, timeout=5))
        detail_table = soup.find('table', class_="detl")
        if not detail_table:
            continue

        crimes = soup.find('table', class_="intv").find_all('tr')
        crime_titles = [u"crime {} - " + unicode(th.string)
                        for th in soup.find('table', class_="intv").find_all('th')]

        for row in detail_table:
            key, value = row.getText().split(":")
            # we don't need to capture the nysid, name, or din again
            key = key.lower()
            if "nysid" in key or "name" in key or "din" in key:
                continue
            if "date" in key and value:
                try:
                    value = datetime.strftime(dateparser.parse(value), '%Y-%m-%d')
                except (ValueError, TypeError):
                    pass
            parolee[key] = value.strip().replace(u'\xa0', u'')

        for crime_num, crime in enumerate(crimes[1:]):
            title = [ct.format(crime_num + 1) for ct in crime_titles]
            i = 0
            while i < len(crime):
                parolee[title[i].lower()] = crime.find_all('td')[i].string.strip()
                i += 1

        out.append(parolee)

    return out
# pylint: enable=too-many-locals

def scrape(old_data_path, no_download):
    """
    Main function -- read in existing data, scrape new data, merge the two
    sets, and save to the output location.
    """
    scraper = scrapelib.Scraper(requests_per_minute=180,
                                retry_attempts=5, retry_wait_seconds=15)

    if old_data_path:
        existing_parolees = utils.get_existing_parolees(old_data_path)
    else:
        existing_parolees = {}

    if no_download:
        new_parolees = []
    else:
        new_parolees = scrape_interviews(scraper)
        new_parolees = scrape_details(scraper, new_parolees)

    for parolee in new_parolees:
        din = parolee[u"din"]
        interview_date = parolee[u"parole board interview date"]
        key = (din, interview_date)

        # Clear out any hearing date that corresponds to a hearing that hadn't
        # yet happened.  This occurs because specific dates aren't set in
        # advance -- only a month and year.  This is notated via the date
        # "YYYY-MM-*".  However, once the interview has happened, we have
        # a date and should replace that row.
        scheduled_date = '-'.join(interview_date.split('-')[0:2]) + '-*'
        scheduled_key = (din, scheduled_date)
        if key != scheduled_key:
            if scheduled_key in existing_parolees:
                del existing_parolees[scheduled_key]

        existing_parolees[key] = parolee

    utils.print_data(existing_parolees.values())


if __name__ == '__main__':
    PARSER = argparse.ArgumentParser()
    PARSER.add_argument('input', help=u"Path to input data", nargs='?')
    PARSER.add_argument('-n', '--no-download', help=u"Don't download anything"
                        " new, simply re-process input data.",
                        action='store_true')
    ARGS = PARSER.parse_args()
    scrape(ARGS.input, ARGS.no_download)
