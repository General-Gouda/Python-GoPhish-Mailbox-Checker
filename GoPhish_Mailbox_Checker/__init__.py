import re
import requests
import logging
from GoPhish_Mailbox_Checker.ADAL_Helper import AzureActiveDirectory_Helper
from GoPhish_Mailbox_Checker.Configuration_Helper import Configuration
from GoPhish_Mailbox_Checker.Email_Helper import gophish_folder_message_checker, email_category_setup_checker, gophish_folder_checker, gophish_folder_reset

def main():
    # Pulls in configuration from config.json file
    logging.debug("Extracting configuration from config.json.")
    config = Configuration()

    # Connects to Azure AD and acquires token through Azure AD app
    logging.debug("Authenticating to Azure AD.")
    ad_helper = AzureActiveDirectory_Helper(config=config)

    # Ensures that email categories are set up on target mailbox
    email_category_setup_checker(
        ad_helper=ad_helper,
        config=config
    )

    # Ensures that folder containing reported phishing emails is present
    gophish_folder_id = gophish_folder_checker(
        ad_helper=ad_helper,
        config=config
    )

    # If the folder id is found run the gophish_folder_message_checker function
    if gophish_folder_id:
        gophish_folder_message_checker(
            gophish_folder_id=gophish_folder_id,
            ad_helper=ad_helper,
            config=config
        )
    else:
        logging.warning(f"Folder {config.Mail_Folder_To_Check} not found in mailbox {config.Mailbox}.")

    logging.info("Application run complete.")