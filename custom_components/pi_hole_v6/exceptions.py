"""Custom exceptions raised during Pi-hole V6 API calls."""

from typing import Any


class PiHoleV6Error(Exception):
    """The class `PiHoleV6Error` is the base exception for every error raised by this integration.

    Catching this single class is enough to handle any failure coming from the
    Pi-hole V6 client, whether it is a network-level problem, a malformed
    response or an error status returned by the API.

    Attributes:
        message (str): The message carried by the exception.

    """

    message: str = ""

    def __init__(self, message: str | None = None) -> None:
        """Initialize the exception.

        Args:
            message (str | None): The message carried by the exception. If None (default), the class-level `message` attribute is used.

        """
        super().__init__(self.message if message is None else message)


class APIError(PiHoleV6Error):
    """The class `APIError` is a parent exception related to Pi-hole API."""


class ActionExecutionError(PiHoleV6Error):
    """The class `ActionExecutionError` is used to raise an exception when an action cannot be executed.

    Attributes:
        message (str): The message carried by the exception.

    """

    message: str = "The action requested has failed. Please check HA logs or Pi-hole logs."


class AbortLogoutError(PiHoleV6Error):
    """The class `AbortLogoutError` represents an exception when a logout is not relevant and can be avoided.

    Attributes:
        code (int): The HTTP status code associated with the exception.
        reason (str): The reason associated with the exception.
        message (str): The message carried by the exception.

    """

    code: int = 499
    reason: str = "No logout needed."
    message: str = "Logout call is not relevant. Maybe no session is active. Please check HA logs or Pi-hole logs."


class BadGatewayError(APIError):
    """The class `BadGatewayError` represents an exception for receiving an invalid response from an upstream server.

    Attributes:
        message (str): The message carried by the exception.

    """

    message: str = "Received an invalid response from an upstream server. Please check HA logs or Pi-hole logs."


class BadRequestError(APIError):
    """The class `BadRequestError` is defined for requests that are unacceptable.

    Attributes:
        message (str): The message carried by the exception.

    """

    message: str = (
        "The request was unacceptable, often due to a missing required parameter. Please check HA logs or Pi-hole logs."
    )


class ClientConnectorError(PiHoleV6Error):
    """The class `ClientConnectorError` is used to raise an exception when the Pi-hole V6 server is unreachable.

    Attributes:
        message (str): The message carried by the exception.

    """

    message: str = "The Pi-hole V6 server seems to be unreachable. Please check HA logs or Pi-hole logs."

    def __init__(self, custom_message: str = "") -> None:
        """Initialize the ClientConnectorError exception, optionally appending a custom message.

        Args:
            custom_message (str): An optional additional message to append to the default error message. If empty (default), only the default message is used.

        """
        new_message: str = self.message

        if custom_message != "":
            new_message = f"{new_message} # {custom_message}"

        super().__init__(new_message)


class ContentTypeError(PiHoleV6Error):
    """The class `ContentTypeError` is used to raise an exception when the content type provided by the API is incorrect.

    Attributes:
        message (str): The message carried by the exception.

    """

    message: str = "Invalid content type returned by the API. Please check HA logs or Pi-hole logs."


class ForbiddenError(APIError):
    """The class `ForbiddenError` represents an exception for when an API key lacks the necessary permissions for a request.

    Attributes:
        message (str): The message carried by the exception.

    """

    message: str = "The API key doesn't have permissions to perform the request. Please check HA logs or Pi-hole logs."


class GatewayTimeoutError(APIError):
    """The class `GatewayTimeoutError` represents a gateway server timing out on an upstream server.

    Attributes:
        message (str): The message carried by the exception.

    """

    message: str = "The server, while acting as a gateway, timed out waiting for another server. Please check HA logs or Pi-hole logs."


class MethodNotAllowedError(APIError):
    """The class `MethodNotAllowedError` represents an HTTP method not supported by the server.

    Attributes:
        message (str): The message carried by the exception.

    """

    message: str = "The HTTP method is not supported on the server. Please check HA logs or Pi-hole logs."


class NotFoundError(APIError):
    """The class `NotFoundError` represents a situation where a requested resource does not exist.

    Attributes:
        message (str): The message carried by the exception.

    """

    message: str = "The requested resource doesn't exist. Please check HA logs or Pi-hole logs."


