from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy import create_engine, Column, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.sql import func
import os
import boto3
import logging
import json
from botocore.exceptions import ClientError
from pydantic import BaseModel
from typing import Optional, Dict, Any
from model import User, AWSMarketplaceInfo
from mangum import Mangum
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_secret(secret_name: str, region_name: str) -> Dict[str, Any]:
    session = boto3.session.Session(
        aws_access_key_id=os.getenv("aws_access_key"),
        aws_secret_access_key=os.getenv("aws_secret_key"),
        region_name=region_name
    )
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )

    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
        
        if 'SecretString' in get_secret_value_response:
            secret = get_secret_value_response['SecretString']
        else:
            secret = get_secret_value_response['SecretBinary']
        
        return json.loads(secret)

    except ClientError as e:
        logging.error(f"Error retrieving secret: {e}")
        raise e

# Get RDS credentials from AWS Secrets Manager
rds_secret_name = "rds!db-1edec54a-39ae-4434-bc86-34b44cff4f1f"
region_name = "us-east-1"
rds_credentials = get_secret(rds_secret_name, region_name)
RDS_DB_USER = rds_credentials.get("username")
RDS_DB_PASSWORD = rds_credentials.get("password")

# Get database connection details
db_secret_name = "marketplace1"
db_credentials = get_secret(db_secret_name, region_name)
RDS_DB_NAME = db_credentials.get("dbname")
RDS_DB_HOST = db_credentials.get("host")
RDS_DB_PORT = db_credentials.get("port")

# Configure database connection
DATABASE_URL = f"postgresql://{RDS_DB_USER}:{RDS_DB_PASSWORD}@{RDS_DB_HOST}:{RDS_DB_PORT}/{RDS_DB_NAME}"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create FastAPI app
app = FastAPI(
    title="AWS Marketplace Integration",
    description="API for AWS Marketplace customer resolution",
    version="1.0.0"
)

# Configure AWS Lambda handler
handler = Mangum(app)

# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def resolve_customer(reg_token: str, db: Session) -> Dict[str, Any]:
    try:
        if not reg_token:
            raise HTTPException(
                status_code=400,
                detail="Registration Token is missing"
            )

        marketplace_client = boto3.client(
            "meteringmarketplace",
            region_name="us-east-1",
            aws_access_key_id=os.getenv("aws_access_key"),
            aws_secret_access_key=os.getenv("aws_secret_key"),
        )
        
        try:
            customer_data = marketplace_client.resolve_customer(
                RegistrationToken=reg_token
            )
        except ClientError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to resolve marketplace customer: {str(e)}"
            )

        product_code = customer_data["ProductCode"]
        customer_id = customer_data["CustomerIdentifier"]
        customer_aws_account_id = customer_data["CustomerAWSAccountId"]
        
        try:
            # Check if the customer is already registered
            aws_marketplace_info = db.query(AWSMarketplaceInfo).filter(
                AWSMarketplaceInfo.customer_id == customer_id
            ).first()

            if aws_marketplace_info:
                marketplace_id = aws_marketplace_info.id
            else:
                # Create new AWS Marketplace Info
                new_aws_marketplace_info = AWSMarketplaceInfo(
                    product_code=product_code,
                    customer_id=customer_id,
                    customer_aws_account_id=customer_aws_account_id
                )
                db.add(new_aws_marketplace_info)
                db.commit()
                db.refresh(new_aws_marketplace_info)
                marketplace_id = new_aws_marketplace_info.id

            return {"status": "redirect", "customer_id": marketplace_id}

        except Exception as db_error:
            db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Database operation failed: {str(db_error)}"
            )

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(e)}"
        )

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "healthy", "message": "Server is running"}

@app.post("/resolve_customer")
async def resolve_customer_handler(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Handle AWS Marketplace customer resolution
    
    This endpoint:
    1. Receives the AWS Marketplace registration token
    2. Resolves the customer using AWS Marketplace API
    3. Creates or retrieves customer information
    4. Redirects to the application with customer ID
    """
    try:
        form_data = await request.form()
        reg_token = form_data.get("x-amzn-marketplace-token")
        
        if not reg_token:
            raise HTTPException(
                status_code=400,
                detail="Missing marketplace token"
            )
            
        result = resolve_customer(reg_token, db)
        
        if result.get("status") == "redirect":
            return RedirectResponse(
                url=f"https://salesanalyticsengine.goml.io/?atrs={result['customer_id']}",
                status_code=302,
            )
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to resolve customer"
            )
            
    except HTTPException as he:
        return {"error": he.detail}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
