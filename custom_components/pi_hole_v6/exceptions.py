"""The above classes represent the specific exceptions raised during the Pi-Hole API calls."""


class AbortLogoutException(Exception):
    """The class `AbortLogoutException` represents an exception when a logout is not relevant and can be avoided."""

    code: int = 499
    reason: str = "No logout needed."

    def __init__(  # noqa: D107
        self,
        message: str = "Logout call is not relevant. Maybe no session is active.",
    ) -> None:
        self.message = message
        super().__init__(self.message)


class BadGatewayException(Exception):
    """The class `BadGatewayException` represents an exception for receiving an invalid response from an upstream server."""

    def __init__(  # noqa: D107
        self,
        message: str = "Received an invalid response from an upstream server.",
    ) -> None:
        self.message = message
        super().__init__(self.message)


class BadRequestException(Exception):
    """The class `BadRequestException` is defined for requests that are unacceptable."""

    def __init__(  # noqa: D107
        self,
        message: str = "The request was unacceptable, often due to a missing required parameter",
    ) -> None:
        self.message = message
        super().__init__(self.message)


class ClientConnectorException(Exception):
    """The class `ClientConnectorException` is used to raise an exception when the Pi-hole V6 server is unreachable."""

    def __init__(  # noqa: D107
        self,
        message: str = "The Pi-hole V6 server seems to be unreachable.",
    ) -> None:
        self.message = message
        super().__init__(self.message)


class ContentTypeException(Exception):
    """The class `ContentTypeException` is used to raise an exception when the content type provided by the API is incorrect."""

    def __init__(  # noqa: D107
        self,
        message: str = "Invalid content type returned by the API.",
    ) -> None:
        self.message = message
        super().__init__(self.message)


class ForbiddenException(Exception):
    """The class `ForbiddenException` represents an exception for when an API key lacks the necessary permissions for a request."""

    def __init__(  # noqa: D107
        self,
        message: str = "The API key doesn't have permissions to perform the request.",
    ) -> None:
        self.message = message
        super().__init__(self.message)


class GatewayTimeoutException(Exception):
    """The class `GatewayTimeoutException` represents an exception that occurs when a server acting as a gateway times out waiting for another server."""

    def __init__(  # noqa: D107
        self,
        message: str = "The server, while acting as a gateway, timed out waiting for another server.",
    ) -> None:
        self.message = message
        super().__init__(self.message)


class MethodNotAllowedException(Exception):
    """The class `MethodNotAllowedException` represents an exception that occurs when a request's HTTP method is not supported on the server."""

    def __init__(  # noqa: D107
        self,
        message: str = "The HTTP method is not supported on the server.",
    ) -> None:
        self.message = message
        super().__init__(self.message)


class NotFoundException(Exception):
    """The class `NotFoundException` represents a situation where a requested resource does not exist."""

    def __init__(  # noqa: D107
        self,
        message: str = "The requested resource doesn't exist.",
    ) -> None:
        self.message = message
        super().__init__(self.message)


class RequestFailedException(Exception):
    """The class `RequestFailedException` defines an exception for when a request fails."""

    def __init__(  # noqa: D107
        self,
        message: str = "The parameters were valid but the request failed.",
    ) -> None:
        self.message = message
        super().__init__(self.message)


class ServerErrorException(Exception):
    """The class `ServerErrorException` defines an exception for internal server errors."""

    def __init__(  # noqa: D107
        self,
        message: str = "An internal server error occurred.",
    ) -> None:
        self.message = message
        super().__init__(self.message)


class ServiceUnavailableException(Exception):
    """The class `ServiceUnavailableException` defines an exception for when the server is temporarily unavailable."""

    def __init__(  # noqa: D107
        self,
        message: str = "The server is temporarily unavailable, usually due to maintenance or overload.",
    ) -> None:
        self.message = message
        super().__init__(self.message)


class TooManyRequestsException(Exception):
    """The class `TooManyRequestsException` represents hitting the API with too many requests too quickly."""

    def __init__(  # noqa: D107
        self,
        message: str = "Too many requests hit the API too quickly.",
    ) -> None:
        self.message = message
        super().__init__(self.message)


class UnauthorizedException(Exception):
    """The class `UnauthorizedException` is used to raise an exception when no session identity is provided for an endpoint requiring authorization."""

    def __init__(  # noqa: D107
        self,
        message: str = "No session identity provided for endpoint requiring authorization.",
    ) -> None:
        self.message = message
        super().__init__(self.message)


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