class RequestFailedError(APIError):
    """The class `RequestFailedError` defines an exception for when a request fails.

    Attributes:
        message (str): The message carried by the exception.

    """

    message: str = "The parameters were valid but the request failed. Please check HA logs or Pi-hole logs."


class ServerError(APIError):
    """The class `ServerError` defines an exception for internal server errors.

    Attributes:
        message (str): The message carried by the exception.

    """

    message: str = "An internal server error occurred. Please check HA logs or Pi-hole logs."


class ServiceUnavailableError(APIError):
    """The class `ServiceUnavailableError` defines an exception for when the server is temporarily unavailable.

    Attributes:
        message (str): The message carried by the exception.

    """

    message: str = "The server is temporarily unavailable, usually due to maintenance or overload. Please check HA logs or Pi-hole logs."


class TooManyRequestsError(APIError):
    """The class `TooManyRequestsError` represents hitting the API with too many requests too quickly.

    Attributes:
        message (str): The message carried by the exception.

    """

    message: str = "Too many requests hit the API too quickly. Please check HA logs or Pi-hole logs."


class UnauthorizedError(APIError):
    """The class `UnauthorizedError` is raised when an endpoint requiring authorization gets no session identity.

    Attributes:
        message (str): The message carried by the exception.

    """

    message: str = (
        "No session identity provided for endpoint requiring authorization. Please check HA logs or Pi-hole logs."
    )


class DataStructureError(APIError):
    """The class `DataStructureError` is used to raise an exception when the data structure returned by the API is incorrect.

    Attributes:
        message (str): The message carried by the exception.

    """

    message: str = "Data structure returned by the API is incorrect. Please check HA logs or Pi-hole logs."

    def __init__(self, endpoint: str | None = None) -> None:
        """Initialize the exception, naming the endpoint that returned the invalid structure.

        Args:
            endpoint (str | None): The name of the API call whose result was not a dictionary. If None (default), only the default message is used.

        """
        new_message: str = self.message

        if endpoint is not None:
            new_message = f"{new_message} # Endpoint {endpoint}"

        super().__init__(new_message)


class UnexpectedStatusError(APIError):
    """The class `UnexpectedStatusError` is used when the API returns a status code that is not mapped.

    Attributes:
        message (str): The message carried by the exception.

    """

    message: str = "The API returned an unexpected status code. Please check HA logs or Pi-hole logs."

    def __init__(self, status_code: int | None = None) -> None:
        """Initialize the exception, appending the unmapped status code when it is known.

        Args:
            status_code (int | None): The unmapped HTTP status code returned by the API. If None (default), only the default message is used.

        """
        new_message: str = self.message

        if status_code is not None:
            new_message = f"{new_message} # Status code {status_code}"

        super().__init__(new_message)


def handle_status(status_code: int) -> None:
    """Raise specific exceptions based on the input status code.

    The errors of the underlying call propagate unchanged: BadRequestError (if status code is 400), UnauthorizedError (if status code is 401), RequestFailedError (if status code is 402), ForbiddenError (if status code is 403), NotFoundError (if status code is 404), MethodNotAllowedError (if status code is 405), TooManyRequestsError (if status code is 429), ServerError (if status code is 500), BadGatewayError (if status code is 502), ServiceUnavailableError (if status code is 503), GatewayTimeoutError (if status code is 504), AbortLogoutError (if status code is 499).

    Args:
        status_code (int): Represents the status code and handles it based on the provided mapping.

    Returns:
        None: Returns immediately if the status code is less than 400.

    Raises:
        UnexpectedStatusError: If the status code is not mapped.

    """

    if status_code < 400:
        return

    exception_map: dict[int, Any] = {
        400: BadRequestError,
        401: UnauthorizedError,
        402: RequestFailedError,
        403: ForbiddenError,
        404: NotFoundError,
        405: MethodNotAllowedError,
        429: TooManyRequestsError,
        500: ServerError,
        502: BadGatewayError,
        503: ServiceUnavailableError,
        504: GatewayTimeoutError,
        499: AbortLogoutError,
    }

    if status_code in exception_map:
        raise exception_map[status_code]()  # noqa: RSE102

    raise UnexpectedStatusError(status_code)
