from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl


class UserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    role: str = Field(default="customer", pattern="^(customer|seller)$")
    store_name: str | None = Field(default=None, max_length=160)


class LoginInput(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserRead(BaseModel):
    id: str
    name: str
    email: EmailStr
    role: str
    model_config = ConfigDict(from_attributes=True)


class TokenRead(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead


class AccountProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = Field(default=None, max_length=32)
    address: str | None = Field(default=None, max_length=2000)


class AccountStatusUpdate(BaseModel):
    is_active: bool


class ProductCreate(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    brand: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=10)
    price: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    category_id: str | None = None
    image_url: HttpUrl | None = None
    benefits: str | None = None
    usage_instructions: str | None = None
    cautions: str | None = None
    stock_quantity: int = Field(default=0, ge=0)
    ingredient_ids: list[str] = Field(default_factory=list)
    skin_type_ids: list[str] = Field(default_factory=list)
    skin_concern_ids: list[str] = Field(default_factory=list)


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    brand: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, min_length=10)
    price: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    category_id: str | None = None
    image_url: HttpUrl | None = None
    benefits: str | None = None
    usage_instructions: str | None = None
    cautions: str | None = None
    ingredient_ids: list[str] | None = None
    skin_type_ids: list[str] | None = None
    skin_concern_ids: list[str] | None = None


class ProductRead(BaseModel):
    id: str
    name: str
    brand: str
    description: str
    price: Decimal
    image_url: str | None
    benefits: str | None
    usage_instructions: str | None
    cautions: str | None
    status: str
    model_config = ConfigDict(from_attributes=True)


class ProductDecision(BaseModel):
    comment: str | None = Field(default=None, max_length=2000)


class ProfileUpdate(BaseModel):
    skin_type_id: str | None = None
    skin_concern_ids: list[str] = Field(default_factory=list)
    budget_min: Decimal | None = Field(
        default=None, ge=0, max_digits=10, decimal_places=2
    )
    budget_max: Decimal | None = Field(
        default=None, ge=0, max_digits=10, decimal_places=2
    )
    preferences: str | None = Field(default=None, max_length=4000)


class NamedRecord(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    description: str | None = None


class IngredientCreate(NamedRecord):
    common_uses: str | None = None
    benefits: str | None = None
    cautions: str | None = None


class IngredientUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    description: str | None = None
    common_uses: str | None = None
    benefits: str | None = None
    cautions: str | None = None


class CartItemInput(BaseModel):
    product_id: str
    quantity: int = Field(ge=1, le=99)


class QuantityUpdate(BaseModel):
    quantity: int = Field(ge=1, le=99)


class CheckoutInput(BaseModel):
    shipping_address: str = Field(min_length=8, max_length=2000)


class ReviewCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    body: str | None = Field(default=None, max_length=5000)


class ReviewModeration(BaseModel):
    is_reported: bool


class RoutineCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str | None = None
    routine_type: str = Field(default="custom", pattern="^(morning|evening|custom)$")


class RoutineUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = None
    routine_type: str | None = Field(default=None, pattern="^(morning|evening|custom)$")


class RoutineItemInput(BaseModel):
    product_id: str
    sequence: int = Field(ge=1)
    step_note: str | None = Field(default=None, max_length=255)


class SellerProfileUpdate(BaseModel):
    store_name: str = Field(min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=4000)


class InventoryUpdate(BaseModel):
    available_quantity: int = Field(ge=0)


class OrderStatusUpdate(BaseModel):
    status: str = Field(pattern="^(confirmed|processing|shipped|delivered)$")


class AdminOrderStatusUpdate(BaseModel):
    status: str = Field(pattern="^(confirmed|processing|shipped|delivered|cancelled)$")


class AIChatInput(BaseModel):
    query: str = Field(min_length=2, max_length=4000)
    skin_type_id: str | None = None
    skin_concern_ids: list[str] = Field(default_factory=list)
    category_id: str | None = None
    budget_max: Decimal | None = Field(
        default=None, ge=0, max_digits=10, decimal_places=2
    )
    limit: int = Field(default=4, ge=1, le=10)


class ContentCreate(BaseModel):
    title: str = Field(min_length=3, max_length=180)
    description: str | None = None
    category: str = Field(min_length=2, max_length=80)
    source: str | None = Field(default=None, max_length=180)
    url: HttpUrl | None = None
    is_published: bool = False


class ContentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=180)
    description: str | None = None
    category: str | None = Field(default=None, min_length=2, max_length=80)
    source: str | None = Field(default=None, max_length=180)
    url: HttpUrl | None = None
    is_published: bool | None = None
