import os
from contextlib import asynccontextmanager
from decimal import Decimal

os.environ.setdefault("MYSQL_URL", "sqlite://")
os.environ.setdefault(
    "JWT_SECRET", "test-secret-key-that-is-long-enough-for-local-tests"
)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.core.database import Base
from app.core.security import hash_password
from app.main import app
from app.models import (
    Ingredient,
    Inventory,
    Order,
    OrderStatus,
    Role,
    SkinConcern,
    SkinType,
    User,
)


@asynccontextmanager
async def empty_lifespan(_app):
    yield


@pytest.fixture
def client_and_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestSession = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)
    app.router.lifespan_context = empty_lifespan

    def override_get_db():
        with TestSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestSession.begin() as session:
        session.add(
            User(
                name="Test Admin",
                email="admin@example.com",
                password_hash=hash_password("admin-test-password-123"),
                role=Role.ADMIN,
            )
        )
        skin_type = SkinType(name="Test Combination")
        concern = SkinConcern(name="Test Dryness")
        ingredient = Ingredient(
            name="Test Ceramide", benefits="Supports the skin barrier"
        )
        session.add_all([skin_type, concern, ingredient])
        session.flush()
        record_ids = (skin_type.id, concern.id, ingredient.id)

    with TestClient(app) as client:
        yield client, TestSession, record_ids

    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


