"""The above classes represent the specific exceptions raised during the Pi-hole API calls."""

from abc import abstractmethod


@abstractmethod
class APIError(Exception):
    """The class `APIError` is a parent exception related to Pi-hole API."""

    message: str = ""

    def __init__(self) -> None:
        """Initialize the APIError exception with the class-level message."""
        super().__init__(self.message)


class ActionExecutionError(Exception):
    """The class `ActionExecutionError` is used to raise an exception when an action cannot be executed."""

    message: str = "The action requested has failed. Please check HA logs or Pi-hole logs."

    def __init__(self) -> None:
        """Initialize the ActionExecutionError exception with the class-level message."""
        super().__init__(self.message)


class AbortLogoutError(Exception):
    """The class `AbortLogoutError` represents an exception when a logout is not relevant and can be avoided."""

    code: int = 499
    reason: str = "No logout needed."
    message: str = "Logout call is not relevant. Maybe no session is active. Please check HA logs or Pi-hole logs."

    def __init__(self) -> None:
        """Initialize the AbortLogoutError exception with the class-level message."""
        super().__init__(self.message)


class BadGatewayError(APIError):
    """The class `BadGatewayError` represents an exception for receiving an invalid response from an upstream server."""

    message: str = "Received an invalid response from an upstream server. Please check HA logs or Pi-hole logs."


class BadRequestError(APIError):
    """The class `BadRequestError` is defined for requests that are unacceptable."""

    message: str = (
        "The request was unacceptable, often due to a missing required parameter. Please check HA logs or Pi-hole logs."
    )


class ClientConnectorError(Exception):
    """The class `ClientConnectorError` is used to raise an exception when the Pi-hole V6 server is unreachable."""

    message: str = "The Pi-hole V6 server seems to be unreachable. Please check HA logs or Pi-hole logs."

    def __init__(self, custom_message: str = "") -> None:
        """Initialize the ClientConnectorError exception, optionally appending a custom message.

        Args:
            custom_message (str): An optional additional message to append to the default error message.
                If empty (default), only the default message is used.

        """
        new_message: str = self.message

        if custom_message != "":
            new_message = f"{new_message} # {custom_message}"

        super().__init__(new_message)


class ContentTypeError(Exception):
    """The class `ContentTypeError` is used to raise an exception when the content type provided by the API is incorrect."""

    message: str = "Invalid content type returned by the API. Please check HA logs or Pi-hole logs."

    def __init__(self) -> None:
        """Initialize the ContentTypeError exception with the class-level message."""
        super().__init__(self.message)


class ForbiddenError(APIError):
    """The class `ForbiddenError` represents an exception for when an API key lacks the necessary permissions for a request."""

    message: str = "The API key doesn't have permissions to perform the request. Please check HA logs or Pi-hole logs."


class GatewayTimeoutError(APIError):
    """The class `GatewayTimeoutError` represents an exception that occurs when a server acting as a gateway times out waiting for another server."""

    message: str = "The server, while acting as a gateway, timed out waiting for another server. Please check HA logs or Pi-hole logs."


class MethodNotAllowedError(APIError):
    """The class `MethodNotAllowedError` represents an exception that occurs when a request's HTTP method is not supported on the server."""

    message: str = "The HTTP method is not supported on the server. Please check HA logs or Pi-hole logs."


class NotFoundError(APIError):
    """The class `NotFoundError` represents a situation where a requested resource does not exist."""

    message: str = "The requested resource doesn't exist. Please check HA logs or Pi-hole logs."


class RequestFailedError(APIError):
    """The class `RequestFailedError` defines an exception for when a request fails."""

    message: str = "The parameters were valid but the request failed. Please check HA logs or Pi-hole logs."


class ServerErrorError(APIError):
    """The class `ServerErrorError` defines an exception for internal server errors."""

    message: str = "An internal server error occurred. Please check HA logs or Pi-hole logs."


class ServiceUnavailableError(APIError):
    """The class `ServiceUnavailableError` defines an exception for when the server is temporarily unavailable."""

    message: str = "The server is temporarily unavailable, usually due to maintenance or overload. Please check HA logs or Pi-hole logs."


class TooManyRequestsError(APIError):
    """The class `TooManyRequestsError` represents hitting the API with too many requests too quickly."""

    message: str = "Too many requests hit the API too quickly. Please check HA logs or Pi-hole logs."


class UnauthorizedError(APIError):
    """The class `UnauthorizedError` is used to raise an exception when no session identity is provided for an endpoint requiring authorization."""

    message: str = (
        "No session identity provided for endpoint requiring authorization. Please check HA logs or Pi-hole logs."
    )


class DataStructureError(APIError):
    """The class `DataStructureError` is used to raise an exception when the data structure returned by the API is incorrect."""

    message: str = "Data structure returned by the API is incorrect. Please check HA logs or Pi-hole logs."


def handle_status(status_code: int) -> None:
    """Raise specific exceptions based on the input status code.

    Args:
      status_code (int): Represents the status code and handles it based on the provided mapping.

    Returns:
      result (None) : If the status code is less than 400, it returns `None`. If the status code corresponds to a known error code
      in the mapping, it raises the corresponding exception else the exception `NotImplementedError` is thrown.

    """

    if status_code < 400:
        return

    exception_map = {
        400: BadRequestError,
        401: UnauthorizedError,
        402: RequestFailedError,
        403: ForbiddenError,
        404: NotFoundError,
        405: MethodNotAllowedError,
        429: TooManyRequestsError,
        500: ServerErrorError,
        502: BadGatewayError,
        503: ServiceUnavailableError,
        504: GatewayTimeoutError,
        499: AbortLogoutError,
    }

    if status_code in exception_map:
        raise exception_map[status_code]()  # noqa: RSE102

    msg: str = f"Unexpected error: Status code {status_code}"
    raise NotImplementedError(msg)
