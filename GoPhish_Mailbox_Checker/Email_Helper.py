import os
import re
import requests
import logging
import multiprocessing
from concurrent.futures import ThreadPoolExecutor
from functools import partial

def email_category_setup_checker(ad_helper, config):
    logging.debug("Retrieving mailbox's master categories.")
    master_categories = ad_helper.azuread_api_caller(
        location=f"/users/{config.Mailbox}/outlook/masterCategories",
        call_type="get"
    )

    if config.Gophish_Category['Name'] not in [category['displayName'] for category in master_categories]:
        logging.info(f"Message category {config.Gophish_Category['Name']} not found. Creating it.")
        category_creation_body = {
            "displayName": config.Gophish_Category['Name'],
            "color": config.Gophish_Category['Color']
        }

        ad_helper.azuread_api_caller(
            location=f"/users/{config.Mailbox}/outlook/masterCategories",
            call_type="post",
            json=category_creation_body
        )

def gophish_folder_checker(ad_helper, config):
    logging.debug("Retrieving mailbox's mail folders.")
    mail_folders = ad_helper.azuread_api_caller(
        location=f'/users/{config.Mailbox}/mailFolders',
        call_type="get"
    )

    logging.debug(f"Looking for the existence of mail folder {config.Mail_Folder_To_Check}.")
    if config.Mail_Folder_To_Check not in [folder['displayName'] for folder in mail_folders]:
        logging.info(f"Mail folder {config.Mail_Folder_To_Check} was not found. Creating it.")
        create_folder = {
            'displayName': config.Mail_Folder_To_Check
        }

        ad_helper.azuread_api_caller(
            location=f'/users/{config.Mailbox}/mailFolders',
            call_type="post",
            json=create_folder
        )

        logging.info(f"Mail folder {config.Mail_Folder_To_Check} successfully created.")

        mail_folders = ad_helper.azuread_api_caller(
            location=f'/users/{config.Mailbox}/mailFolders',
            call_type="get"
        )
    else:
        logging.debug(f"Mail folder {config.Mail_Folder_To_Check} was located.")

    gophish_folder_id = None

    logging.debug(f"Retrieving mail folder {config.Mail_Folder_To_Check}'s ID")
    for folder in mail_folders:
        if folder['displayName'] == config.Mail_Folder_To_Check:
            gophish_folder_id = folder['id']

    return gophish_folder_id