def bearer(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post(
        "/api/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_customer_seller_admin_flow(client_and_session):
    client, session_factory, record_ids = client_and_session
    skin_type_id, concern_id, ingredient_id = record_ids

    admin_registration = client.post(
        "/api/auth/register",
        json={
            "name": "Admin",
            "email": "fake-admin@example.com",
            "password": "test-password-123",
            "role": "admin",
        },
    )
    assert admin_registration.status_code == 422

    seller_signup = client.post(
        "/api/auth/register",
        json={
            "name": "Seller",
            "email": "seller@example.com",
            "password": "seller-test-password-123",
            "role": "seller",
            "store_name": "Care Store",
        },
    )
    assert seller_signup.status_code == 201
    seller_headers = {"Authorization": f"Bearer {seller_signup.json()['access_token']}"}
    seller_profile = client.patch(
        "/api/seller/profile",
        headers=seller_headers,
        json={
            "store_name": "Care Store Updated",
            "description": "Gentle skin essentials.",
        },
    )
    assert seller_profile.status_code == 200
    assert seller_profile.json()["store_name"] == "Care Store Updated"

    product_response = client.post(
        "/api/products",
        headers=seller_headers,
        json={
            "name": "Barrier Cream",
            "brand": "Care Lab",
            "description": "A daily moisturizer made for a gentle skincare routine.",
            "price": "14.50",
            "stock_quantity": 3,
            "ingredient_ids": [ingredient_id],
            "skin_type_ids": [skin_type_id],
            "skin_concern_ids": [concern_id],
        },
    )
    assert product_response.status_code == 201
    product_id = product_response.json()["id"]
    assert client.get("/api/products").json()["total"] == 0

    admin_headers = bearer(client, "admin@example.com", "admin-test-password-123")
    seller_records = client.get("/api/admin/sellers", headers=admin_headers)
    assert seller_records.status_code == 200
    seller_record = seller_records.json()[0]
    verification = client.patch(
        f"/api/admin/sellers/{seller_record['id']}/verification",
        headers=admin_headers,
        json={"verification_status": "verified"},
    )
    assert verification.status_code == 200
    assert verification.json()["verification_status"] == "verified"
    assert (
        client.patch(
            f"/api/admin/products/{product_id}/approve",
            headers=admin_headers,
            json={"comment": "Reviewed"},
        ).status_code
        == 200
    )
    detail = client.get(f"/api/products/{product_id}")
    assert detail.status_code == 200
    assert detail.json()["ingredients"][0]["name"] == "Test Ceramide"
    assert detail.json()["suitable_skin_types"] == ["Test Combination"]
    ingredient_detail = client.get(f"/api/ingredients/{ingredient_id}")
    assert ingredient_detail.status_code == 200
    assert ingredient_detail.json()["name"] == "Test Ceramide"
    assert ingredient_detail.json()["products"][0]["id"] == product_id
    seller_edit = client.patch(
        f"/api/seller/products/{product_id}",
        headers=seller_headers,
        json={
            "name": "Barrier Cream Updated",
            "ingredient_ids": [ingredient_id],
            "skin_type_ids": [skin_type_id],
            "skin_concern_ids": [concern_id],
        },
    )
    assert seller_edit.status_code == 200
    assert seller_edit.json()["status"] == "pending"
    assert client.get("/api/products").json()["total"] == 0
    assert (
        client.patch(
            f"/api/admin/products/{product_id}/approve",
            headers=admin_headers,
            json={"comment": "Updated listing reviewed"},
        ).status_code
        == 200
    )
    seller_listing = client.get("/api/seller/products", headers=seller_headers)
    assert seller_listing.json()[0]["ingredient_ids"] == [ingredient_id]
    assert client.get("/api/ingredients/missing").status_code == 404

    customer_signup = client.post(
        "/api/auth/register",
        json={
            "name": "Customer",
            "email": "customer@example.com",
            "password": "customer-test-password-123",
        },
    )
    assert customer_signup.status_code == 201
    customer_headers = {
        "Authorization": f"Bearer {customer_signup.json()['access_token']}"
    }
    profile = client.put(
        "/api/users/profile/skin",
        headers=customer_headers,
        json={
            "skin_type_id": skin_type_id,
            "skin_concern_ids": [concern_id],
            "budget_min": "5",
            "budget_max": "30",
        },
    )
    assert profile.status_code == 200

    assert (
        client.post(f"/api/wishlist/{product_id}", headers=customer_headers).status_code
        == 201
    )
    assert len(client.get("/api/wishlist", headers=customer_headers).json()) == 1
    assert (
        client.post(
            "/api/cart/items",
            headers=customer_headers,
            json={"product_id": product_id, "quantity": 2},
        ).status_code
        == 201
    )
    assert client.get("/api/cart", headers=customer_headers).json()[
        "subtotal"
    ] == Decimal("29.00")
    assert (
        client.post(
            "/api/products/{product_id}/reviews".format(product_id=product_id),
            headers=customer_headers,
            json={"rating": 5},
        ).status_code
        == 403
    )

    order_response = client.post(
        "/api/orders",
        headers=customer_headers,
        json={"shipping_address": "12 Example Road, Dhaka"},
    )
    assert order_response.status_code == 201
    order_id = order_response.json()["id"]
    seller_orders = client.get("/api/seller/orders", headers=seller_headers)
    assert seller_orders.status_code == 200
    assert seller_orders.json()[0]["can_manage_order"] is True
    assert (
        client.patch(
            f"/api/seller/orders/{order_id}/status",
            headers=seller_headers,
            json={"status": "confirmed"},
        ).json()["status"]
        == "confirmed"
    )
    with session_factory.begin() as session:
        order = session.get(Order, order_id)
        order.status = OrderStatus.DELIVERED
    review = client.post(
        f"/api/products/{product_id}/reviews",
        headers=customer_headers,
        json={"rating": 5, "body": "A nice lightweight texture."},
    )
    assert review.status_code == 201

    routine = client.post(
        "/api/routines",
        headers=customer_headers,
        json={"name": "Morning routine", "routine_type": "morning"},
    )
    assert routine.status_code == 201
    routine_id = routine.json()["id"]
    assert (
        client.post(
            f"/api/routines/{routine_id}/products",
            headers=customer_headers,
            json={"product_id": product_id, "sequence": 1},
        ).status_code
        == 201
    )
    assert (
        client.patch(
            f"/api/routines/{routine_id}",
            headers=seller_headers,
            json={"name": "Not yours"},
        ).status_code
        == 404
    )

    seller_products = client.get("/api/seller/products", headers=seller_headers)
    assert seller_products.status_code == 200
    assert seller_products.json()[0]["available_quantity"] == 1
    assert (
        client.put(
            f"/api/seller/products/{product_id}/inventory",
            headers=seller_headers,
            json={"available_quantity": 8},
        ).status_code
        == 200
    )
    assert client.get("/api/seller/orders", headers=seller_headers).status_code == 200
    assistant_response = client.post(
        "/api/ai/chat",
        headers=customer_headers,
        json={"query": "ceramide moisturizer for dry skin", "limit": 3},
    )
    assert assistant_response.status_code == 200
    assert assistant_response.json()["recommendations"][0]["id"] == product_id
    assert "cannot diagnose" in assistant_response.json()["response"]
    assert len(client.get("/api/ai/history", headers=customer_headers).json()) == 1

    content = client.post(
        "/api/admin/content",
        headers=admin_headers,
        json={
            "title": "Skin barrier basics",
            "category": "Guide",
            "is_published": True,
        },
    )
    assert content.status_code == 201
    assert client.get("/api/content").json()[0]["title"] == "Skin barrier basics"
    admin_content = client.get("/api/admin/content", headers=admin_headers)
    assert admin_content.status_code == 200
    content_id = content.json()["id"]
    assert (
        client.patch(
            f"/api/admin/content/{content_id}",
            headers=admin_headers,
            json={"is_published": False},
        ).status_code
        == 200
    )
    assert client.get("/api/content").json() == []
    assert (
        client.delete(
            f"/api/admin/content/{content_id}", headers=admin_headers
        ).status_code
        == 204
    )
    reports = client.get("/api/admin/reports/overview", headers=admin_headers)
    assert reports.status_code == 200
    assert reports.json()["total_users"] == 3


def test_account_admin_tools_and_order_cancellation(client_and_session):
    client, session_factory, _ = client_and_session
    admin_headers = bearer(client, "admin@example.com", "admin-test-password-123")

    seller_signup = client.post(
        "/api/auth/register",
        json={
            "name": "Seller",
            "email": "seller-admin@example.com",
            "password": "seller-test-password-123",
            "role": "seller",
            "store_name": "Admin Test Store",
        },
    )
    seller_headers = {"Authorization": f"Bearer {seller_signup.json()['access_token']}"}
    product = client.post(
        "/api/products",
        headers=seller_headers,
        json={
            "name": "Order Test Cream",
            "brand": "Test Lab",
            "description": "A simple moisturizer for daily order processing checks.",
            "price": "9.00",
            "stock_quantity": 3,
        },
    ).json()
    product_id = product["id"]
    assert (
        client.patch(
            f"/api/admin/products/{product_id}/approve",
            headers=admin_headers,
            json={},
        ).status_code
        == 200
    )

    customer = client.post(
        "/api/auth/register",
        json={
            "name": "Customer",
            "email": "customer-admin@example.com",
            "password": "customer-test-password-123",
        },
    ).json()
    customer_headers = {"Authorization": f"Bearer {customer['access_token']}"}
    profile = client.patch(
        "/api/users/profile",
        headers=customer_headers,
        json={"name": "Updated Customer", "phone": "+880 1700 000000"},
    )
    assert profile.status_code == 200
    assert profile.json()["name"] == "Updated Customer"

    assert (
        client.post(
            "/api/cart/items",
            headers=customer_headers,
            json={"product_id": product_id, "quantity": 1},
        ).status_code
        == 201
    )
    customer_order = client.post(
        "/api/orders",
        headers=customer_headers,
        json={"shipping_address": "9 Example Road, Dhaka"},
    ).json()
    assert (
        client.post(
            f"/api/orders/{customer_order['id']}/cancel",
            headers=customer_headers,
        ).status_code
        == 200
    )
    with session_factory() as session:
        inventory = session.get(Inventory, product_id)
        assert inventory.available_quantity == 3

    assert (
        client.post(
            "/api/cart/items",
            headers=customer_headers,
            json={"product_id": product_id, "quantity": 2},
        ).status_code
        == 201
    )
    admin_order = client.post(
        "/api/orders",
        headers=customer_headers,
        json={"shipping_address": "9 Example Road, Dhaka"},
    ).json()
    assert (
        client.patch(
            f"/api/admin/orders/{admin_order['id']}/status",
            headers=admin_headers,
            json={"status": "cancelled"},
        ).status_code
        == 200
    )
    with session_factory() as session:
        inventory = session.get(Inventory, product_id)
        assert inventory.available_quantity == 3

    assert client.get("/api/admin/users", headers=admin_headers).json()["total"] == 3
    assert len(client.get("/api/admin/sellers", headers=admin_headers).json()) == 1
    assert len(client.get("/api/admin/orders", headers=admin_headers).json()) == 2
    assert (
        client.patch(
            f"/api/admin/products/{product_id}/archive",
            headers=admin_headers,
            json={"comment": "No longer listed"},
        ).status_code
        == 200
    )
    assert client.get(f"/api/products/{product_id}").status_code == 404
