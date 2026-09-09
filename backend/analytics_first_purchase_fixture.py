"""Bounded JSON fixture for the shared owned worker. No database connection."""
from dataclasses import dataclass
import json
from backend.contracts.analytics_first_purchase import FirstPurchaseSnapshot, snapshot_digest
from backend.contracts.analytics_first_purchase_kernel import FirstPurchaseFixtureDescriptor

@dataclass(frozen=True)
class FirstPurchaseFixture:
    payload: str

    def validate(self):
        if len(self.payload.encode()) > 24000:
            raise ValueError("first-purchase fixture exceeds isolated worker wire budget")
        return FirstPurchaseSnapshot.model_validate(json.loads(self.payload))

    def binding_descriptor(self):
        snapshot = self.validate()
        return FirstPurchaseFixtureDescriptor(snapshot=snapshot, data_digest=snapshot_digest(snapshot)).model_dump(mode="json")


def create_first_purchase_fixture(snapshot):
    model = FirstPurchaseSnapshot.model_validate(snapshot)
    fixture = FirstPurchaseFixture(model.model_dump_json())
    fixture.validate()
    return fixture
