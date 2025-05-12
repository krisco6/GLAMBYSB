# myproject/backends.py
import msal
import requests
from django.core.mail.backends.base import BaseEmailBackend
from django.conf import settings

class GraphEmailBackend(BaseEmailBackend):
    """
    A Django EmailBackend that sends messages via Microsoft Graph instead of SMTP.
    """

    def get_ms_graph_token(self):
        """
        Acquire a token from Microsoft Graph using msal.
        """
        app = msal.ConfidentialClientApplication(
            client_id=settings.MS_GRAPH_CLIENT_ID,
            authority=f"https://login.microsoftonline.com/{settings.MS_GRAPH_TENANT_ID}",
            client_credential=settings.MS_GRAPH_CLIENT_SECRET
        )
        result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
        if "access_token" in result:
            return result["access_token"]
        else:
            raise Exception(f"Failed to obtain Graph token: {result}")

    def send_messages(self, email_messages):
        """
        Sends one or more EmailMessage objects via Microsoft Graph.
        Returns the number of successfully sent messages.
        """
        if not email_messages:
            return 0

        token = self.get_ms_graph_token()
        from_address = getattr(settings, 'DEFAULT_FROM_EMAIL', 'manoj.challapalli@kriscosales.com')
        endpoint = f"https://graph.microsoft.com/v1.0/users/{from_address}/sendMail"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        sent_count = 0
        for message in email_messages:
            # Convert Django EmailMessage to Graph API format
            subject = message.subject
            body = message.body
            # 'html' or 'text'?
            content_type = "HTML"

            # Build recipients
            to_recipients = [{"emailAddress": {"address": addr}} for addr in message.to]
            cc_recipients = [{"emailAddress": {"address": addr}} for addr in message.cc]
            bcc_recipients = [{"emailAddress": {"address": addr}} for addr in message.bcc]

            # Build Graph API JSON
            email_data = {
                "message": {
                    "subject": subject,
                    "body": {
                        "contentType": content_type,
                        "content": body
                    },
                    "toRecipients": to_recipients,
                    "ccRecipients": cc_recipients,
                    "bccRecipients": bcc_recipients
                },
                "saveToSentItems": "true"
            }

            # (Optional) Handle attachments
            # if message.attachments:
            #   build the "attachments" list for Graph

            # Send via Graph
            response = requests.post(endpoint, headers=headers, json=email_data)
            # Raise if there's an error
            response.raise_for_status()
            sent_count += 1

        return sent_count
