"""Identity boundary for the future student score module."""

from app.services.authorization import require_student_masv


class StudentScoreService:
    def own_masv(self) -> str:
        """Return the student ID from the session; callers cannot supply another ID."""
        return require_student_masv()
