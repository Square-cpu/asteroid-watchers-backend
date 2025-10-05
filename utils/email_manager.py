import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


class _DummyGmailService:
    """A dummy service that mimics the Gmail API but does nothing.

    This is used when email is disabled to prevent the app from crashing.
    """

    def users(self):
        return self

    def messages(self):
        return self

    def send(self, userId, body):
        """Simulates the send method by printing to the console."""
        print("\n--- EMAIL SENDING DISABLED ---")
        print("An email would have been sent, but EMAIL_ENABLED is false.")
        # You can add more detailed logging here if you wish
        print("----------------------------\n")
        return self

    def execute(self):
        return {"result": "success (dummy)"}


class EmailManager:
    def __init__(self, app):
        """Initializes the EmailManager, lazy-loading the Gmail service."""
        self.app = app
        self.service_gmail = None
        self.is_enabled = app.config.get("EMAIL_ENABLED", False)

        # Initialize the real service only if enabled in the config
        if self.is_enabled:
            self._init_real_gmail_service()
        else:
            # Use the safe, dummy service if not enabled
            self.service_gmail = _DummyGmailService()

    def _init_real_gmail_service(self):
        """Initializes the connection to the real Gmail API."""
        try:
            service_account_file = self.app.config.get("SERVICE_ACCOUNT_FILE")
            api_subject = self.app.config.get("GMAIL_API_SUBJECT")

            # Check if necessary config values are present
            if not service_account_file or not api_subject:
                print(
                    "WARNING: EMAIL_ENABLED is true, but SERVICE_ACCOUNT_FILE or GMAIL_API_SUBJECT is not configured."
                )
                self.service_gmail = _DummyGmailService()
                return

            credentials = service_account.Credentials.from_service_account_file(
                filename=service_account_file,
                scopes=["https://mail.google.com/"],
                subject=api_subject,
            )
            self.service_gmail = build("gmail", "v1", credentials=credentials)
            print("INFO: Gmail service initialized successfully.")
        except Exception as e:
            print(f"ERROR: Failed to initialize Gmail service: {e}")
            print("WARNING: Falling back to dummy email service.")
            self.service_gmail = _DummyGmailService()

    def send_email(self, to, subject, template, template_html=None):
        """
        Constructs and sends an email using the configured Gmail service.

        If email sending is disabled, it will log the attempt to the console
        instead of sending a real email.
        """
        sender_address = self.app.config.get("MAIL_SENDER")

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender_address
        msg["To"] = to
        msg.attach(MIMEText(template, "plain"))

        if template_html:
            msg.attach(MIMEText(template_html, "html"))

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        body = {"raw": raw}

        try:
            # The service_gmail object is either the real one or the dummy one
            self.service_gmail.users().messages().send(userId="me", body=body).execute()
            return 200
        except HttpError as e:
            self.app.logger.error(
                f"Email sending failed with HTTP error: {e.resp.status}"
            )
            return e.resp.status
        except Exception as e:
            self.app.logger.error(
                f"An unexpected error occurred during email sending: {e}"
            )
            return 500
