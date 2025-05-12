from typing import Counter
from django.contrib import messages
from django.conf import settings
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import redirect, render
from django.contrib.auth.models import User, auth
from django.template.loader import render_to_string
from django.core.mail import EmailMessage
from django.db.models import Avg, Count, Min, Sum
from django.utils import timezone
from django.contrib.sessions.models import Session
from django.contrib.auth.decorators import permission_required, user_passes_test
import pandas as pd
import math
import msal
import requests
# Create your views here.
from accounts.email_utils import send_registration_email
from django.contrib.auth.views import PasswordResetView
from .models import EmailVerification
import uuid


def verify_email(request, token):
    try:
        # Find the verification object by token
        verification = EmailVerification.objects.get(token=token)
        
        # Check if token is valid
        if verification.is_verified:
            messages.info(request, 'Your email is already verified.')
            return redirect('login')  # Redirect to the login page

        # Mark as verified
        verification.is_verified = True
        verification.save()

        # Activate the user
        user = verification.user
        user.is_active = True  # Activate the user after verification
        user.save()

        messages.success(request, 'Your email has been verified successfully!')
        return redirect('login')  # Redirect to login page after verification
    
    except EmailVerification.DoesNotExist:
        messages.error(request, 'Invalid or expired verification link.')
        return redirect('register')






def verify_recaptcha_v2(recaptcha_response):
    """
    Verifies the reCAPTCHA response by sending a request to Google's API.
    """
    secret_key = settings.RECAPTCHA_PRIVATE_KEY
    url = 'https://www.google.com/recaptcha/api/siteverify'
    data = {
        'secret': secret_key,
        'response': recaptcha_response
    }
    response = requests.post(url, data=data)
    result = response.json()
    return result.get('success', False)


def login(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = auth.authenticate(username=username, password=password)
        if user is not None:
            auth.login(request, user)
            return redirect("/")
        else:
            messages.info(request, 'Oh No,Invalid Username or Password !')
            return redirect('login')
    else:
        return render(request, 'login.html')


def register(request):
    context = {
        'RECAPTCHA_PUBLIC_KEY': settings.RECAPTCHA_PUBLIC_KEY,
    }
    if request.method == 'POST':
        email = request.POST['email']
        first_name = request.POST['first_name']
        last_name = request.POST['last_name']
        password = request.POST['password']
        username = request.POST['username']
        recaptcha_response = request.POST.get('g-recaptcha-response')

        # Validate reCAPTCHA response
        if not verify_recaptcha_v2(recaptcha_response):
            messages.info(request, 'Please complete the CAPTCHA.')
            return redirect('register')

        if User.objects.filter(username=username).exists():
            messages.info(request, 'Huff, Username already exists')
            return redirect("register")
        elif User.objects.filter(email=email).exists():
            messages.info(request, 'Come on, Email was already taken!')
            return redirect("register")
        else:
            user = User.objects.create_user(
                username=username,
                password=password,
                email=email,
                first_name=first_name,
                last_name=last_name
            )
            user.save()
            try:
                send_registration_email(user)
            except Exception as e:
                messages.error(request, f"Failed to send welcome email: {e}")
            return redirect("login")
    else:
        return render(request, 'register.html',context)


def logout(request):
    auth.logout(request)
    return redirect("/")



class CustomPasswordResetView(PasswordResetView):
    # Specify the templates for the form, the email body, and the email subject.
    template_name = "registration/password_reset_form.html"
    email_template_name = "registration/password_reset_email.html"
    subject_template_name = "registration/password_reset_subject.txt"

    def send_mail(self, subject_template_name, email_template_name, context,
                  from_email, to_email, html_email_template_name=None):
        """
        Instead of using Django’s default SMTP email backend,
        this method sends the password reset email via Microsoft Graph.
        """
        # Render subject and email content from templates:
        subject = render_to_string(subject_template_name, context).strip()
        html_body = render_to_string(email_template_name, context)
        
        # Fixed sender and CC (if needed)
        sender = "manoj.challapalli@kriscosales.com"
        
        token = get_ms_graph_token()
        endpoint = f"https://graph.microsoft.com/v1.0/users/{sender}/sendMail"
        email_data = {
            "message": {
                "subject": subject,
                "body": {
                    "contentType": "HTML",
                    "content": html_body,
                },
                "toRecipients": [
                    {"emailAddress": {"address": to_email}},
                ],
            },
            "saveToSentItems": "true"
        }
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        response = requests.post(endpoint, headers=headers, json=email_data)
        response.raise_for_status()
