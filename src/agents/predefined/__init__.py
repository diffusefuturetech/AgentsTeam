from src.agents.predefined.ceo import get_role_data as ceo_role
from src.agents.predefined.product_manager import get_role_data as pm_role
from src.agents.predefined.engineer import get_role_data as engineer_role
from src.agents.predefined.designer import get_role_data as designer_role
from src.agents.predefined.qa_engineer import get_role_data as qa_role
from src.agents.predefined.operations import get_role_data as operations_role

PREDEFINED_ROLES = [
    ceo_role(),
    pm_role(),
    engineer_role(),
    designer_role(),
    qa_role(),
    operations_role(),
]
