from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Dict, Any

from mock_data import MOCK_DATA

app = FastAPI(title="AI Family Pension & Wealth Monitor API")

# Add CORS middleware for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Verify the Firebase token. 
    In a real app, use firebase_admin.auth.verify_id_token() here.
    For this skeleton, we just ensure a token is passed.
    """
    token = credentials.credentials
    if not token or token == "undefined" or token == "null":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Temporary mock validation - returning a mock user dict
    return {"uid": "mock_user_id"}

@app.get("/api/portfolio")
def get_portfolio(user: dict = Depends(verify_token)):
    """
    Returns the JSON structure of the entire family portfolio.
    """
    return {
        "last_updated": MOCK_DATA["last_updated"],
        "portfolios": MOCK_DATA["portfolios"]
    }

@app.get("/api/action-items")
def get_action_items(user: dict = Depends(verify_token)):
    """
    Returns AI-generated recommendations (action items).
    """
    return MOCK_DATA["action_items"]

class ManualInvestment(BaseModel):
    id: str
    name: str
    description: str
    balance: float
    monthly_deposit: float
    expected_yearly_yield: float
    start_date: str
    end_date: str
    owner: str = "user" # user or spouse

@app.post("/api/manual-investment", status_code=status.HTTP_201_CREATED)
def add_manual_investment(investment: ManualInvestment, user: dict = Depends(verify_token)):
    """
    Endpoint to add manual alternative investments.
    """
    # In a real app we'd save this to a database and map to the specific user uid
    # For now, just return exactly what was posted back to indicate success
    return {"status": "success", "data": investment.model_dump()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
