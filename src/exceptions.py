""" Custom exceptions """


class RepositoryException(Exception):
    """Base Exception for repository exceptions"""


class PaperNotFound(RepositoryException):
    """Paper Not Found Exception"""


class PaperNotSaved(RepositoryException):
    """Exception for Paper Not Saved Exception"""


class ParsingError(RepositoryException):
    """Exception for Parsing Exception"""
