"""
Custom SMTP email backend compatible with Python 3.12.

Python 3.12 removed the deprecated `keyfile` and `certfile` keyword
arguments from both `smtplib.SMTP.starttls()` and `smtplib.SMTP_SSL()`.
Django 3.2 still passes them.  This backend replaces those calls with
the modern `ssl.SSLContext`-based API.
"""
import ssl
import smtplib

from django.core.mail.backends.smtp import EmailBackend as DjangoEmailBackend
from django.core.mail.utils import DNS_NAME


class EmailBackend(DjangoEmailBackend):
    def _build_ssl_context(self):
        """Return an SSLContext, loading certfile/keyfile if configured."""
        context = ssl.create_default_context()
        if self.ssl_certfile or self.ssl_keyfile:
            context.load_cert_chain(
                certfile=self.ssl_certfile,
                keyfile=self.ssl_keyfile,
            )
        return context

    def open(self):
        if self.connection:
            return False
        connection_params = {
            "local_hostname": DNS_NAME.get_fqdn(),
        }
        if self.timeout is not None:
            connection_params["timeout"] = self.timeout
        try:
            if self.use_ssl:
                connection_params["context"] = self._build_ssl_context()
                self.connection = smtplib.SMTP_SSL(
                    self.host, self.port, **connection_params
                )
            else:
                self.connection = smtplib.SMTP(
                    self.host, self.port, **connection_params
                )
            if self.use_tls:
                self.connection.ehlo()
                self.connection.starttls(context=self._build_ssl_context())
                self.connection.ehlo()
            if self.username and self.password:
                self.connection.login(self.username, self.password)
            return True
        except smtplib.SMTPException:
            if not self.fail_silently:
                raise
