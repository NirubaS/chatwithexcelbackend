import os
import boto3
from sqlalchemy.orm import Session
import sys
sys.path.append("")
from model import User, AWSMarketplaceInfo
from app import get_db_connection
import logging

# load the access key and secret key from the environment variables
access_key = os.environ.get("aws_access_key")
secret_key = os.environ.get("aws_secret_key")

def resolve_customer(reg_token: str, db: Session):
    try:
        if reg_token:
            marketplace_client = boto3.client(
                "meteringmarketplace",
                region_name="us-east-1",
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
            )
            customer_data = marketplace_client.resolve_customer(
                RegistrationToken=reg_token
            )
            product_code = customer_data["ProductCode"]
            customer_id = customer_data["CustomerIdentifier"]
            customer_aws_account_id = customer_data["CustomerAWSAccountId"]
            
            # Check if the customer is already registered
            aws_marketplace_info = db.query(AWSMarketplaceInfo).filter(AWSMarketplaceInfo.customer_id == customer_id).first()

            if aws_marketplace_info:
                return {"status": "redirect", "customer_id": aws_marketplace_info.id}
            else:
                # Register the customer
                new_aws_marketplace_info = AWSMarketplaceInfo(
                    product_code=product_code,
                    customer_id=customer_id,
                    customer_aws_account_id=customer_aws_account_id
                )
                db.add(new_aws_marketplace_info)
                db.commit()
                db.refresh(new_aws_marketplace_info)
                return {"status": "redirect", "customer_id": new_aws_marketplace_info.id}

        else:
            return {"error": "Registration Token is missing"}

    except Exception as e:
        db.rollback()
        return {"error": str(e)}

def get_entitlements(customer_id : str):
    try:
       
        marketplace_client = boto3.client(
            "marketplace-entitlement",
            region_name="us-east-1",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )
        entitlements = marketplace_client.get_entitlements(
            ProductCode="db70sghlx0y4s77pfepvtx74q",
            Filter={"CUSTOMER_IDENTIFIER": [customer_id]},
        )
        
        return {
            "status": "success",
            "entitlements": entitlements,
        }
            
    except Exception as e:
        return {"error": str(e)}
    
def get_marketplace_customer_id(email):
    print(email)
    conn = get_db_connection()
    if not conn:
        logging.error("Unable to connect to the database")
        return None

    cur = conn.cursor()
    try:
        cur.execute("SELECT customer_id FROM users WHERE email = %s", (email,))
        result = cur.fetchone()
        print(result)
        if not result:
            logging.error(f"No user found with email: {email}")
            return None
        
        user_customer_id = result[0]
        print(user_customer_id)

        cur.execute("SELECT customer_id FROM product_customers WHERE id = %s", (user_customer_id,))
        result = cur.fetchone()
        
        if not result:
            logging.error(f"No product customer found for user customer_id: {user_customer_id}")
            return None
        print(result[0])
        return result[0] 
    # This is the marketplace customer_id
    except Exception as e:
        logging.error(f"Error retrieving marketplace customer ID: {e}")
        return None
    finally:
        cur.close()
        conn.close()

# Example usage
email = "sathish@gmail.com"  # Replace with the actual email
customer_id = get_marketplace_customer_id(email)

if customer_id:
    print(f"Marketplace customer ID: {customer_id}")
else:
    print("Customer ID not found.")

    
if  __name__ == "__main__":
    
    result = get_entitlements(customer_id)
    print(result)
    
    if result and result["status"] == "success":
        date = result["entitlements"]["ResponseMetadata"]["HTTPHeaders"]["date"]
        print(f"Date: {date}")
    else:
        print("Failed to retrieve entitlements or entitlements response is missing.")