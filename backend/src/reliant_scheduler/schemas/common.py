import uuid
from datetime import datetime

from pydantic import BaseModel


class PaginationParams(BaseModel):
    page: int = 1
    page_size: int = 50


class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    page_size: int
    pages: int
