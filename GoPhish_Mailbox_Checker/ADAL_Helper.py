import adal
import requests
import logging
from GoPhish_Mailbox_Checker.Configuration_Helper import Configuration

class AzureActiveDirectory_Helper:
    def __init__(self, config):
        with open(r"./app_pass") as ap:
            _app_pass = ap.read().replace("\n","").replace("\r","")

        self._config = config
        self._resource = self._config.Resource
        self._graph_api_endpoint = self._config.Graph_API_Endpoint
        self._authority = self._config.Authority + self._config.Tenant_ID
        self.Context = adal.AuthenticationContext(self._authority)

        self.Token = self.Context.acquire_token_with_client_credentials(
            resource=self._resource,
            client_id=self._config.Client_ID,
            client_secret=_app_pass
        )

        self.Headers = {
            'Authorization' : f'Bearer {self.Token["accessToken"]}',
            'Accept' : 'application/json',
            'Content-Type' : 'application/json'
        }

    def refresh_access_token(self):
        with open(r"./app_pass") as ap:
            _app_pass = ap.read().replace("\n","").replace("\r","")
        self.Token = self.Context.acquire_token_with_client_credentials(
            resource=self._resource,
            client_id=self._config.Client_ID,
            client_secret=_app_pass
        )

        self.Headers = {
            'Authorization' : f'Bearer {self.Token["accessToken"]}',
            'Accept' : 'application/json',
            'Content-Type' : 'application/json'
        }

    def azuread_api_caller(self, location, call_type, data=None, json=None):
        '''
        API call helper function
        '''

        api_url = self._graph_api_endpoint + location

        continue_code = True

        try:
            if call_type.lower() == "get":
                api_response = requests.get(url=api_url, headers=self.Headers, json=json)
            elif call_type.lower() == "post":
                api_response = requests.post(url=api_url, headers=self.Headers, json=json)
            elif call_type.lower() == "patch":
                api_response = requests.patch(url=api_url, headers=self.Headers, json=json)
            elif call_type.lower() == "put":
                api_response = requests.put(url=api_url, headers=self.Headers, data=data, json=json)
        except Exception as error:
            logging.error(f"API Caller exception: {error}")
            continue_code = False

        if continue_code is True:
            api_json_data = api_response.json()

            if "error" in api_json_data.keys():
                if api_json_data['error']['code'] == "InvalidAuthenticationToken":
                    logging.warning("Auth Token has expired. Attempting to acquire a new one.")
                    self.refresh_access_token()
                    api_json_data = self.azuread_api_caller(location, call_type, data, json)

            if 'value' in api_json_data.keys():
                _continue = False

                if '@odata.nextLink' in api_json_data.keys():
                    nextLink = api_json_data['@odata.nextLink']

                    while _continue == False:
                        if nextLink:
                            nextLink_response = requests.get(url=nextLink, headers=self.Headers).json()
                            api_json_data['value'] = api_json_data['value'] + nextLink_response['value']

                            if '@odata.nextLink' in nextLink_response.keys():
                                nextLink = nextLink_response['@odata.nextLink']
                            else:
                                _continue = True
                        else:
                            _continue = True

                return api_json_data['value']
            else:
                return api_json_data
        else:
            return None
