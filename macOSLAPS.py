#!/usr/bin/python
'''LAPS for macOS devices
__________________________________________________________________________
| This python script will set a randomly generated password for your     |
| local adminsitrator account on macOS if the expiration date has passed |
| in your Active Directory. The results will then be written to your AD  |
| into the attribute dsAttrTypeNative:ms-Mcs-AdmPwd to mimic the same    |
| behavior of Local Administrator Password Solution (LAPS) on Windows.   |
| Once completed, an expiration date will then be set for the new        |
| password and written to the AD attribute dsAttrTypeNative:ms-Mcs-      |
| AdmPwdExpirationTime. This will allow the LAPS UI to be utilized and   |
| the random password the ability to be seen by those with permission to |
| retrieve it.                                                           |
|________________________________________________________________________|
Joshua D. Miller - josh@psu.edu - The Pennsylvania State University
Script was Last Updated July 8, 2016

Preference code from Jaharmi's Read preferences from
property list'''

from __future__ import print_function
from Foundation import CFPreferencesCopyAppValue
from random import randint, choice
from datetime import datetime, timedelta
from socket import gethostname
from string import ascii_letters, punctuation, digits
from subprocess import check_output, PIPE
from time import mktime
import logging

BUNDLE_ID = 'edu.psu.macoslaps'

DEFAULT_PREFERENCES = {
    'LocalAdminAccount': 'admin',
    'PasswordLength': 8,
    'DaysTillExpiration': 60
}


def main():
    '''main function'''
    # Log
    logging.basicConfig(filename='/Library/Logs/macOSLAPS.log',
                        level=logging.DEBUG,
                        format='%(asctime)s|%(levelname)s:%(message)s')
    # Get the current time
    now = datetime.now()
    # Local Admin Account
    admin = get_config_settings('LocalAdminAccount')
    # Days till expiration
    exp_days = get_config_settings('DaysTillExpiration')
    # Get Domain Name
    domain = check_output(['/usr/bin/dscl', '/Active Directory/',
                           '-read', '/', 'SubNodes'], stderr=PIPE)[10:-1]
    # Password Length
    pass_length = get_config_settings('PasswordLength')
    # Get Computer Hostname
    computer = gethostname()
    # Active Directory Path
    ad_path = '/Active Directory/{0:}/All Domains'.format(domain)
    # Computer Path
    computer_path = 'Computers/{0:}$'.format(computer)
    # LAPS Attributes
    attributes = dict()
    attributes[0] = 'dsAttrTypeNative:ms-Mcs-AdmPwd'
    attributes[1] = 'dsAttrTypeNative:ms-Mcs-AdmPwdExpirationTime'
    # Get Expiration Time of Password
    try:
        expiration_time = check_output(['/usr/bin/dscl', ad_path, '-read',
                                        computer_path, attributes[1]],
                                       stderr=PIPE)
    except StandardError as error:
        logging.error(error)
        exit(1)
    # Convert Windows Time to Epoch Time
    format_expiration_time = (int(expiration_time[46:])/10000000-11644473600)
    # Change to TimeStamp
    format_expiration_time = datetime.fromtimestamp(format_expiration_time)
    # Determine if the password expired and then change it
    if format_expiration_time < now:
        # Log that the password change is being started
        logging.info('Password change required. Performing password change..')
        # Characters used for random password
        characters = ascii_letters + punctuation + digits
        # Create random password
        password = "".join(choice(characters)
                           for x in range(randint(pass_length, pass_length)))
        try:
            # Remove AD LAPS Password using Computer Account
            logging.info('Removing old password from Active Directory...')
            check_output(['/usr/bin/dscl', ad_path, '-delete',
                          computer_path, attributes[0]], stderr=PIPE)
            # Change the local admin password
            logging.info('Setting random password for local'
                         ' admin account %s', admin)
            check_output(['/usr/bin/dscl', '.', 'passwd',
                          '/Users/{0:}'.format(admin), password], stderr=PIPE)
            # Re-add the LAPS Password using Computer Account
            logging.info('Writing new password to Active Directory...')
            check_output(['/usr/bin/dscl', ad_path, '-append', computer_path,
                          attributes[0], password], stderr=PIPE)
            # Convert the time back from Time Stamp to Epoch to Windows
            # and add 30 days onto the time
            new_expiration_time = (now + timedelta(days=exp_days))
            format_new_expiration_time = new_expiration_time
            new_expiration_time = new_expiration_time.timetuple()
            new_expiration_time = mktime(new_expiration_time)
            new_expiration_time = ((new_expiration_time+11644473600)*10000000)
            # Set the Expiration Time to 30 days from now in AD
            logging.info('Removing expiration time from Active Directory...')
            check_output(['/usr/bin/dscl', ad_path, '-delete', computer_path,
                          attributes[1]], stderr=PIPE)
            logging.info('Settings new expiration time...')
            check_output(['/usr/bin/dscl', ad_path, '-append', computer_path,
                          attributes[1], str(int(new_expiration_time))],
                         stderr=PIPE)
            logging.info('Password change has been completed. '
                         'New expiration date is %s',
                         format_new_expiration_time)
        except StandardError as error:
            logging.error(error)
            exit(1)
    else:
        # Log that a password change is not necessary at this time
        logging.info('Password change not necessary at this time as'
                     ' the expiration date is %s', format_expiration_time)


def get_config_settings(preference_key, preference_file=BUNDLE_ID):
    '''Function to retrieve configuration settings from
    /Library/Preferences or /Library/Managed Preferences'''
    preference_value = CFPreferencesCopyAppValue(preference_key,
                                                 preference_file)
    if preference_value == None:
        preference_value = DEFAULT_PREFERENCES.get(preference_key)
    return preference_value

if __name__ == '__main__':
    main()
