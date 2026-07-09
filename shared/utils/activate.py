# import mysql.connector

# conn = mysql.connector.connect(
#     host='localhost',
#     user='root',
#     password='123456',
#     database='arknights_toolbox'
# )
from sqlalchemy import String, BigInteger, DateTime, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from typing import Any
from datetime import datetime, timezone
import json

class Base(DeclarativeBase):
    pass
class Activity(Base):
    __tablename__ = "activities"
    name: Mapped[str] = mapped_column(String(128),primary_key=True)
    start_time: Mapped[int | None] = mapped_column(DateTime, nullable=True)  # Unix 秒
    end_time: Mapped[int | None] = mapped_column(DateTime, nullable=True)  # Unix 秒
engine = create_engine(
    "mysql+pymysql://root:123456@localhost/arknights?charset=utf8mb4"
)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

json_data = json.load(open(r'F:\项目\ArknightsData\ArknightsGameData\zh_CN\gamedata\excel\activity_table.json', 'r', encoding='utf-8'))
type_list = set[str]()
#activity_type = ["TYPE_ACT24SIDE","TYPE_ACT9D0","TYPE_ACT3D0","MINISTORY","TYPE_ACT4D0","TYPE_ACT5D0","TYPE_ACT17SIDE","TYPE_ACT36SIDE","TYPE_MAINSS","TYPE_ACT38SIDE","TYPE_ACT21SIDE","TYPE_ACT42SIDE"]
activity_type = ["MINISTORY","TYPE_MAINSS"]
activity = []
for basicInfo in json_data["basicInfo"].values():
    if basicInfo["type"].startswith("TYPE_ACT") or basicInfo["type"] in activity_type:
        if "复刻" not in basicInfo["name"]:
            item = {}
            item["name"] = basicInfo["name"]
            item["start_time"] = datetime.fromtimestamp(basicInfo["startTime"], timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            item["end_time"] = datetime.fromtimestamp(basicInfo["endTime"], timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            activity.append(item)
            with Session() as session:
                try:
                    session.add(Activity(name=item["name"], start_time=item["start_time"], end_time=item["end_time"]))
                    session.commit()
                except Exception as e:
                    session.rollback()
                    print(e)
print(activity)
print(len(activity))

# for basicInfo in json_data["basicInfo"].values():
#     type_list.add(basicInfo["type"])
# print(type_list)
