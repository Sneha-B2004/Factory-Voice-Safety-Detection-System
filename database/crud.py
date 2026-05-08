from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
import pymysql
from .config import DATABASE_URL, MYSQL_USER, MYSQL_PASSWORD, MYSQL_HOST, MYSQL_PORT, MYSQL_DATABASE
from .models import Base, DetectionHistory

engine = create_engine(DATABASE_URL)

# 🔥 THREAD SAFE SESSION
SessionLocal = scoped_session(sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
))

def init_db():
    try:
        conn = pymysql.connect(
            host=MYSQL_HOST,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            port=int(MYSQL_PORT)
        )
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {MYSQL_DATABASE}")
        conn.close()
        print(f"DB '{MYSQL_DATABASE}' ready.")
    except Exception as e:
        print("DB error:", e)

    Base.metadata.create_all(bind=engine)


def add_detection(keyword_detected: str, status: str, confidence: float):
    db = SessionLocal()
    try:
        record = DetectionHistory(
            keyword_detected=keyword_detected,
            status=status,
            confidence=confidence
        )
        db.add(record)
        db.commit()
        db.refresh(record)

        print("DB SAVED:", record.id)

        # Also write to JSONL so the AI chatbot can read events
        import json, os, time as _time
        jsonl_path = os.getenv("DASHBOARD_EVENTS_PATH", "dashboard_events.jsonl")
        event = {
            "event_type": "detection",
            "alarm_type": keyword_detected.upper(),
            "action": "alert_triggered",
            "severity": "high" if keyword_detected in ["fire", "help"] else "medium",
            "emergency": status == "DANGER",
            "notify_supervisor": status == "DANGER",
            "keyword": keyword_detected,
            "confidence": round(confidence, 3),
            "threshold": 0.85,
            "noise_level": 0.0,
            "device_id": os.getenv("DEVICE_ID", "edge-device-1"),
            "zone": os.getenv("FACTORY_ZONE", "factory-floor"),
            "repeated_count": 1,
            "timestamp": record.timestamp.timestamp(),
            #"detection_source": "stt_confirmed",
            #"decision_source": "consensus",
            #"reason": f"{keyword_detected} confirmed by STT and AI model"
        }
        with open(jsonl_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")

        return record
    except Exception as e:
        db.rollback()
        print("DB ERROR:", e)
    finally:
        db.close()


def get_history(limit: int = 50):
    db = SessionLocal()
    try:
        data = db.query(DetectionHistory)\
            .order_by(DetectionHistory.timestamp.desc())\
            .limit(limit)\
            .all()
        return data
    finally:
        db.close()