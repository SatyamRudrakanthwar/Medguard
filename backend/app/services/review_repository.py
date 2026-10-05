"""
ReviewRepository — all database operations for review records.
Keeps raw SQLAlchemy queries out of the API layer.
"""
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.models import ReviewStatus
from app.services.db_models import ReviewRecord, ReviewStatusEnum

logger = logging.getLogger(__name__)


class ReviewRepository:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def create(self, review_id: str, request_data: dict) -> ReviewRecord:
        record = ReviewRecord(
            id=review_id,
            status=ReviewStatusEnum.pending,
            patient_age=request_data["age"],
            patient_conditions=request_data.get("conditions", []),
            medications_input=request_data["medications"],
            user_question=request_data["question"],
        )
        self._db.add(record)
        await self._db.flush()
        return record

    async def get(self, review_id: str) -> Optional[ReviewRecord]:
        result = await self._db.execute(
            select(ReviewRecord).where(ReviewRecord.id == review_id)
        )
        return result.scalar_one_or_none()

    async def list_recent(self, limit: int = 20) -> list[ReviewRecord]:
        result = await self._db.execute(
            select(ReviewRecord)
            .order_by(desc(ReviewRecord.created_at))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update_status(self, review_id: str, status: ReviewStatusEnum) -> None:
        record = await self.get(review_id)
        if record:
            record.status = status
            record.updated_at = datetime.utcnow()
            await self._db.flush()

    async def complete(self, review_id: str, result_data: dict) -> None:
        record = await self.get(review_id)
        if record:
            record.status = ReviewStatusEnum.completed
            record.findings = result_data.get("findings")
            record.evidence = result_data.get("evidence")
            record.additional_information = result_data.get("additional_information", [])
            record.high_severity_count = result_data.get("high_severity_count", 0)
            record.research_retries = result_data.get("research_retries", 0)
            record.completed_at = datetime.utcnow()
            await self._db.flush()

    async def fail(self, review_id: str, error_message: str) -> None:
        record = await self.get(review_id)
        if record:
            record.status = ReviewStatusEnum.failed
            record.error_message = error_message
            record.updated_at = datetime.utcnow()
            await self._db.flush()
