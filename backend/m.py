import os
import smtplib
from email.message import EmailMessage
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

import requests
from email.mime.image import MIMEImage

def send_email(subject: str, body_text: str, image_url: str, recipient: str):
    sender_email = "fundypro1@gmail.com"
    app_password = "laxmgoosojmvpmzg"

    # HTML with embedded image
    body = f"""
    <h2>Deposit</h2>
    <p>Approve: {body_text}</p>
    <img src="cid:image1" alt="Deposit Image" style="max-width:400px;">
    """

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = recipient
    msg.set_content("This is an HTML email. Please enable HTML view.")
    msg.add_alternative(body, subtype="html")

    # Download image if it's a URL
    if image_url.startswith("http"):
        response = requests.get(image_url)
        response.raise_for_status()
        img_data = response.content
    else:
        with open(image_url, "rb") as f:
            img_data = f.read()

    # Attach image inline
    image = MIMEImage(img_data)
    image.add_header("Content-ID", "<image1>")
    image.add_header("Content-Disposition", "inline", filename="deposit.png")
    msg.get_payload()[1].add_related(img_data, "image", "png", cid="<image1>")

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(sender_email, app_password)
        server.send_message(msg)



# m.py (or wherever your email helper lives)

def _sanitize_header(value: str) -> str:
    """Remove any CR / LF from header values and collapse multiple lines to a single space."""
    if value is None:
        return ""
    # Splitlines removes all kinds of line breaks, join with a single space, then strip.
    return " ".join(str(value).splitlines()).strip()

def send_withdraw_email(subject: str, body_html: str, recipient: str):
    """
    Send a simple HTML email. Header values are sanitized to avoid CR/LF injection.
    NOTE: set SMTP_SENDER and SMTP_APP_PASSWORD in your environment instead of hardcoding.
    """
    sender_email = os.getenv("SMTP_SENDER", "fundypro1@gmail.com")
    app_password = os.getenv("SMTP_APP_PASSWORD", "laxmgoosojmvpmzg")  # replace with env var in production

    subj = _sanitize_header(subject)
    recipient_sanitized = _sanitize_header(recipient)

    msg = EmailMessage()
    msg["Subject"] = subj
    msg["From"] = sender_email
    msg["To"] = recipient_sanitized

    # Plain text fallback for non-HTML clients:
    msg.set_content("You have a new withdrawal request. Please view in HTML-enabled client.")
    # Add HTML alternative:
    msg.add_alternative(body_html, subtype="html")

    # send email
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(sender_email, app_password)
        server.send_message(msg)

def send_deposit_email(subject: str, body_html: str, recipient: str):
    """
    Send a simple HTML email. Header values are sanitized to avoid CR/LF injection.
    NOTE: set SMTP_SENDER and SMTP_APP_PASSWORD in your environment instead of hardcoding.
    """
    sender_email = os.getenv("SMTP_SENDER", "fundypro1@gmail.com")
    app_password = os.getenv("SMTP_APP_PASSWORD", "laxmgoosojmvpmzg")  # replace with env var in production

    subj = _sanitize_header(subject)
    recipient_sanitized = _sanitize_header(recipient)

    msg = EmailMessage()
    msg["Subject"] = subj
    msg["From"] = sender_email
    msg["To"] = recipient_sanitized

    # Plain text fallback for non-HTML clients:
    msg.set_content("You have a new withdrawal request. Please view in HTML-enabled client.")
    # Add HTML alternative:
    msg.add_alternative(body_html, subtype="html")

    # send email
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(sender_email, app_password)
        server.send_message(msg)
