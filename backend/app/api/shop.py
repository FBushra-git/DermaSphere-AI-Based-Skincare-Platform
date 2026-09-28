from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import (
    Cart,
    CartItem,
    Inventory,
    Order,
    OrderItem,
    OrderStatus,
    Product,
    ProductStatus,
    Review,
    Role,
    User,
    WishlistItem,
)
from app.schemas import CartItemInput, CheckoutInput, QuantityUpdate, ReviewCreate

router = APIRouter(tags=["shopping"])


def customer_only(user: User) -> None:
    if user.role != Role.CUSTOMER:
        raise HTTPException(
            status_code=403, detail="This action is available to customer accounts"
        )


def get_or_create_cart(db: Session, user_id: str) -> Cart:
    cart = db.scalar(select(Cart).where(Cart.user_id == user_id))
    if not cart:
        cart = Cart(user_id=user_id)
        db.add(cart)
        db.flush()
    return cart


@router.get("/api/cart")
def get_cart(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    customer_only(user)
    cart = get_or_create_cart(db, user.id)
    rows = db.execute(
        select(CartItem, Product, Inventory.available_quantity)
        .select_from(CartItem)
        .join(Product, CartItem.product_id == Product.id)
        .outerjoin(Inventory, Product.id == Inventory.product_id)
        .where(CartItem.cart_id == cart.id)
    ).all()
    items = [
        {
            "id": item.id,
            "product_id": product.id,
            "name": product.name,
            "brand": product.brand,
            "image_url": product.image_url,
            "unit_price": product.price,
            "quantity": item.quantity,
            "available_quantity": stock or 0,
            "line_total": product.price * item.quantity,
        }
        for item, product, stock in rows
    ]
    return {
        "items": items,
        "subtotal": sum((row["line_total"] for row in items), Decimal("0.00")),
    }


@router.post("/api/cart/items", status_code=status.HTTP_201_CREATED)
def add_cart_item(
    payload: CartItemInput,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    customer_only(user)
    product = db.get(Product, payload.product_id)
    if not product or product.status != ProductStatus.APPROVED:
        raise HTTPException(status_code=404, detail="Approved product not found")
    cart = get_or_create_cart(db, user.id)
    item = db.scalar(
        select(CartItem).where(
            CartItem.cart_id == cart.id, CartItem.product_id == product.id
        )
    )
    quantity = payload.quantity + (item.quantity if item else 0)
    inventory = db.get(Inventory, product.id)
    if not inventory or inventory.available_quantity < quantity:
        raise HTTPException(
            status_code=409, detail="Requested quantity is not available"
        )
    if item:
        item.quantity = quantity
    else:
        item = CartItem(cart_id=cart.id, product_id=product.id, quantity=quantity)
        db.add(item)
    db.commit()
    return {"id": item.id, "product_id": product.id, "quantity": item.quantity}


@router.patch("/api/cart/items/{item_id}")
def update_cart_item(
    item_id: str,
    payload: QuantityUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    customer_only(user)
    item = db.scalar(
        select(CartItem)
        .join(Cart)
        .where(CartItem.id == item_id, Cart.user_id == user.id)
    )
    if not item:
        raise HTTPException(status_code=404, detail="Cart item not found")
    inventory = db.get(Inventory, item.product_id)
    if not inventory or inventory.available_quantity < payload.quantity:
        raise HTTPException(
            status_code=409, detail="Requested quantity is not available"
        )
    item.quantity = payload.quantity
    db.commit()
    return {"id": item.id, "quantity": item.quantity}


@router.delete("/api/cart/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_cart_item(
    item_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    customer_only(user)
    item = db.scalar(
        select(CartItem)
        .join(Cart)
        .where(CartItem.id == item_id, Cart.user_id == user.id)
    )
    if not item:
        raise HTTPException(status_code=404, detail="Cart item not found")
    db.delete(item)
    db.commit()


@router.get("/api/wishlist")
def get_wishlist(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    customer_only(user)
    return (
        db.execute(
            select(Product)
            .join(WishlistItem, WishlistItem.product_id == Product.id)
            .where(WishlistItem.user_id == user.id)
            .order_by(WishlistItem.created_at.desc())
        )
        .scalars()
        .all()
    )


@router.post("/api/wishlist/{product_id}", status_code=status.HTTP_201_CREATED)
def add_to_wishlist(
    product_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    customer_only(user)
    product = db.get(Product, product_id)
    if not product or product.status != ProductStatus.APPROVED:
        raise HTTPException(status_code=404, detail="Approved product not found")
    existing = db.scalar(
        select(WishlistItem).where(
            WishlistItem.user_id == user.id, WishlistItem.product_id == product_id
        )
    )
    if not existing:
        db.add(WishlistItem(user_id=user.id, product_id=product_id))
        db.commit()
    return {"product_id": product_id, "saved": True}


@router.delete("/api/wishlist/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_from_wishlist(
    product_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    customer_only(user)
    item = db.scalar(
        select(WishlistItem).where(
            WishlistItem.user_id == user.id, WishlistItem.product_id == product_id
        )
    )
    if not item:
        raise HTTPException(status_code=404, detail="Wishlist item not found")
    db.delete(item)
    db.commit()


@router.post("/api/orders", status_code=status.HTTP_201_CREATED)
def checkout(
    payload: CheckoutInput,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    customer_only(user)
    cart = db.scalar(select(Cart).where(Cart.user_id == user.id))
    if not cart:
        raise HTTPException(status_code=409, detail="Your cart is empty")
    items = db.scalars(
        select(CartItem).where(CartItem.cart_id == cart.id).with_for_update()
    ).all()
    if not items:
        raise HTTPException(status_code=409, detail="Your cart is empty")
    lines = []
    total = Decimal("0.00")
    try:
        for item in items:
            product = db.scalar(
                select(Product).where(Product.id == item.product_id).with_for_update()
            )
            inventory = db.scalar(
                select(Inventory)
                .where(Inventory.product_id == item.product_id)
                .with_for_update()
            )
            if not product or product.status != ProductStatus.APPROVED:
                raise HTTPException(
                    status_code=409, detail="A cart product is no longer available"
                )
            if not inventory or inventory.available_quantity < item.quantity:
                raise HTTPException(
                    status_code=409, detail=f"Insufficient stock for {product.name}"
                )
            line_total = product.price * item.quantity
            total += line_total
            lines.append((item, product, inventory))
        order = Order(
            user_id=user.id,
            total_amount=total,
            shipping_address=payload.shipping_address.strip(),
            status=OrderStatus.PENDING,
        )
        db.add(order)
        db.flush()
        for item, product, inventory in lines:
            inventory.available_quantity -= item.quantity
            inventory.sold_quantity += item.quantity
            db.add(
                OrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    seller_id=product.seller_id,
                    product_name=product.name,
                    quantity=item.quantity,
                    unit_price=product.price,
                )
            )
            db.delete(item)
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(order)
    return {
        "id": order.id,
        "total_amount": order.total_amount,
        "status": order.status,
        "created_at": order.created_at,
    }


@router.get("/api/orders")
def list_orders(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    customer_only(user)
    orders = db.scalars(
        select(Order).where(Order.user_id == user.id).order_by(Order.created_at.desc())
    ).all()
    return [
        {
            "id": order.id,
            "total_amount": order.total_amount,
            "status": order.status,
            "created_at": order.created_at,
        }
        for order in orders
    ]


@router.get("/api/orders/{order_id}")
def get_order(
    order_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    order = db.scalar(
        select(Order).where(Order.id == order_id, Order.user_id == user.id)
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    items = db.scalars(select(OrderItem).where(OrderItem.order_id == order.id)).all()
    return {
        "id": order.id,
        "status": order.status,
        "total_amount": order.total_amount,
        "shipping_address": order.shipping_address,
        "created_at": order.created_at,
        "items": [
            {
                "product_id": item.product_id,
                "product_name": item.product_name,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
            }
            for item in items
        ],
    }


@router.post("/api/products/{product_id}/reviews", status_code=status.HTTP_201_CREATED)
def create_review(
    product_id: str,
    payload: ReviewCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    customer_only(user)
    product = db.get(Product, product_id)
    if not product or product.status != ProductStatus.APPROVED:
        raise HTTPException(status_code=404, detail="Approved product not found")
    purchased = db.scalar(
        select(OrderItem.id)
        .join(Order)
        .where(
            Order.user_id == user.id,
            OrderItem.product_id == product_id,
            Order.status == OrderStatus.DELIVERED,
        )
        .limit(1)
    )
    if not purchased:
        raise HTTPException(
            status_code=403,
            detail="Reviews are available after this product is delivered",
        )
    if db.scalar(
        select(Review.id).where(
            Review.user_id == user.id, Review.product_id == product_id
        )
    ):
        raise HTTPException(
            status_code=409, detail="You have already reviewed this product"
        )
    review = Review(
        user_id=user.id, product_id=product_id, rating=payload.rating, body=payload.body
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return {
        "id": review.id,
        "rating": review.rating,
        "body": review.body,
        "created_at": review.created_at,
    }


@router.get("/api/products/{product_id}/reviews")
def list_reviews(
    product_id: str, page: int = 1, page_size: int = 20, db: Session = Depends(get_db)
):
    if page < 1 or not 1 <= page_size <= 100:
        raise HTTPException(status_code=422, detail="Invalid pagination values")
    rows = db.execute(
        select(Review, User.name)
        .join(User)
        .where(Review.product_id == product_id, Review.is_reported.is_(False))
        .order_by(Review.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return [
        {
            "id": review.id,
            "name": name,
            "rating": review.rating,
            "body": review.body,
            "created_at": review.created_at,
        }
        for review, name in rows
    ]


@router.post("/api/orders/{order_id}/cancel")
def cancel_order(
    order_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    customer_only(user)
    order = db.scalar(
        select(Order)
        .where(Order.id == order_id, Order.user_id == user.id)
        .with_for_update()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status not in {OrderStatus.PENDING, OrderStatus.CONFIRMED}:
        raise HTTPException(
            status_code=409, detail="This order can no longer be cancelled"
        )

    items = db.scalars(select(OrderItem).where(OrderItem.order_id == order.id)).all()
    for item in items:
        inventory = db.scalar(
            select(Inventory)
            .where(Inventory.product_id == item.product_id)
            .with_for_update()
        )
        if inventory:
            inventory.available_quantity += item.quantity
            inventory.sold_quantity = max(0, inventory.sold_quantity - item.quantity)
    order.status = OrderStatus.CANCELLED
    db.commit()
    return {"id": order.id, "status": order.status}


@router.post("/api/reviews/{review_id}/report")
def report_review(
    review_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role != Role.CUSTOMER:
        raise HTTPException(status_code=403, detail="Only customers can report reviews")
    review = db.get(Review, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    if review.user_id == user.id:
        raise HTTPException(status_code=409, detail="You cannot report your own review")
    review.is_reported = True
    db.commit()
    return {"id": review.id, "reported": True}
