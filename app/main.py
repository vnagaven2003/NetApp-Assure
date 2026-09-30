"""Small inventory service used as the target of network and API tests."""

from fastapi import FastAPI, HTTPException, Path
from pydantic import BaseModel

app = FastAPI(title="NetApp Assure — Lab Inventory", version="0.1.0")


class Device(BaseModel):
    id: int
    name: str
    platform: str


DEVICES = (
    Device(id=1, name="r1", platform="FRR"),
    Device(id=2, name="r2", platform="FRR"),
)


@app.get("/health")
def health() -> dict[str, str]:
    # Application liveness only; this does not claim that routing is healthy.
    return {"status": "ok"}


@app.get("/devices", response_model=list[Device])
def list_devices() -> list[Device]:
    return list(DEVICES)


@app.get("/devices/{device_id}", response_model=Device)
def get_device(device_id: int = Path(gt=0)) -> Device:
    for device in DEVICES:
        if device.id == device_id:
            return device
    raise HTTPException(status_code=404, detail="Device not found")
