from dataclasses import dataclass
from datetime import datetime

@dataclass
class Indicator:
   id: str
   category: str
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
   comment_emr_id: str
   created_at: datetime
   updated_at: datetime