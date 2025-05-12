from django.shortcuts import render
from django.views import View

from django.core.paginator import Paginator
from django.shortcuts import render

from django.shortcuts import render
from django.http import JsonResponse
from django.conf import settings
from django.views import View
from django.conf import settings
from .models import *
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.contrib import messages
import json
import random
from django.core.mail import EmailMessage
from io import BytesIO
from django.utils import timezone
import logging
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
import pandas as pd
from django.http import HttpResponse
import requests
import msal
from datetime import datetime
import io, base64, csv

from .models import *
class HomeView(View):
    def get(self, request):
        return render(request, 'home.html')


def brand_autocomplete(request):
    if 'term' in request.GET:
        qs = Brand.objects.filter(brand_name__icontains=request.GET.get('term'))
        brands = list(qs.values_list('brand_name', flat=True))
        return JsonResponse(brands, safe=False)
    return JsonResponse([], safe=False)

def brands(request):
    search_query = request.GET.get('q', '')  # Get the search query parameter 'q', default to empty string if not found

    if search_query:
        # Adjust the filter according to your Brand model attributes
        brand_lists = Brand.objects.filter(brand_name__icontains=search_query)
    else:
        brand_lists = Brand.objects.all()
    brand_lists = brand_lists.order_by('brand_name')
    paginator = Paginator(brand_lists, 18)  # Show 18 brands per page, adjust as needed

    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'brands.html', {'page_obj': page_obj, 'search_query': search_query})


def new_products(request):
    return render(request, 'new_products.html')

def about_us(request):
    return render(request, 'aboutus.html')




class OrderView(View):
    template_name = "shop.html"

    def get(self, request, *args, **kwargs):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            inventory = self.load_inventory()
            return JsonResponse({"inventory": inventory})
        else:
            return render(request, self.template_name)

    @method_decorator(csrf_exempt)
    def post(self, request, *args, **kwargs):
        try:
            order_details = json.loads(request.body)
            self.save_order_to_gsheet(order_details)
            self.send_email(order_details)
            return JsonResponse({"status": "success"})
        except Exception as e:
            return JsonResponse({"status": "error", "error": str(e)}, status=400)

    def load_inventory(self):
        sheet_id = settings.GOOGLE_SPREADSHEET_ID
        api_key = settings.GOOGLE_API_KEY
        url = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/Inventory!A1:Z1000?key={api_key}"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            rows = data.get("values", [])
            # If you want to drop the header row:
            if len(rows) > 1:
                rows = rows[1:]
            return rows
        return []

    def save_order_to_gsheet(self, order_details):
        sheet_id = settings.GOOGLE_SPREADSHEET_ID
        api_key = settings.GOOGLE_API_KEY
        url = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/Orders!A1:append?valueInputOption=USER_ENTERED&key={api_key}"
        values = [[order_details.get("email", ""), json.dumps(order_details)]]
        payload = {"values": values}
        headers = {"Content-Type": "application/json"}
        requests.post(url, json=payload, headers=headers)

    def generate_order_number(self):
        """Generate a unique numeric order ID."""
        timestamp = datetime.now().strftime('%y%m%d%H%M%S')  # e.g. '250320142359'
        random_digits = str(random.randint(100, 999))        # e.g. '123'
        return timestamp + random_digits

    def create_csv_attachment(self, order_details, order_number):
        """
        Creates a CSV file in memory with order details.
        Returns a base64-encoded string.
        """
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["SKU", "Description", "Size", "Qty", "MSRP", "Discount", "Offer", "Comment"])
        for item in order_details["items"]:
            writer.writerow([
                item.get("SKU"),
                item.get("DESCRIPTION"),
                item.get("SIZE"),
                item.get("ORDER_QTY"),
                item.get("MSRP"),
                item.get("DISCOUNT"),
                item.get("OFFER"),
                item.get("COMMENT", "")
            ])
        csv_bytes = output.getvalue().encode("utf-8")
        return base64.b64encode(csv_bytes).decode("utf-8")

    def build_email_body(self, order_details, order_number):
        return f"""
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
                    box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
                }}
                .header {{
                    text-align: center;
                    padding-bottom: 20px;
                    border-bottom: 1px solid #dddddd;
                }}
                .header h1 {{
                    margin: 0;
                    font-size: 24px;
                    color: #333333;
                }}
                .section-title {{
                    font-size: 18px;
                    color: #555555;
                    margin-top: 20px;
                    margin-bottom: 10px;
                    border-bottom: 1px solid #dddddd;
                    padding-bottom: 5px;
                }}
                .info-row {{
                    margin-bottom: 10px;
                    line-height: 1.6;
                }}
                p {{
                    margin-top: 20px;
                }}
                </style>
            </head>
            <body>
                <div class="container">
                <div class="header">
                    <h1>New Order Received</h1>
                </div>
                <div class="section-title">Order Details</div>
                <div class="info-row"><strong>Order Number:</strong> {order_number}</div>
                <div class="info-row"><strong>Email:</strong> {order_details.get("email")}</div>
                <div class="info-row"><strong>Phone:</strong> {order_details.get("phone")}</div>
                <div class="info-row"><strong>Company:</strong> {order_details.get("company")}</div>
                <div class="section-title">Shipping Information</div>
                <div class="info-row"><strong>Address:</strong> {order_details["shipping"].get("address")}</div>
                <div class="info-row"><strong>City:</strong> {order_details["shipping"].get("city")}</div>
                <div class="info-row"><strong>Zip:</strong> {order_details["shipping"].get("zip")}</div>
                <div class="info-row"><strong>Country:</strong> {order_details["shipping"].get("country")}</div>
                <p>Please find the attached CSV for detailed item information.</p>
                </div>
            </body>
            </html>
        """

    def send_email(self, order_details):
        # Generate order number and prepare attachment and email body
        order_number = self.generate_order_number()
        csv_content = self.create_csv_attachment(order_details, order_number)
        csv_filename = f"order_{order_number}.csv"
        html_body = self.build_email_body(order_details, order_number)
        from_email = "manoj.challapalli@kriscosales.com"
        to_email = order_details.get("email")
        subject = f"New Order Received - Order #{order_number}"

        token = self.get_ms_graph_token()
        endpoint = f"https://graph.microsoft.com/v1.0/users/{from_email}/sendMail"
        email_data = {
            "message": {
                "subject": subject,
                "body": {
                    "contentType": "HTML",
                    "content": html_body
                },
                "toRecipients": [
                    {"emailAddress": {"address": to_email}}
                ],
                "ccRecipients": [
                    {"emailAddress": {"address": "salesteam@kriscosales.com"}}
                ],
                "attachments": [
                    {
                        "@odata.type": "#microsoft.graph.fileAttachment",
                        "name": csv_filename,
                        "contentBytes": csv_content
                    }
                ]
            },
            "saveToSentItems": "true"
        }
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        resp = requests.post(endpoint, headers=headers, json=email_data)
        resp.raise_for_status()

    def get_ms_graph_token(self):
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
        

def contact(request):
    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        mobile_number = request.POST.get('mobile_number')
        company_name = request.POST.get('company_name')
        message = request.POST.get('message')
        
        # Create a new ContactUs instance and save it to the database
        contact_entry = ContactUs(first_name=first_name, last_name=last_name,company_name=company_name,mobile_number=mobile_number ,email=email, message=message)
        contact_entry.save()
        
        messages.success(request, 'Thank you for your message. We will get back to you shortly.')
    return render(request,'contact.html')   