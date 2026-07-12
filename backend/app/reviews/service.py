"""POST/GET /v1/me/review (D-93c): one review per user, upserted.

Uniqueness is enforced at the DB layer (reviews.user_id UNIQUE), so this is
a straightforward select-then-insert-or-update, not a request-scoped
idempotency-key scheme like POST /attempts -- an upsert converges to the
same row no matter how many times it's retried, which is the only property
"idempotent" needs to mean here.
"""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Review, ReviewHistory, User
from app.schemas.reviews import ReviewRequest, ReviewResponse, ReviewStatusResponse


def _to_response(review: Review) -> ReviewResponse:
    return ReviewResponse(
        rating=review.rating,
        body=review.body,
        created_at=review.created_at,
        updated_at=review.updated_at,
    )


async def upsert_review(db: AsyncSession, user: User, payload: ReviewRequest) -> ReviewResponse:
    review = await db.scalar(select(Review).where(Review.user_id == user.id))
    if review is None:
        review = Review(user_id=user.id, rating=payload.rating, body=payload.body)
        db.add(review)
    else:
        # A Core UPDATE, not ORM attribute assignment: POST /v1/me/review
        # means "the user submitted a review right now" and updated_at must
        # advance even when the resubmitted rating/body are byte-identical
        # to what's stored (the "review us again" flow pre-fills the form
        # with the existing values, so an unedited resubmit is expected).
        # ORM attribute assignment skips the UPDATE -- and therefore the
        # trg_reviews_touch trigger -- when SQLAlchemy sees no column
        # actually changed; this always issues the statement.
        await db.execute(
            update(Review)
            .where(Review.user_id == user.id)
            .values(rating=payload.rating, body=payload.body),
        )
    db.add(ReviewHistory(user_id=user.id, rating=payload.rating, body=payload.body))
    await db.flush()
    await db.commit()
    await db.refresh(review)
    return _to_response(review)


async def get_review_status(db: AsyncSession, user: User) -> ReviewStatusResponse:
    review = await db.scalar(select(Review).where(Review.user_id == user.id))
    if review is None:
        return ReviewStatusResponse(reviewed=False, review=None)
    return ReviewStatusResponse(reviewed=True, review=_to_response(review))