def message_checker(email_object, ad_helper, config):
    # If the email is unread, has an attachment and is not flagged then proceed...
    if email_object['isRead'] == False and email_object['hasAttachments'] == True and re.match('notFlagged', email_object['flag']['flagStatus']):
        # Extract attachment data
        attachments = ad_helper.azuread_api_caller(
            location=f"/users/{config.Mailbox}/messages/{email_object['id']}/attachments",
            call_type="get"
        )

        for attachment in attachments:
            # Extract email data (like headers, sender, recipients, etc) from message attachments
            attachment_info = ad_helper.azuread_api_caller(
                location=f"/users/{config.Mailbox}/messages/{email_object['id']}/attachments/{attachment['id']}/?$expand=microsoft.graph.itemattachment/item",
                call_type="get"
            )

            # The 'item' key should only exist on message attachments...(I think)
            if 'item' in attachment_info.keys():
                # Extract the Gophish url from the Gophish Header specified in the config file
                # and transforms it into the report URL.
                gophish_report_url = ", ".join(
                    [
                        header['value']
                        for header in attachment_info['item']['internetMessageHeaders']
                        if header['name'] == config.Gophish_URL_Header
                    ]
                )

                if gophish_report_url:
                    logging.info(f"Gophish email located with ID {email_object['id']}. Extracting URL from header, transforming into report URL and sending GET request to it.")

                    if not re.match("/report", gophish_report_url):
                        gophish_report_url = gophish_report_url.replace("?rid=","/report?rid=")

                    # Sends a simple HTTP GET request to the report URL to mark email as reported in Gophish.
                    reported_response = requests.get(url=gophish_report_url)

                    # If there is a successful response to reporting the email then mark the email as read, flagged and categorized.
                    if re.match("20[0-9]", str(reported_response.status_code)):
                        logging.info(f"Marking email as read, completed and categorized as {config.Gophish_Category['Name']}.")
                        update_email = {
                            'isRead' : True,
                            'categories': [
                                config.Gophish_Category['Name']
                            ],
                            'flag': {
                                'flagStatus': 'complete'
                            }
                        }

                        ad_helper.azuread_api_caller(
                            location=f"/users/{config.Mailbox}/messages/{email_object['id']}",
                            call_type="patch",
                            json=update_email
                        )
                else:
                    # If the Gophish header is not found and the email is not flagged mark it as flagged.
                    if not re.match("flagged|complete", email_object['flag']['flagStatus']):
                        logging.debug("Flagging non-Gophish email.")
                        update_email = {
                            'flag': {
                                'flagStatus': 'flagged'
                            }
                        }

                        ad_helper.azuread_api_caller(
                            location=f"/users/{config.Mailbox}/messages/{email_object['id']}",
                            call_type="patch",
                            json=update_email
                        )
    else:
        # If the email is read, has no attachments and is not flagged mark it as flagged.
        if not re.match("flagged|complete", email_object['flag']['flagStatus']) and email_object['isRead'] == False:
            logging.debug("Flagging non-Gophish email.")
            update_email = {
                'flag': {
                    'flagStatus': 'flagged'
                }
            }

            ad_helper.azuread_api_caller(
                location=f"/users/{config.Mailbox}/messages/{email_object['id']}",
                call_type="patch",
                json=update_email
            )

def gophish_folder_message_checker(gophish_folder_id, ad_helper, config):
    # Checks for emails in the specified folder
    logging.debug(f"Checking for emails in {config.Mail_Folder_To_Check}")
    email_data = ad_helper.azuread_api_caller(
        location=f"/users/{config.Mailbox}/mailFolders/{gophish_folder_id}/messages?$top=200&$filter=isRead eq false and flag/flagStatus ne 'flagged'",
        call_type="get"
    )

    if email_data:
        logging.debug("Email query returned results.")

        logging.debug("Setting up ThreadPoolExecutor.")
        with ThreadPoolExecutor(max_workers=(multiprocessing.cpu_count() * 2)) as executor:
            for email_object in email_data:
                executor.submit(message_checker, email_object, ad_helper, config)

def message_resetter(email_object, ad_helper, config):
    if re.match('flagged|complete', email_object['flag']['flagStatus']):
        update_email = {
            'isRead' : False,
            'categories': [],
            'flag': {
                'flagStatus': 'notFlagged'
            }
        }

        ad_helper.azuread_api_caller(
            location=f"/users/{config.Mailbox}/messages/{email_object['id']}",
            call_type="patch",
            json=update_email
        )

def gophish_folder_reset(gophish_folder_id, ad_helper, config):
    '''
    Code you can use to reset all flagged messages back to unflagged for testing purposes:

    gophish_folder_reset(
        gophish_folder_id=gophish_folder_id,
        ad_helper=ad_helper,
        config=config
    )
    '''
    
    # Checks for emails in the specified folder
    logging.debug(f"Checking for emails in {config.Mail_Folder_To_Check}")
    email_data = ad_helper.azuread_api_caller(
        location=f"/users/{config.Mailbox}/mailFolders/{gophish_folder_id}/messages?$top=200&$filter=isRead eq false and flag/flagStatus eq 'flagged'",
        call_type="get"
    )

    if email_data:
        logging.debug("Email query returned results.")

        logging.debug("Setting up ThreadPoolExecutor.")
        with ThreadPoolExecutor(max_workers=(multiprocessing.cpu_count() * 2)) as executor:
            for email_object in email_data:
                executor.submit(message_resetter, email_object, ad_helper, config)