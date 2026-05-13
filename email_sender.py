import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send_email(subject, body_html, config):
    smtp_host = os.environ.get("SMTP_HOST", config["email"]["smtp_host"])
    smtp_port = int(os.environ.get("SMTP_PORT", config["email"]["smtp_port"]))
    username = os.environ["SMTP_USERNAME"]
    password = os.environ["SMTP_PASSWORD"]
    email_from = os.environ["EMAIL_FROM"]

    # Support comma-separated EMAIL_TO or fall back to config receivers
    email_to_raw = os.environ.get("EMAIL_TO", "")
    if email_to_raw:
        receivers = [r.strip() for r in email_to_raw.split(",") if r.strip()]
    else:
        receivers = config["email"]["receivers"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = email_from
    msg["To"] = ", ".join(receivers)

    # Plain text fallback: strip basic HTML tags
    plain = body_html.replace("<br>", "\n").replace("<b>", "").replace("</b>", "")
    plain = plain.replace("<hr>", "---").replace("<p>", "").replace("</p>", "\n")
    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
        server.starttls()
        server.login(username, password)
        server.sendmail(email_from, receivers, msg.as_string())

    print(f"Email sent to {receivers}")
