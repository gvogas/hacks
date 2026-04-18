from fastapi import APIRouter

from models.schemas import PurchaseUpgradeRequest, StudyTickRequest
from services import auth, shop

router = APIRouter()


@router.get("/state")
async def get_shop_state(user: dict = auth.CurrentUser):
    return shop.get_shop_state(user["id"])


@router.post("/study-tick")
async def study_tick(req: StudyTickRequest, user: dict = auth.CurrentUser):
    return shop.record_study_time(user["id"], req.elapsed_seconds)


@router.post("/purchase")
async def purchase(req: PurchaseUpgradeRequest, user: dict = auth.CurrentUser):
    return shop.purchase_upgrade(user["id"], req.upgrade_id)
