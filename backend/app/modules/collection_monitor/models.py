from datetime import datetime
from sqlalchemy import Integer,Text,DateTime
from sqlalchemy.orm import Mapped,mapped_column
from app.core.database import Base
from app.core.datetime_utils import utc_now

class GovernmentCollectionConfiguration(Base):
    __tablename__='government_collection_configurations'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    revision:Mapped[int]=mapped_column(Integer,nullable=False)
    payload:Mapped[str]=mapped_column(Text,nullable=False)
    updated_by:Mapped[int]=mapped_column(Integer,nullable=False)
    updated_at:Mapped[datetime]=mapped_column(DateTime,default=utc_now,nullable=False)

class GovernmentCollectionConfigurationHistory(Base):
    __tablename__='government_collection_configuration_histories'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    revision:Mapped[int]=mapped_column(Integer,nullable=False)
    payload:Mapped[str]=mapped_column(Text,nullable=False)
    actor_id:Mapped[int]=mapped_column(Integer,nullable=False)
    backup_name:Mapped[str]=mapped_column(Text,nullable=False)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=utc_now,nullable=False)
