from fastapi import APIRouter

from services import auth, plant as plant_svc

router = APIRouter()


@router.post("/heal-flashcard")
async def heal_flashcard(user: dict = auth.CurrentUser):
    state = plant_svc.apply_heal(user["id"], plant_svc.HEAL_PER_FLASHCARD)
    return {"plant": state, "healed": plant_svc.HEAL_PER_FLASHCARD}
