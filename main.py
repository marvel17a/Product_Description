# main.py
import os
import requests
import google.generativeai as genai
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta, datetime
from typing import List, Optional
from jose import JWTError, jwt
from passlib.context import CryptContext

# Import our files
import models, database
from database import engine, get_db
from pydantic import BaseModel

# --- SECURITY CONFIG ---
SECRET_KEY = "CHANGE_THIS_TO_A_LONG_RANDOM_STRING" # Used to sign the digital ID cards
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# Create Tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static", html=True), name="static")

# --- PYDANTIC SCHEMAS (Validation) ---
class UserCreate(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class ProductRequest(BaseModel):
    product_name: str

class ProductResponse(BaseModel):
    name: str
    description: str
    image_url: str
    created_at: datetime

# --- HELPER FUNCTIONS ---
def get_password_hash(password):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# --- DEPENDENCY: GET CURRENT USER ---
# This function checks if the user is logged in for every protected page
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid credentials")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    user = db.query(models.User).filter(models.User.email == email).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user

# --- AUTH ENDPOINTS ---

@app.post("/register")
def register(user: UserCreate, db: Session = Depends(get_db)):
    # Check if user exists
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create new user
    hashed_pw = get_password_hash(user.password)
    # FIRST USER TRICK: If table is empty, make first user Admin automatically
    is_first_user = db.query(models.User).count() == 0
    
    new_user = models.User(email=user.email, hashed_password=hashed_pw, is_admin=is_first_user)
    db.add(new_user)
    db.commit()
    return {"message": "User created successfully"}

@app.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    
    # Generate Token
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

# --- APP ENDPOINTS (PROTECTED) ---

@app.post("/generate")
def generate(request: ProductRequest, 
             current_user: models.User = Depends(get_current_user), 
             db: Session = Depends(get_db)):
    
    # 1. AI Logic (Gemini)
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    model = genai.GenerativeModel('gemini-pro')
    prompt = f"Act as SEO expert. Describe {request.product_name} in 100 words with keywords."
    try:
        ai_resp = model.generate_content(prompt)
        desc = ai_resp.text
    except:
        desc = "AI Service unavailable. Try again."

    # 2. Image Logic (Unsplash)
    unsplash_key = os.getenv("UNSPLASH_ACCESS_KEY")
    u_url = f"https://api.unsplash.com/search/photos?query={request.product_name}&client_id={unsplash_key}&per_page=1"
    try:
        img_data = requests.get(u_url).json()
        img_url = img_data['results'][0]['urls']['regular'] if img_data['results'] else "https://via.placeholder.com/400"
    except:
        img_url = "https://via.placeholder.com/400"

    # 3. Save to DB (Linked to Current User)
    new_prod = models.Product(
        name=request.product_name, 
        description=desc, 
        image_url=img_url, 
        owner_id=current_user.id
    )
    db.add(new_prod)
    db.commit()
    
    return {"name": request.product_name, "description": desc, "image": img_url}

@app.get("/my-history")
def get_history(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(models.Product).filter(models.Product.owner_id == current_user.id).all()

# --- ADMIN PANEL ---
@app.get("/admin/stats")
def admin_stats(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    total_users = db.query(models.User).count()
    total_products = db.query(models.Product).count()
    all_users = db.query(models.User).all()
    
    return {
        "total_users": total_users,
        "total_products": total_products,
        "users": [{"email": u.email, "id": u.id} for u in all_users]
  }
               
