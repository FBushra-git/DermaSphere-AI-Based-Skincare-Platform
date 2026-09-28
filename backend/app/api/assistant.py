from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import (
    AIConversation,
    AIRecommendation,
    Ingredient,
    Inventory,
    Product,
    ProductStatus,
    Review,
    Role,
    SkinConcern,
    User,
    UserSkinProfile,
    product_ingredients,
    product_skin_concerns,
    product_skin_types,
    profile_skin_concerns,
)
from app.schemas import AIChatInput

router = APIRouter(prefix="/api/ai", tags=["skincare assistant"])


@router.post("/chat")
def chat(
    payload: AIChatInput,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role == Role.ADMIN:
        raise HTTPException(
            status_code=403,
            detail=(
                "The skincare assistant is available to customer and seller accounts"
            ),
        )

    profile = db.scalar(
        select(UserSkinProfile).where(UserSkinProfile.user_id == user.id)
    )
    skin_type_id = payload.skin_type_id or (profile.skin_type_id if profile else None)
    concern_ids = set(payload.skin_concern_ids)
    if not concern_ids and profile:
        concern_ids.update(
            db.scalars(
                select(profile_skin_concerns.c.skin_concern_id).where(
                    profile_skin_concerns.c.profile_id == profile.id
                )
            ).all()
        )
    budget = (
        payload.budget_max
        if payload.budget_max is not None
        else profile.budget_max
        if profile
        else None
    )

    statement = (
        select(Product, Inventory.available_quantity)
        .join(Inventory, Inventory.product_id == Product.id)
        .where(
            Product.status == ProductStatus.APPROVED,
            Inventory.available_quantity > 0,
        )
    )
    if payload.category_id:
        statement = statement.where(Product.category_id == payload.category_id)
    if budget is not None:
        statement = statement.where(Product.price <= budget)
    candidates = db.execute(
        statement.order_by(Product.created_at.desc()).limit(200)
    ).all()
    product_ids = [product.id for product, _ in candidates]

    type_matches: dict[str, set[str]] = {}
    concern_matches: dict[str, set[str]] = {}
    ingredient_matches: dict[str, set[str]] = {}
    if product_ids:
        type_rows = db.execute(
            select(
                product_skin_types.c.product_id, product_skin_types.c.skin_type_id
            ).where(product_skin_types.c.product_id.in_(product_ids))
        )
        for product_id, type_id in type_rows:
            type_matches.setdefault(product_id, set()).add(type_id)

        concern_rows = db.execute(
            select(
                product_skin_concerns.c.product_id,
                product_skin_concerns.c.skin_concern_id,
            ).where(product_skin_concerns.c.product_id.in_(product_ids))
        )
        for product_id, concern_id in concern_rows:
            concern_matches.setdefault(product_id, set()).add(concern_id)

        search_terms = [
            word for word in payload.query.casefold().split() if len(word) >= 4
        ]
        if search_terms:
            ingredient_rows = db.execute(
                select(product_ingredients.c.product_id, Ingredient.name)
                .join(Ingredient, Ingredient.id == product_ingredients.c.ingredient_id)
                .where(
                    product_ingredients.c.product_id.in_(product_ids),
                    or_(*(Ingredient.name.ilike(f"%{word}%") for word in search_terms)),
                )
            )
            for product_id, name in ingredient_rows:
                ingredient_matches.setdefault(product_id, set()).add(name)

        rating_rows = db.execute(
            select(Product.id, func.avg(Review.rating))
            .outerjoin(Review, Review.product_id == Product.id)
            .where(Product.id.in_(product_ids))
            .group_by(Product.id)
        ).all()
        ratings = {product_id: float(value or 0) for product_id, value in rating_rows}
    else:
        ratings = {}

    ranked = []
    for product, quantity in candidates:
        matched_skin_type = bool(
            skin_type_id and skin_type_id in type_matches.get(product.id, set())
        )
        matched_concerns = concern_ids.intersection(
            concern_matches.get(product.id, set())
        )
        matched_ingredients = ingredient_matches.get(product.id, set())
        score = (
            (3 if matched_skin_type else 0)
            + 2 * len(matched_concerns)
            + min(2, len(matched_ingredients))
            + ratings.get(product.id, 0) / 5
        )
        reasons = []
        if matched_skin_type:
            reasons.append("matches your selected skin type")
        if matched_concerns:
            names = db.scalars(
                select(SkinConcern.name).where(SkinConcern.id.in_(matched_concerns))
            ).all()
            reasons.append("supports your concern for " + ", ".join(names))
        if matched_ingredients:
            reasons.append("contains " + ", ".join(sorted(matched_ingredients)))
        if budget is not None:
            reasons.append("fits your selected budget")
        if ratings.get(product.id, 0):
            reasons.append(f"has a {ratings[product.id]:.1f}/5 average customer rating")
        ranked.append((score, product, quantity, reasons))

    ranked.sort(
        key=lambda row: (row[0], ratings.get(row[1].id, 0), row[1].created_at),
        reverse=True,
    )
    selected = ranked[: payload.limit]

    caution = (
        "I can share general skincare information, but I cannot diagnose skin "
        "conditions or replace professional medical advice."
    )
    concerning_terms = (
        "diagnose",
        "prescription",
        "infection",
        "bleeding",
        "severe pain",
        "swelling",
        "allergic reaction",
    )
    if any(term in payload.query.casefold() for term in concerning_terms):
        response_text = (
            "For these symptoms, contact a qualified healthcare professional. "
            + caution
        )
    elif selected:
        response_text = (
            "Here are in-stock DermaSphere products that best match your skin details "
            "and budget. Try new products carefully and follow their label directions. "
            + caution
        )
    else:
        response_text = (
            "I could not find an in-stock product that matches those filters. Broaden "
            "the category or budget, or explore our educational guides. " + caution
        )

    conversation = AIConversation(
        user_id=user.id,
        query=payload.query.strip(),
        response=response_text,
    )
    db.add(conversation)
    db.flush()

    recommendations = []
    for _, product, quantity, reasons in selected:
        reason = "; ".join(reasons) or (
            "available in the DermaSphere catalogue and currently in stock"
        )
        db.add(
            AIRecommendation(
                conversation_id=conversation.id,
                product_id=product.id,
                reason=reason,
            )
        )
        recommendations.append(
            {
                "id": product.id,
                "name": product.name,
                "brand": product.brand,
                "price": product.price,
                "image_url": product.image_url,
                "available_quantity": quantity,
                "reason": reason,
            }
        )

    db.commit()
    return {
        "conversation_id": conversation.id,
        "response": response_text,
        "recommendations": recommendations,
    }


@router.get("/history")
def history(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conversations = db.scalars(
        select(AIConversation)
        .where(AIConversation.user_id == user.id)
        .order_by(AIConversation.created_at.desc())
        .limit(100)
    ).all()
    result = []
    for conversation in conversations:
        rows = db.execute(
            select(Product.id, Product.name, AIRecommendation.reason)
            .join(AIRecommendation, AIRecommendation.product_id == Product.id)
            .where(AIRecommendation.conversation_id == conversation.id)
        ).all()
        result.append(
            {
                "id": conversation.id,
                "query": conversation.query,
                "response": conversation.response,
                "created_at": conversation.created_at,
                "recommendations": [
                    {
                        "product_id": row.id,
                        "product_name": row.name,
                        "reason": row.reason,
                    }
                    for row in rows
                ],
            }
        )
    return result
