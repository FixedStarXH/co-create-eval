"""Local demo provisioning. No public registration endpoint is exposed."""
import argparse
import getpass
import os
from sqlmodel import Session, select
from app.config import database_url
from app.db import build_engine
from app.models import Participant, StudySession, TaskVersion
from app.security import hash_credential

SEQUENCES = {"S1": (("A", "AI"), ("B", "INDEPENDENT")), "S2": (("A", "INDEPENDENT"), ("B", "AI")), "S3": (("B", "AI"), ("A", "INDEPENDENT")), "S4": (("B", "INDEPENDENT"), ("A", "AI"))}

def provision(session: Session, code: str, credential: str, sequence: str) -> Participant:
    code = code.strip().upper()
    if not code or len(code) > 32 or len(credential) < 8 or sequence not in SEQUENCES:
        raise ValueError("Invalid code, credential or sequence")
    if session.exec(select(Participant).where(Participant.study_code == code)).first():
        raise ValueError("Participant code already exists")
    tasks = {}
    for task_code, title, scenario in [("A", "核验 AI 生成的学习资料", "设计一节帮助学生核验 AI 资料的课堂活动。"), ("B", "评价 AI 生成的学习建议", "设计一节帮助学生评价并调整 AI 学习建议的课堂活动。")]:
        task = session.exec(select(TaskVersion).where(TaskVersion.task_code == task_code, TaskVersion.version == "demo-1")).first()
        if task is None:
            task = TaskVersion(task_code=task_code, version="demo-1", title=title, scenario=scenario, instructions="请填写目标、学生任务、活动流程、资源和评价方式。", status="PUBLISHED")
            session.add(task)
            session.flush()
        tasks[task_code] = task
    participant = Participant(study_code=code, credential_hash=hash_credential(credential), sequence=sequence)
    session.add(participant)
    session.flush()
    for number, (task_code, condition) in enumerate(SEQUENCES[sequence], 1):
        session.add(StudySession(participant_id=participant.id, task_version_id=tasks[task_code].id, round_no=number, condition=condition))
    session.commit()
    session.refresh(participant)
    return participant

def main():
    parser = argparse.ArgumentParser(description="Create a local demonstration participant")
    parser.add_argument("--code", required=True)
    parser.add_argument("--sequence", choices=SEQUENCES, default="S1")
    args = parser.parse_args()
    if os.environ.get("APP_MODE") != "demo":
        parser.error("Local demo provisioning requires APP_MODE=demo")
    password = getpass.getpass("Set demo access credential (8+ characters): ")
    engine = build_engine(database_url())
    try:
        with Session(engine) as session:
            provision(session, args.code, password, args.sequence)
        print("Demo participant created.")
    finally:
        engine.dispose()

if __name__ == "__main__":
    main()
