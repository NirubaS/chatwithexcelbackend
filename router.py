from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
import boto3
import os
from model import User, AWSMarketplaceInfo

def resolve_customer(reg_token: str, db: Session):
    try:
        if reg_token:
            marketplace_client = boto3.client(
                "meteringmarketplace",
                region_name="us-east-1",
                aws_access_key_id=os.getenv("aws_access_key"),
                aws_secret_access_key=os.getenv("aws_secret_key"),
            )
            customer_data = marketplace_client.resolve_customer(
                RegistrationToken=reg_token
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

            except Exception as inner_e:
                db.rollback()
                raise HTTPException(
                    status_code=500,
                    detail=f"Database transaction failed: {str(inner_e)}"
                )

        else:
            raise HTTPException(
                status_code=400,
                detail="Registration Token is missing"
            )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Customer resolution failed: {str(e)}"
        )

@app.post("/resolve_customer")
async def resolve_customer_handler(request: Request, db=Depends(get_db)):
    try:
        form_data = await request.form()
        reg_token = form_data.get("x-amzn-marketplace-token")
        if not reg_token:
            raise HTTPException(status_code=400, detail="Missing marketplace token")
            
        result = resolve_customer(reg_token, db)
        
        if "status" in result and result["status"] == "redirect":
            return RedirectResponse(
                url=f"https://salesanalyticsengine.goml.io/?atrs={result['customer_id']}",
                status_code=302,
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to resolve customer")
            
    except HTTPException as e:
        return {"error": e.detail}
    except Exception as e:
        return {"error": str(e)}
