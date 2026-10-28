"""Modèles Pydantic miroirs des dataclasses de `model.py`.

Configurés avec `from_attributes=True` : ils se construisent directement depuis
les instances des repos (`IndicatorSchema.model_validate(indicator)`) et servent
de schémas de réponse / de requête pour FastAPI.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from poc_trust_tower.core.model import ROLE, CertificationStatus


class _Schema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# Business units ======================================================
class BusinessUnitSchema(_Schema):
    id: str
    name: str


class BusinessUnitCreateSchema(BaseModel):
    name: str = Field(min_length=1, max_length=100)


# Categories ==========================================================
class CategorySchema(_Schema):
    id: str
    name: str


class CategoryCreateSchema(BaseModel):
    name: str = Field(min_length=1, max_length=100)


# Users ===============================================================
class UserSchema(_Schema):
    """Vue publique d'un utilisateur : le mot de passe n'est jamais exposé."""

    id: str
    email: EmailStr
    business_unit: BusinessUnitSchema
    role: ROLE


class UserCreateSchema(BaseModel):
    """Payload de création d'un utilisateur (la BU est référencée par son id)."""

    email: EmailStr
    password: str = Field(min_length=4)
    business_unit_id: str
    role: ROLE


# Indicators ==========================================================
class IndicatorSchema(_Schema):
    id: str
    category: CategorySchema
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
    comment_bu: str
    comment_bu_head: str
    comment_cfo: str
    business_unit: BusinessUnitSchema
    created_at: datetime
    updated_at: datetime


class IndicatorCreateSchema(BaseModel):
    """Payload de création d'un indicateur.

    `id`, `variation`, `created_at` et `updated_at` sont calculés par le serveur ;
    les statuts de certification démarrent à `pending` et les commentaires vides.
    """

    category_id: str
    business_unit_id: str
    nature_of_information: str = Field(min_length=1)
    description_action_expected: str = Field(min_length=1)
    availability_date: datetime
    validation_committee: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    value: float
    value_previous: float
    comment_analysis: str = ""
    thresold_certified_without_reserves: float
    thresold_acceptable: float
    thresold_certified_with_significant_reserves: float
    thresold_not_certified: float
    certification_bu: str = CertificationStatus.pending.name
    certification_bu_head: str = CertificationStatus.pending.name
    certification_cfo: str = CertificationStatus.pending.name
    comment_emr_id: str = ""
    comment_bu: str = ""
    comment_bu_head: str = ""
    comment_cfo: str = ""

    @model_validator(mode="after")
    def _check_thresholds_order(self) -> "IndicatorCreateSchema":
        thresholds = (
            self.thresold_certified_without_reserves,
            self.thresold_acceptable,
            self.thresold_certified_with_significant_reserves,
            self.thresold_not_certified,
        )
        if list(thresholds) != sorted(thresholds, reverse=True):
            raise ValueError(
                "thresholds must be decreasing: certified_without_reserves >= acceptable "
                ">= certified_with_significant_reserves >= not_certified"
            )
        return self


# Campaigns ===========================================================
class CampaignSchema(_Schema):
    id: str
    name: str
    start_date: datetime
    end_date: datetime
    indicators: list[IndicatorSchema]


class CampaignCreateSchema(BaseModel):
    """Payload de création d'une campagne (indicateurs référencés par leurs ids)."""

    name: str = Field(min_length=1, max_length=100)
    start_date: datetime
    end_date: datetime
    indicator_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_dates(self) -> "CampaignCreateSchema":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be after start_date")
        return self
