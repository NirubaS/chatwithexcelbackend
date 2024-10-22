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
    customer_id = Column(String(100), ForeignKey('product_customers.customer_id'))
    
    # Relationship
    aws_marketplace_info = relationship("AWSMarketplaceInfo", back_populates="users")

class AWSMarketplaceInfo(Base):
    __tablename__ = 'product_customers'

    id = Column(Integer, primary_key=True, index=True)
    product_code = Column(String(100), nullable=False)
    customer_id = Column(String(100), unique=True, nullable=False)
    customer_aws_account_id = Column(String(100), nullable=False)
    
    # Relationship
    users = relationship("User", back_populates="aws_marketplace_info")