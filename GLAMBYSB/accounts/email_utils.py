import msal
import requests
from django.conf import settings
from .models import EmailVerification
import uuid

def get_ms_graph_token():
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

def send_registration_email(user):
    """
    Sends a welcome email via Microsoft Graph with the email verification link.
    """
    # Generate a unique token for email verification
    token = str(uuid.uuid4())  # Generate a unique token for email verification
    verification = EmailVerification(user=user, token=token)  # Create an EmailVerification object
    verification.save()  # Save the token in the database
    
    # Generate the verification URL
    verification_url = f'https://kriscosalesllc.com/accounts/verify_email/{token}'  # Replace with your actual URL

    subject = "Welcome to Krisco Sales"
    html_body = f"""
    <html>
      <head>
        <style>
          body {{
            font-family: Arial, sans-serif;
            background-color: #ffffff;
            color: #333333;
            margin: 0;
            padding: 20px;
          }}
          .container {{
            max-width: 600px;
            margin: auto;
            border: 1px solid #dddddd;
            padding: 20px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
          }}
          h1 {{
            font-size: 24px;
            color: #13375e;
            margin-bottom: 20px;
          }}
          p {{
            line-height: 1.6;
          }}
          .button {{
            display: inline-block;
            padding: 10px 20px;
            font-size: 16px;
            color: #fff;
            background-color: #4CAF50;
            text-decoration: none;
            border-radius: 5px;
            text-align: center;
          }}
        </style>
      </head>
      <body>
        <div class="container">
          <h1>Welcome, {user.first_name}!</h1>
          <p>Thank you for registering with Krisco Sales. We’re excited to have you on board!</p>
          <p>Your username is: <strong>{user.username}</strong></p>
          <!-- Email verification button -->
          <p><a href="{verification_url}" class="button">Verify Your Email</a></p>
          <p>If you have any questions, please feel free to contact us.</p>
          <p>Best regards,<br/>Krisco Sales Team</p>
        </div>
      </body>
    </html>
    """
    
    # Prepare email data
    email_data = {
        "message": {
            "subject": subject,
            "body": {
                "contentType": "HTML",
                "content": html_body
            },
            "toRecipients": [
                {"emailAddress": {"address": user.email}}
            ],
            "ccRecipients": [
                {"emailAddress": {"address": "salesteam@kriscosales.com"}}
            ]
        },
        "saveToSentItems": "true"
    }

    # Get the token from Microsoft Graph API
    token = get_ms_graph_token()  # Ensure this function is defined elsewhere

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Send the email via Microsoft Graph
    endpoint = "https://graph.microsoft.com/v1.0/users/manoj.challapalli@kriscosales.com/sendMail"
    resp = requests.post(endpoint, headers=headers, json=email_data)
    resp.raise_for_status()
