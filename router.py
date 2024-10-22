from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import RedirectResponse # You'll need to replace this with your actual database module
from aws_marketplace import resolve_customer 
from sqlalchemy import create_engine, Column, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.sql import func
from sqlalchemy.orm import Session,sessionmaker
import os
import boto3
import logging
import json
from botocore.exceptions import ClientError






def get_secret(secret_name, region_name):
    # Create a session using the loaded environment variables
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
        # Fetch the secret value
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
        
        # Return SecretString if available
        if 'SecretString' in get_secret_value_response:
            secret = get_secret_value_response['SecretString']
        else:
            secret = get_secret_value_response['SecretBinary']
        
        secret_dict = json.loads(secret)  # Parse secret JSON string
        return secret_dict

    except ClientError as e:
        print(f"Error retrieving secret: {e}")
        raise e

secret_name = "rds!db-1edec54a-39ae-4434-bc86-34b44cff4f1f"  # Replace with your secret name
region_name = "us-east-1"  # Replace with your AWS region

    # Get the secret
credentials = get_secret(secret_name, region_name)

    # Print credentials or do something with them
RDS_DB_USER = credentials.get("username")
RDS_DB_PASSWORD = credentials.get("password")
print(RDS_DB_USER, RDS_DB_PASSWORD)

secret_name = "marketplace1" 
credentials=get_secret(secret_name, region_name)

RDS_DB_NAME = credentials.get("dbname")
RDS_DB_HOST = credentials.get("host")
RDS_DB_PORT = credentials.get("port")

DATABASE_URL = f"postgresql://{RDS_DB_USER}:{RDS_DB_PASSWORD}@{RDS_DB_HOST}:{RDS_DB_PORT}/{RDS_DB_NAME}"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

app=FastAPI()
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/resolve_customer")
async def resolve_customer_handler(request: Request, db=Depends(get_db)):
    try:
        form_data = await request.form()
        reg_token = form_data.get("x-amzn-marketplace-token")
        if not reg_token:
            raise HTTPException(status_code=400, detail="Missing marketplace token")
        result = resolve_customer(reg_token, db)
        print(result)
        if "status" in result and result["status"] == "redirect":
            return RedirectResponse(
                url=f"https://salesanalyticsengine.goml.io/?atrs={result['customer_id']}"
,
                status_code=302,
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to resolve customer")
    except HTTPException as e:
        return {"error": e.detail}
    except Exception as e:
        return {"error": str(e)}