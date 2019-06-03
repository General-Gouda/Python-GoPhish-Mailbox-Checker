'''
A Gophish tool

This utility checks a specific mailbox for new emails,
checks the attached email file for specific headers or URLs
related to a Gophish server or campaign. If it finds one the
program will gather the URL, transform it into a REPORT URL and
send a GET request to it to mark the email as reported.

By: Matt Marchese
'''

import logging, os, sys
import GoPhish_Mailbox_Checker
from time import sleep
from datetime import datetime, time
from GoPhish_Mailbox_Checker.Configuration_Helper import Configuration

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.realpath(sys.argv[0])))

    config = Configuration()
    log_location = config.Log_Location
    log_file_name = "Gophish_mailbox_checker.log"

    if not os.path.exists(log_location):
        os.mkdir(log_location)

    if not os.path.isfile(os.path.join(log_location, log_file_name)):
        open(os.path.join(log_location, log_file_name), 'a').close()

    # Logging Setup
        # Log Levels for reference:
        #     CRITICAL = 50
        #     FATAL = CRITICAL
        #     ERROR = 40
        #     WARNING = 30
        #     WARN = WARNING
        #     INFO = 20
        #     DEBUG = 10
        #     NOTSET = 0

    logging.basicConfig(
        format='[ %(asctime)s | %(levelname)s ] %(message)s',
        datefmt='%m/%d/%Y %I:%M:%S %p',
        filename=os.path.join(
            log_location,
            log_file_name
        ),
        level=config.Log_Level
    )
    logging.getLogger().addHandler(logging.StreamHandler())
    logging.info("Log initialized.")

    if config.Run_Once:
        GoPhish_Mailbox_Checker.main()
    else:
        while True:
            # Indefinitely run the program after it completes its last run.
            GoPhish_Mailbox_Checker.main()
            sleep(config.Run_Interval_Timer)

