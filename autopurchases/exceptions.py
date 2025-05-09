from rest_framework.exceptions import APIException, status


class BadRequest(APIException):
    status_code = status.HTTP_400_BAD_REQUEST


class Conflict(APIException):
    status_code = status.HTTP_409_CONFLICT
