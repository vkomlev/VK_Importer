"""Хранилище данных о видео."""

from .database import VideoStorage, VideoRecord
from .duplicate_detector import DuplicateDetector
from .job_queue import JobQueue, JobRecord, STATUS_PENDING, STATUS_RUNNING, STATUS_DONE, STATUS_FAILED

__all__ = [
    "VideoStorage", "VideoRecord", "DuplicateDetector",
    "JobQueue", "JobRecord", "STATUS_PENDING", "STATUS_RUNNING", "STATUS_DONE", "STATUS_FAILED",
]
