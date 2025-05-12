from django.shortcuts import render
from django.http import JsonResponse, HttpResponseBadRequest
from django.template.loader import render_to_string
from django.contrib.auth import get_user_model
from django.core import signing
from django.conf import settings
from django.views import View
from django.conf import settings
from django.http import JsonResponse
from .models import *
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.core.exceptions import ObjectDoesNotExist
import json
import random
from django.core.mail import EmailMessage
from django.core import serializers
from io import BytesIO
from django.utils import timezone
import logging
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
import pandas as pd
from django.http import HttpResponse
from order.models import Order
import requests
import msal
from datetime import datetime
import io, base64, csv



logger = logging.getLogger(__name__)

class WeeklyOffersView(View):
    template_name = 'offers.html'

    def get(self, request, *args, **kwargs):
        brand = request.GET.get('brand', '')
        category = request.GET.get('category', '')

        items = Weekly_Offer.objects.all()
        if brand:
            items = items.filter(brand=brand)
        if category:
            items = items.filter(category=category)

        unique_brands = set(items.values_list('brand', flat=True))
        unique_categories = set(items.values_list('category', flat=True))

        context = {
            'items': items,
            'unique_brands': unique_brands,
            'unique_categories': unique_categories,
        }
        return render(request, self.template_name, context)

class AddToPreviewView(View):
    def post(self, request, *args, **kwargs):
        data = json.loads(request.body.decode('utf-8'))
        columns = ['SKU', 'UPC', 'Description', 'Quantity', 'Price']
        df = pd.DataFrame(data, columns=columns)

        for index, row in df.iterrows():
            sku = row['SKU']
            entered_quantity = int(row['Quantity'])
            Weekly_Offer.objects.filter(sku=sku).update(available_qty=models.F('available_qty') - entered_quantity)

        return JsonResponse({'success': True})

def update_quantity_view(request):
    if request.method == 'POST':
        sku = request.POST.get('sku')
        quantity = request.POST.get('quantity')

        try:
            weekly_offer = Weekly_Offer.objects.get(sku=sku)
            weekly_offer.available_qty = quantity
            weekly_offer.save()
            return JsonResponse({'success': True})
        except Weekly_Offer.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Offer not found'})

    return JsonResponse({'success': False, 'error': 'Invalid request'})

@method_decorator(csrf_exempt, name='dispatch')
class SubmitPreviewView(View):
    def post(self, request, *args, **kwargs):
        try:
            # Assuming request.body contains the necessary data in JSON format
            data = json.loads(request.body.decode('utf-8'))

            # Convert the data to a pandas DataFrame (assuming 'data' has the appropriate structure)
            dataframe = pd.DataFrame(data['previewData'])

            # Generate a unique order ID using the current timestamp
            order_id = f'ORDER-ID :- {timezone.now().strftime("%Y%m%d%H%M%S")}'

            # Convert DataFrame to a dictionary for JSON storage
            order_data_json = dataframe.to_dict(orient='records')

            # Create an Order object and save it to the database
            Order.objects.create(
                order_id=order_id,
                order_data=order_data_json,
                customer_email = request.user.email,
                customer_firstname = request.user.first_name,
                customer_lastname = request.user.last_name,
            )

            grand_total_row = {
                'sku' : '-',
                'upc' : '-',
                'description': 'Grand Total:',
                'entered_quantity': dataframe['entered_quantity'].sum(),
                'offered_price': dataframe['offered_price'].sum(),
            }

            grand_total_df = pd.DataFrame([grand_total_row])
            dataframe = pd.concat([dataframe, grand_total_df], ignore_index=True)

            workbook = Workbook()
            sheet = workbook.active

            for row in dataframe_to_rows(dataframe, index=False, header=True):
                sheet.append(row)

            for column in sheet.columns:
                max_length = 0
                column = [cell for cell in column]
                max_length = max(len(str(cell.value)) for cell in column)
                adjusted_width = (max_length + 2)
                sheet.column_dimensions[column[0].column_letter].width = adjusted_width

            excel_buffer = BytesIO()
            workbook.save(excel_buffer)
            excel_buffer.seek(0)

            subject = f'New Order Received: {order_id}'
            message = 'Please find the attached Excel file containing the order details.'
            from_email = settings.EMAIL_HOST_USER
            cc_email = 'support10@pbkriscosales.net'
            recipient_list_with_cc = [request.user.email, cc_email]

            email = EmailMessage(subject, message, from_email, recipient_list_with_cc)
            email.attach('preview_order.xlsx', excel_buffer.read(), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            email.send()

            excel_buffer.close()

            # Log the successful creation of the order
            logger.info(f'Order {order_id} created successfully.')

            # Return a success response with the order ID
            return JsonResponse({'success': True, 'order_id': order_id})

        except Exception as e:
            # Log the error
            logger.error(f'Error in SubmitPreviewView: {e}')

            # Return a response indicating failure
            return JsonResponse({'success': False, 'error': 'Failed to submit the order'})
        

class ThankYouView(View):
    template_name = 'thankyou.html'

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)


class OrderView(View):
    template_name = "offer_order_submission.html"

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