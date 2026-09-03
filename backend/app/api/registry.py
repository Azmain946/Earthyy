from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.registry import ModelRegistryEntry
from app.models.user import User

router = APIRouter(prefix="/models", tags=["model-registry"])


@router.get("")
def list_models(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    entries = db.query(ModelRegistryEntry).order_by(ModelRegistryEntry.module).all()
    return [
        {
            "id": e.id, "model_name": e.model_name, "version": e.version, "module": e.module,
            "model_type": e.model_type, "source": e.source, "input_requirements": e.input_requirements,
            "output_type": e.output_type, "status": e.status, "metrics": e.metrics,
            "limitations": e.limitations,
        }
        for e in entries
    ]
