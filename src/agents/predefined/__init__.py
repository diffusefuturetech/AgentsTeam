from src.agents.predefined.ceo import get_role_data as ceo_role
from src.agents.predefined.douyin_strategist import get_role_data as douyin_role
from src.agents.predefined.xiaohongshu_specialist import get_role_data as xiaohongshu_role
from src.agents.predefined.growth_hacker import get_role_data as growth_role
from src.agents.predefined.ai_citation_strategist import get_role_data as citation_role
from src.agents.predefined.ui_designer import get_role_data as ui_role
from src.agents.predefined.content_creator import get_role_data as content_role

PREDEFINED_ROLES = [
    ceo_role(),
    douyin_role(),
    xiaohongshu_role(),
    growth_role(),
    citation_role(),
    ui_role(),
    content_role(),
]
