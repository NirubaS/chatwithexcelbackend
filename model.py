from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    customer_id = Column(Integer, ForeignKey('product_customers.id'), unique=True)
    
    # Relationship
    aws_marketplace_info = relationship(
        "AWSMarketplaceInfo",
        back_populates="user",
        uselist=False
    )

class AWSMarketplaceInfo(Base):
    __tablename__ = 'product_customers'

    id = Column(Integer, primary_key=True, index=True)
    product_code = Column(String(100), nullable=False)
    customer_id = Column(String(100), unique=True, nullable=False)
    customer_aws_account_id = Column(String(100), nullable=False)
    
    # Relationship
    user = relationship(
        "User",
        back_populates="aws_marketplace_info",
        uselist=False
    )
