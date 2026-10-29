"""Modèles Pydantic miroirs des dataclasses de `model.py`.

Configurés avec `from_attributes=True` : ils se construisent directement depuis
les instances des repos (`IndicatorSchema.model_validate(indicator)`) et servent
de schémas de réponse / de requête pour FastAPI.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from poc_trust_tower.core.model import ROLE, CertificationStatus


class _Schema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# Business units ======================================================
class BusinessUnitSchema(_Schema):
    id: int
    name: str


class BusinessUnitCreateSchema(BaseModel):
    name: str = Field(min_length=1, max_length=100)


# Categories ==========================================================
class CategorySchema(_Schema):
    id: int
    name: str


class CategoryCreateSchema(BaseModel):
    name: str = Field(min_length=1, max_length=100)


# Users ===============================================================
class UserSchema(_Schema):
    """Vue publique d'un utilisateur : le mot de passe n'est jamais exposé."""

    id: int
    email: EmailStr
    business_unit: BusinessUnitSchema
    role: ROLE


class UserCreateSchema(BaseModel):
    """Payload de création d'un utilisateur (la BU est référencée par son id)."""

    email: EmailStr
    password: str = Field(min_length=4)
    business_unit_id: int
    role: ROLE


class UserUpdateSchema(BaseModel):
    """Payload de mise à jour : mot de passe vide = inchangé."""

    email: EmailStr
    password: str = ""
    business_unit_id: int
    role: ROLE

    @model_validator(mode="after")
    def _check_password(self) -> "UserUpdateSchema":
        if self.password and len(self.password) < 4:
            raise ValueError("password must be at least 4 characters")
        return self


# Indicators ==========================================================
class IndicatorSchema(_Schema):
    id: int
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
    comment_emr: str
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

    category_id: int
    business_unit_id: int
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
    comment_emr: str = ""
    comment_bu: str = ""
    comment_bu_head: str = ""
    comment_cfo: str = ""

    @model_validator(mode="after")
    def _check_thresholds_order(self) -> "IndicatorCreateSchema":
        # Décroissants si "plus = mieux" (ex. taux de couverture), croissants
        # si "moins = mieux" (ex. absentéisme, nombre d'incidents).
        thresholds = [
            self.thresold_certified_without_reserves,
            self.thresold_acceptable,
            self.thresold_certified_with_significant_reserves,
            self.thresold_not_certified,
        ]
        if thresholds not in (sorted(thresholds), sorted(thresholds, reverse=True)):
            raise ValueError(
                "thresholds must be monotonic (all decreasing or all increasing): "
                "certified_without_reserves, acceptable, certified_with_significant_reserves, not_certified"
            )
        return self


# Certification ========================================================
class CertificationSchema(BaseModel):
    """Payload de certification d'un indicateur par un utilisateur BU / BU_HEAD / CFO."""

    status: str
    comment: str = ""

    @field_validator("status")
    @classmethod
    def _check_status(cls, value: str) -> str:
        if value not in CertificationStatus.__members__:
            raise ValueError(f"status must be one of: {', '.join(CertificationStatus.__members__)}")
        return value


# Settings =============================================================
class SettingsSchema(BaseModel):
    """Paramètres d'affichage modifiables depuis l'administration."""

    home_message: str = Field(min_length=1, max_length=1000)


# Campaigns ===========================================================
class CampaignSchema(_Schema):
    id: int
    name: str
    start_date: datetime
    end_date: datetime
    indicators: list[IndicatorSchema]


class CampaignCreateSchema(BaseModel):
    """Payload de création d'une campagne (indicateurs référencés par leurs ids)."""

    name: str = Field(min_length=1, max_length=100)
    start_date: datetime
    end_date: datetime
    indicator_ids: list[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_dates(self) -> "CampaignCreateSchema":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be after start_date")
        return self


class CampaignIndicatorSchema(_Schema):
    campain_id: int
    indicateur_id: int


class CampaignIndicatorCreateSchema(BaseModel):
    """Association d'un indicateur à une campagne (noms de champs du modèle)."""

    campain_id: int
    indicateur_id: int
