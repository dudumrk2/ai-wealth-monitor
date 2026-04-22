from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
import os
from pydantic import BaseModel
from typing import Optional, List
import db_manager
from auth import verify_token

router = APIRouter(tags=["alternatives"])

# Pydantic Schemas
class AltProject(BaseModel):
    id: Optional[str] = None
    name: str
    developer: str
    originalAmount: float
    currency: str
    startDate: str
    durationMonths: int
    expectedReturn: float
    status: str = "Active"
    actualExitDate: Optional[str] = None
    finalAmount: Optional[float] = None

class LeveragedPolicy(BaseModel):
    id: Optional[str] = None
    policyNumber: str
    name: str
    funderLink: str
    currentBalance: float
    baseMonth: str
    balloonLoanAmount: float
    interestRate: float
    initialDepositAmount: float
    initialRepaymentDate: str
    pdfUrl: Optional[str] = None

# --- Routes for Alternative Projects ---

@router.get("/api/alternatives/projects", response_model=List[AltProject])
async def get_projects(user: dict = Depends(verify_token)):
    uid = user.get("uid")
    if not uid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    
    projects = db_manager.get_alt_projects(uid)
    return projects

@router.post("/api/alternatives/projects")
async def add_project(project: AltProject, user: dict = Depends(verify_token)):
    uid = user.get("uid")
    if not uid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    
    doc_id = db_manager.add_alt_project(uid, project.model_dump(exclude_none=True))
    if not doc_id:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to add project")
    
    return {"status": "success", "id": doc_id}

# --- Routes for Leveraged Policies ---

@router.get("/api/alternatives/leveraged-policies", response_model=List[LeveragedPolicy])
async def get_leveraged_policies(user: dict = Depends(verify_token)):
    uid = user.get("uid")
    if not uid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    
    policies = db_manager.get_leveraged_policies(uid)
    return policies

@router.post("/api/alternatives/leveraged-policies")
async def add_leveraged_policy(policy: LeveragedPolicy, user: dict = Depends(verify_token)):
    uid = user.get("uid")
    if not uid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    
    data = policy.model_dump(exclude_none=True)
    if "policyNumber" in data:
        data["id"] = data["policyNumber"]

    doc_id = db_manager.add_leveraged_policy(uid, data)
    if not doc_id:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to add leveraged policy")
    
    return {"status": "success", "id": doc_id}

@router.post("/api/alternatives/upload-pdf")
async def upload_alt_pdf(file: UploadFile = File(...), user: dict = Depends(verify_token)):
    uid = user.get("uid")
    if not uid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    
    try:
        from routers.documents import upload_to_firebase_storage
        file_bytes = await file.read()
        url = upload_to_firebase_storage(file_bytes, uid, file.filename)
        return {"status": "success", "url": url}
    except Exception as e:
        print(f"Error uploading pdf: {e}")
        raise HTTPException(status_code=500, detail="Upload failed")
