"""The above classes represent the specific exceptions raised during the Pi-hole API calls."""

from abc import abstractmethod


@abstractmethod
class APIException(Exception):
    """The class `APIException` is a parent exception related to Pi-hole API."""

    message: str = ""

    def __init__(self) -> None:
        super().__init__(self.message)


class ActionExecutionException(Exception):
    """The class `ActionExecutionException` is used to raise an exception when an action cannot be executed."""

    message: str = "The action requested has failed. Please check HA logs or Pi-hole logs."

    def __init__(self) -> None:
        super().__init__(self.message)


class AbortLogoutException(Exception):
    """The class `AbortLogoutException` represents an exception when a logout is not relevant and can be avoided."""

    code: int = 499
    reason: str = "No logout needed."
    message: str = "Logout call is not relevant. Maybe no session is active."

    def __init__(self) -> None:
        super().__init__(self.message)


class BadGatewayException(APIException):
    """The class `BadGatewayException` represents an exception for receiving an invalid response from an upstream server."""

    message: str = "Received an invalid response from an upstream server."


class BadRequestException(APIException):
    """The class `BadRequestException` is defined for requests that are unacceptable."""

    message: str = "The request was unacceptable, often due to a missing required parameter"


class ClientConnectorException(Exception):
    """The class `ClientConnectorException` is used to raise an exception when the Pi-hole V6 server is unreachable."""

    message: str = "The Pi-hole V6 server seems to be unreachable."

    def __init__(self, custom_message: str = "") -> None:
        new_message: str = self.message

        if custom_message != "":
            new_message = f"{new_message} # {custom_message}"

        super().__init__(new_message)


class ContentTypeException(Exception):
    """The class `ContentTypeException` is used to raise an exception when the content type provided by the API is incorrect."""

    message: str = "Invalid content type returned by the API."

    def __init__(self) -> None:
        super().__init__(self.message)


class ForbiddenException(APIException):
    """The class `ForbiddenException` represents an exception for when an API key lacks the necessary permissions for a request."""

    message: str = "The API key doesn't have permissions to perform the request."


class GatewayTimeoutException(APIException):
    """The class `GatewayTimeoutException` represents an exception that occurs when a server acting as a gateway times out waiting for another server."""

    message: str = "The server, while acting as a gateway, timed out waiting for another server."


class MethodNotAllowedException(APIException):
    """The class `MethodNotAllowedException` represents an exception that occurs when a request's HTTP method is not supported on the server."""

    message: str = "The HTTP method is not supported on the server."


class NotFoundException(APIException):
    """The class `NotFoundException` represents a situation where a requested resource does not exist."""

    message: str = "The requested resource doesn't exist."


class RequestFailedException(APIException):
    """The class `RequestFailedException` defines an exception for when a request fails."""

    message: str = "The parameters were valid but the request failed."


class ServerErrorException(APIException):
    """The class `ServerErrorException` defines an exception for internal server errors."""

    message: str = "An internal server error occurred."


class ServiceUnavailableException(APIException):
    """The class `ServiceUnavailableException` defines an exception for when the server is temporarily unavailable."""

    message: str = "The server is temporarily unavailable, usually due to maintenance or overload."


class TooManyRequestsException(APIException):
    """The class `TooManyRequestsException` represents hitting the API with too many requests too quickly."""

    message: str = "Too many requests hit the API too quickly."


class UnauthorizedException(APIException):
    """The class `UnauthorizedException` is used to raise an exception when no session identity is provided for an endpoint requiring authorization."""

    message: str = "No session identity provided for endpoint requiring authorization."


class DataStructureException(APIException):
    """The class `DataStructureException` is used to raise an exception when the data structure returned by the API is incorrect."""

    message: str = "Data structure returned by the API is incorrect."


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
        400: BadRequestException,
        401: UnauthorizedException,
        402: RequestFailedException,
        403: ForbiddenException,
        404: NotFoundException,
        405: MethodNotAllowedException,
        429: TooManyRequestsException,
        500: ServerErrorException,
        502: BadGatewayException,
        503: ServiceUnavailableException,
        504: GatewayTimeoutException,
        499: AbortLogoutException,
    }

    if status_code in exception_map:
        raise exception_map[status_code]()  # noqa: RSE102

    raise NotImplementedError(f"Unexpected error: Status code {status_code}")
