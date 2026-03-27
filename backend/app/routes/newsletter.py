"""
Newsletter routes — integrates with GoHighLevel for contact management and email delivery.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
import httpx

from app.config import settings

router = APIRouter(prefix="/v1/newsletter", tags=["newsletter"])


class NewsletterSubscribeRequest(BaseModel):
    email: EmailStr
    first_name: str | None = None
    last_name: str | None = None


class NewsletterSubscribeResponse(BaseModel):
    status: str
    message: str
    contact_id: str | None = None


@router.post("/subscribe", response_model=NewsletterSubscribeResponse)
async def subscribe_to_newsletter(request: NewsletterSubscribeRequest):
    """
    Subscribe an email to the newsletter.
    Creates a contact in GoHighLevel, which triggers the "AgentID Developer Onboarding" workflow.
    """
    if not settings.GHL_LOCATION_ACCESS_TOKEN:
        raise HTTPException(
            status_code=500,
            detail="GHL_LOCATION_ACCESS_TOKEN not configured"
        )

    # Create contact in GHL
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{settings.GHL_API_URL}/contacts/",
                headers={
                    "Authorization": f"Bearer {settings.GHL_LOCATION_ACCESS_TOKEN}",
                    "Content-Type": "application/json",
                    "Version": "2021-07-28",
                },
                json={
                    "locationId": settings.GHL_LOCATION_ID,
                    "email": request.email,
                    "firstName": request.first_name or "Newsletter",
                    "lastName": request.last_name or "Subscriber",
                    "source": "newsletter_signup",
                    "tags": ["early-access"],
                },
                timeout=10.0,
            )

            print(f"[INFO] GHL response {response.status_code}: {response.text[:500]}")
            if response.status_code in (200, 201):
                data = response.json()
                contact_id = data.get("contact", {}).get("id") or data.get("id")
                return NewsletterSubscribeResponse(
                    status="success",
                    message="Successfully subscribed to newsletter. Welcome!",
                    contact_id=contact_id,
                )
            else:
                print(f"[WARN] GHL contact creation returned {response.status_code}: {response.text}")
                return NewsletterSubscribeResponse(
                    status="pending",
                    message="Subscription received. Please check your email.",
                    contact_id=None,
                )

        except httpx.RequestError as e:
            print(f"[ERROR] GHL API request failed: {e}")
            raise HTTPException(
                status_code=500,
                detail="Failed to process subscription. Please try again."
            )
        except Exception as e:
            print(f"[ERROR] Unexpected error during subscription: {e}")
            raise HTTPException(
                status_code=500,
                detail="An unexpected error occurred."
            )
