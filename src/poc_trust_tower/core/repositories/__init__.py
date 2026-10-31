"""Repos en mémoire de l'application, un module par repo.

Ce package ré-exporte tout (y compris quelques noms privés utilisés par le bootstrap
et les tests) ; `poc_trust_tower.core.repository` en est la façade historique.
"""

from ._base import (  # noqa: F401
    _HIGH_WATER_IDS,
    _NOW,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    _find,
    _name_taken,
    _next_id,
)
from .audits import (  # noqa: F401
    AUDITED_FIELDS,
    _audit_repr,
    _build_audit_seed,
    _record_audit,
    _record_diff,
    _snapshot,
    audit_trail,
    indicator_audit_trail,
    indicator_source_file,
    repoIndicatorAudits,
)
from .business_units import (  # noqa: F401
    _BU_SEED,
    create_business_unit,
    delete_business_unit,
    get_business_unit,
    repoBusinessUnits,
    update_business_unit,
)
from .campaign_indicators import (  # noqa: F401
    _set_campaign_links,
    add_campaign_indicator,
    campaign_indicator_counts,
    campaign_indicator_ids,
    campaign_indicator_links,
    campaign_indicators,
    campaigns_of_indicator,
    indicator_in_active_campaign,
    remove_campaign_indicator,
    repoCampaignIndicators,
    set_campaign_indicators,
)
from .campaigns import (  # noqa: F401
    _apply_campaign_payload,
    _build_campaigns,
    active_campaigns,
    create_campaign,
    delete_campaign,
    get_campaign,
    repoCampaigns,
    update_campaign,
)
from .categories import (  # noqa: F401
    create_category,
    delete_category,
    get_category,
    repoCategories,
    update_category,
)
from .certifications import (  # noqa: F401
    CERTIFICATION_FIELDS,
    can_certify,
    can_view_indicator,
    certification_denial,
    certify_indicator,
    visible_indicators,
)
from .indicators import (  # noqa: F401
    _COMMITTEES,
    _NATURES,
    _STATUSES,
    _UNITS,
    VariationFilter,
    _apply_indicator_payload,
    _build_indicator,
    _compute_variation,
    create_indicator,
    delete_indicator,
    distinct_categories,
    distinct_statuses,
    filter_indicators,
    get_indicator,
    repoIndicators,
    update_indicator,
    variation_kind,
)
from .settings import (  # noqa: F401
    DEFAULT_HOME_MESSAGE,
    get_home_message,
    repoSettings,
    update_settings,
)
from .users import (  # noqa: F401
    _build_users,
    _demo_hash,
    change_password,
    create_user,
    delete_user,
    get_user,
    repoUsers,
    update_user,
)

# Jeu de démonstration de l'audit : construit une fois tous les repos chargés.
repoIndicatorAudits.extend(_build_audit_seed())

__all__ = [name for name in dir() if not name.startswith("__")]
