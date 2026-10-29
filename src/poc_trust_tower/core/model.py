from dataclasses import dataclass
from datetime import datetime
from enum import Enum

@dataclass
class BusinessUnit:
   id: int
   name: str


@dataclass
class Category:
   id: int
   name: str


@dataclass
class User:
   id: int
   email: str
   password: str
   business_unit: BusinessUnit
   role: ROLE


class CertificationStatus(int,Enum):
   pending                             = 1
   certified_without_reserves           = 2
   acceptable                          = 3
   certified_with_significant_reserves   = 4
   not_certified                        = 5


class ROLE (str, Enum):
   ADMIN   = "ADMIN"
   BU      = "BU"
   BU_HEAD = "BU_HEAD"
   CFO     = "CFO"


@dataclass
class Campaign:
   id: int
   name: str
   start_date: datetime
   end_date: datetime
   indicators: list[Indicator]

@dataclass
class Indicator:
   id: int
   category: Category
   nature_of_information: str
   description_action_expected: str
   availability_date: datetime
   validation_committee: str
   unit: str
   value: float
   value_previous: float
   variation: float
   comment_analysis: str
   thresold_certified_without_reserves: float
   thresold_acceptable: float
   thresold_certified_with_significant_reserves: float
   thresold_not_certified: float
   certification_bu: str
   certification_bu_head: str
   certification_cfo: str
   comment_emr: str
   comment_bu: str
   comment_bu_head: str
   comment_cfo: str
   business_unit: BusinessUnit
   created_at: datetime
   updated_at: datetime

@dataclass
class CampaignIndicator:
   campain_id: int
   indicateur_id: int