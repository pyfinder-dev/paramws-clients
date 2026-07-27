# -*- coding: utf-8 -*-
""" Base class for the web service clients. """
from abc import ABC, abstractmethod
import socket
import ssl
import time
import urllib
import urllib.error
import urllib.request as urlrequest
from urllib.parse import urlparse
from paramws.clients.services import httphelpers
from paramws.utils.customlogger import logger


class InvalidQueryOption(Exception):
    """ Raised when the given query option is not supported."""
    pass

class InvalidOptionValue(ValueError):
    """ Raised when the given query option value is not allowed."""
    pass

class BaseWebServiceConnector(ABC):
    """ Base class for all web service clients."""
    def __init__(self, agency=None, base_url=None, end_point=None, version="1"):
        # The web service base URL, e.g. "https://esm-db.eu/fdsnws"
        self.base_url = base_url

        # The web service end point, e.g. "shakemap"
        self.end_point = end_point

        # The web service version, e.g. "1"
        self.version = version

        # Full combined URL
        self.combined_url = self.build_url()

        # The agency providing the web service, e.g. "ESM"
        self.agency = agency

        # The data structure (model) to store the data retrieved from
        # the web services. This will be a subclass of BaseDataStructure,
        # and mostly likely nested.
        self.data = None

        # The flag to force redirect. If True, the client will follow
        # the redirect even if the credentials are given.
        self._force_redirect = False

        # These two private callables are the complete transport injection
        # boundary. Production requests still use the configured urllib
        # opener, while deterministic tests can supply the existing scripted
        # request and delay methods without changing a public constructor.
        self._request_callable = None
        self._delay_callable = time.sleep

        # Request context exists only while one query is in transport. It
        # gives retry logs the endpoint and provider options without exposing
        # separately supplied authentication credentials.
        self._active_request_context = None

    @abstractmethod
    def build_url(self, **options):
        """
        Return the final URL with web service, end point and options
        combined. Also, keep it internally.
        """
        return None

    @abstractmethod
    def parse_response(self, file_like_obj):
        """ Parse the data returned by the web service. """
        pass

    @abstractmethod
    def get_supported_options(self):
        """ Return the list of supported options for the web service. """
        return []

    @abstractmethod
    def is_value_valid(self, option, value):
        """
        Validate the given option value. Each subclass of this class is
        required supply a list of the values per option.
        """
        return True

    def set_force_redirect(self, force_redirect):
        """ Set the flag to force redirect. """
        self._force_redirect = force_redirect

    def get_force_redirect(self):
        """ Return the flag to force redirect. """
        return self._force_redirect

    def get_data(self):
        """ Return the data structure."""
        return self.data

    def set_data(self, data):
        """ Set the data structure."""
        self.data = data

    def get_agency(self):
        """ Return the agency providing the web service."""
        return self.agency

    def set_agency(self, agency):
        """ Set the agency providing the web service."""
        self.agency = agency

    def get_version(self):
        """ Return the web service version."""
        return self.version

    def set_version(self, version):
        """ Set the web service version."""
        self.version = version

    def get_end_point(self):
        """ Return the web service end point."""
        return self.end_point

    def set_end_point(self, end_point):
        """ Set the web service end point."""
        self.end_point = end_point

    def get_base_url(self):
        """ Return the web service base URL."""
        return self.base_url

    def set_base_url(self, base_url):
        """ Set the web service base URL."""
        # Complete the base URL if it does not end with a slash
        if base_url and base_url[-1] != "/":
            base_url += "/"

        self.base_url = base_url

    def get_combined_url(self):
        """ Return the combined URL."""
        return self.combined_url

    def query(self, url=None, user=None, password=None, **options):
        """
        Query the web service using either options or an already-resolved URL.

        A supplied URL is opaque transport input. Its parsed query is inspected
        only because existing connectors use those options to select a response
        parser; the exact original string is sent to the transport unchanged.
        """
        # If URL is not given, combine one using the options
        if url is None:
            # The concrete URL builder uses the same option cleaning path as
            # direct build_url() calls, including warnings for ignored input.
            options = self.validate_options(**options)
            url = self.build_url(**options)

        # Resolved URLs may contain provider-controlled ordering and percent
        # encoding. Inspecting a separate parsed copy must never turn into URL
        # reconstruction or another option-validation pass.
        else:
            parsed_url = urlparse(url)
            query_dict = urllib.parse.parse_qs(parsed_url.query)
            options = {
                key: value[0]
                for key, value in query_dict.items()
            }

        # The code below is taken from obspy.
        # Only add the authentication handler if required.
        handlers = []

        if user is not None and password is not None:
            # Create an OpenerDirector for HTTP Digest Authentication
            password_mgr = urlrequest.HTTPPasswordMgrWithDefaultRealm()
            password_mgr.add_password(None, self.base_url, user, password)
            handlers.append(urlrequest.HTTPDigestAuthHandler(password_mgr))

        if (user is None and password is None) or self._force_redirect is True:
            # Redirect if no credentials are given or the force_redirect
            # flag is True.
            handlers.append(httphelpers.CustomRedirectHandler())
        else:
            handlers.append(httphelpers.NoRedirectionHandler())

        # Open the URL and get the response
        opener = urlrequest.build_opener(*handlers)
        self._active_request_context = {
            "endpoint": self.get_end_point(),
            "options": dict(options),
        }
        try:
            code, url_response, _error = self.open_url(
                url=url, opener=opener)
        finally:
            self._active_request_context = None

        if url_response is None or not 200 <= code < 300:
            return code, None

        # Parsing is deliberately outside open_url(). A deterministic parser
        # or validation failure therefore escapes after one transport attempt
        # and can never be mistaken for a retryable request failure.
        data = self.parse_response(
            file_like_obj=url_response, options=options)
        if data is None:
            raise ValueError(
                "{} returned invalid successful content for endpoint {!r}."
                .format(self.get_agency(), self.get_end_point())
            )
        return code, data

    def validate_options(self, **options):
        """
        Return only supported options whose values are valid.

        Concrete connectors retain their own supported-option lists and value
        rules. This shared path only applies the common ignore-with-warning
        and invalid-value behavior.
        """
        if options is None:
            return {}

        supported_options = self.get_supported_options()
        cleaned_options = {}

        for option, value in options.items():
            if option not in supported_options:
                logger.warning(
                    "%s %s ignored unsupported option %r with value %r.",
                    self.get_agency(),
                    self.get_end_point(),
                    option,
                    value,
                )
                continue

            if not self.is_value_valid(option, value):
                raise InvalidOptionValue(
                    "`{}` is not a valid value for `{}` option.".format(
                        value, option))

            cleaned_options[option] = value

        return cleaned_options

    def open_url(self, url, opener, retries=3, timeout=10, wait=2):
        """
        Open one resolved URL using the fixed synchronous retry policy.

        Return the real HTTP status, response, and HTTP error after a response.
        Exhausted failures without an HTTP response raise their contracted
        standard exception instead of fabricating a status code.
        """
        retryable_statuses = {429, 500, 502, 503, 504}

        for attempt_index in range(retries):
            attempt = attempt_index + 1
            try:
                if self._request_callable is None:
                    url_response = opener.open(url, timeout=timeout)
                    code = url_response.getcode()
                else:
                    code, url_response = self._request_callable(url, timeout)
                error = None

            except urllib.error.HTTPError as caught_error:
                code = caught_error.code
                url_response = None
                error = caught_error

            except Exception as caught_error:
                failure_kind, underlying_reason = \
                    self._classify_transport_failure(caught_error)

                if failure_kind == "tls":
                    self._log_transport_failure(
                        url=url,
                        attempt=attempt,
                        attempts=retries,
                        outcome="not-retryable",
                        reason=underlying_reason,
                    )
                    if underlying_reason is caught_error:
                        raise
                    raise underlying_reason from caught_error

                if failure_kind in {"timeout", "connection"}:
                    if attempt < retries:
                        self._log_transport_failure(
                            url=url,
                            attempt=attempt,
                            attempts=retries,
                            outcome="retry",
                            reason=underlying_reason,
                            retry_delay=wait,
                        )
                        self._delay_callable(wait)
                        continue

                    self._log_transport_failure(
                        url=url,
                        attempt=attempt,
                        attempts=retries,
                        outcome="exhausted",
                        reason=underlying_reason,
                    )
                    if failure_kind == "timeout":
                        raise TimeoutError(
                            "{} request timed out after {} attempts: {}"
                            .format(self.get_agency(), retries,
                                    underlying_reason)
                        ) from caught_error
                    raise ConnectionError(
                        "{} connection failed after {} attempts: {}"
                        .format(self.get_agency(), retries,
                                underlying_reason)
                    ) from caught_error

                self._log_transport_failure(
                    url=url,
                    attempt=attempt,
                    attempts=retries,
                    outcome="not-retryable",
                    reason=underlying_reason,
                )
                raise

            if 200 <= code < 300:
                if self._response_is_empty(url_response):
                    error = ValueError(
                        "{} returned an empty successful response for "
                        "endpoint {!r}."
                        .format(self.get_agency(), self.get_end_point())
                    )
                    self._log_transport_failure(
                        url=url,
                        attempt=attempt,
                        attempts=retries,
                        outcome="not-retryable",
                        reason=error,
                        status=code,
                    )
                    raise error

                logger.debug(
                    "provider=%r url=%s status=%s attempt=%d/%d "
                    "outcome=success context=%r",
                    self.get_agency(),
                    self._url_for_log(url),
                    code,
                    attempt,
                    retries,
                    self._request_context(),
                )
                return code, url_response, None

            reason = error if error is not None else \
                "HTTP status {}".format(code)
            if code in retryable_statuses and attempt < retries:
                self._log_transport_failure(
                    url=url,
                    attempt=attempt,
                    attempts=retries,
                    outcome="retry",
                    reason=reason,
                    status=code,
                    retry_delay=wait,
                )
                self._delay_callable(wait)
                continue

            outcome = "exhausted" if code in retryable_statuses \
                else "not-retryable"
            self._log_transport_failure(
                url=url,
                attempt=attempt,
                attempts=retries,
                outcome=outcome,
                reason=reason,
                status=code,
            )
            return code, None, error

        raise AssertionError("Transport attempt loop ended without an outcome.")

    @staticmethod
    def _classify_transport_failure(error):
        """Return the retry category and most useful underlying reason."""
        reason = error.reason \
            if isinstance(error, urllib.error.URLError) else error

        # SSLError inherits from OSError, so TLS must be distinguished before
        # the broader URL and connection classifications.
        if isinstance(reason, ssl.SSLError):
            return "tls", reason
        if isinstance(reason, (TimeoutError, socket.timeout)):
            return "timeout", reason
        if isinstance(reason, (socket.gaierror, ConnectionError)):
            return "connection", reason
        return None, reason

    @staticmethod
    def _url_for_log(url):
        """Return URL context with authority user information replaced."""
        try:
            parsed_url = urllib.parse.urlsplit(url)
            if "@" not in parsed_url.netloc:
                return url

            # Only the diagnostic copy is rebuilt. The original resolved URL
            # remains untouched and is still passed exactly to the transport.
            host = parsed_url.netloc.rsplit("@", 1)[1]
            return urllib.parse.urlunsplit((
                parsed_url.scheme,
                "[redacted]@" + host,
                parsed_url.path,
                parsed_url.query,
                parsed_url.fragment,
            ))
        except Exception:
            return "<unavailable-url>"

    @staticmethod
    def _response_is_empty(response):
        """Recognize known-empty successful responses without consuming them."""
        if response is None:
            return True
        if isinstance(response, (bytes, bytearray, str)):
            return len(response) == 0
        if getattr(response, "length", None) == 0:
            return True
        if hasattr(response, "getheader"):
            content_length = response.getheader("Content-Length")
            if content_length == "0":
                return True
        return False

    def _request_context(self):
        """Return the applicable request context for transport diagnostics."""
        if self._active_request_context is not None:
            return self._active_request_context
        return {"endpoint": self.get_end_point()}

    def _log_transport_failure(self, url, attempt, attempts, outcome, reason,
                               status=None, retry_delay=None):
        """Log one failed transport attempt with its retry decision."""
        level = logger.warning if outcome == "retry" else logger.error
        message = (
            "provider=%r url=%s status=%r attempt=%d/%d outcome=%s "
            "context=%r reason=%s"
        )
        arguments = [
            self.get_agency(),
            self._url_for_log(url),
            status,
            attempt,
            attempts,
            outcome,
            self._request_context(),
            reason,
        ]
        if retry_delay is not None:
            message += " retry_delay=%s"
            arguments.append(retry_delay)
        level(message, *arguments)
