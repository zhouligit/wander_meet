from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from app.schemas.datetime_iso import datetime_to_rfc3339_utc_z_shanghai_naive


class PayProductRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_id: str = Field(validation_alias=AliasChoices("user_id", "userId"))
    qr_id: str = Field(validation_alias=AliasChoices("qr_id", "qrId"))
    product: str = "publish"


class PayPublishQrcodeRequest(PayProductRequest):
    pass


class PayPublishMinipayRequest(PayProductRequest):
    code: str = Field(min_length=1, max_length=128)


class PayPublishQrcodeData(BaseModel):
    qrId: str
    outTradeNo: str
    payCodeUrl: str


class PayMinipayData(BaseModel):
    qrId: str
    outTradeNo: str
    paymentParams: dict[str, str] | None = None
    mockSkip: bool = False


class PayStateData(BaseModel):
    paid: bool
    state: str
    paidAt: str | None = None
    payChannel: str | None = None

    @classmethod
    def from_order(
        cls, *, paid: bool, state: str, paid_at=None, pay_channel: str | None = None
    ) -> "PayStateData":
        paid_at_str = None
        if paid_at is not None:
            paid_at_str = datetime_to_rfc3339_utc_z_shanghai_naive(paid_at)
        return cls(paid=paid, state=state, paidAt=paid_at_str, payChannel=pay_channel)
